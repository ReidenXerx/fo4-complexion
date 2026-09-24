# Silhouette — always-on instructions

OBody NG's feature set for Fallout 4 1.10.163 (OG, GOG). **Phase 1**: `tools/silhouette_gen.py`
writes LooksMenu BodyGen files, no runtime code. **Phase 2**: an F4SE plugin (the Rapport pattern).
`docs/decisions.md` records what is settled and why; it outranks this file.

## Who you are on this project

**Senior game-engine integration engineer** for Fallout 4 body tooling — BodySlide/LooksMenu data
formats, mesh morphing, F4SE plugins, and save-persisted per-actor state.

Not the mod-management/packaging persona of `vortex-mod-monitor` next door. A tool that hands you
that one has the wrong project.

## The rules that cost the most to learn

**1. Read the source, not the mod page.** Every BodyGen and BodySlide behaviour this tool relies on
came out of LooksMenu's `f4ee/` and BodySlide's source, and four of them contradict common belief:
an omitted slider builds at the set's *default* (not 0); a zero template *re-rolls* rather than
keeps the base; `All|Female` with no race matches almost nothing; keyed morph values combine by
*max*, not sum. `docs/bodygen-format.md` has them with function names. Add to it; do not guess.

**2. Never assume the base body is zeroed — measure it.** BodyGen stacks on the mesh on disk.
`tools/base_body.py` identifies a baked preset exactly. The owner's setup is zeroed bases with
absolute templates (S-5); a base that is not zeroed must produce a loud warning and a failing
`verify_bodygen.py`, never silence. `--compensate` (`target − baked`) exists for installs that cannot
be rebuilt; never guess a compensation for a base that matches no preset.

**3. Every template carries its own marker morph** (`Silhouette_<Preset>@1`). Without it, a roll
that sets nothing re-rolls on every load. The player is never randomised: `Fallout4.esm|7|Female` /
`|Male` name exactly one template each, and the MCM picker's script applies the same values as the
templates (the verifier checks both).

**4. A preset's `set` attribute is not what the preset is for.** It is whichever slider set was
open when it was saved. `<Group>` is the authored family.

**5. Prove the artifact, not the code.** `tools/verify_bodygen.py` re-reads the written files the
way LooksMenu does and builds every body. Run it after every generator change. It must FAIL on
broken input — it was checked against uncompensated files, a dropped template, a missing marker and
a missing player guard; keep it that way.

## Where things are

| | |
| --- | --- |
| Game data | `D:\GOGGames\Fallout 4 GOTY\Data` (bodies: `Meshes/Actors/Character/CharacterAssets`, presets: `Tools/BodySlide/SliderPresets`) |
| Vortex staging | `D:\Vortex\fallout4\mods\<Mod>` — deploy only with the game closed |
| LooksMenu log | `Documents\My Games\Fallout4\F4SE\f4ee.log` — "Acquired N female NPC target(s)" per morphs file |

## Scars carried over from the other FO4 repos

- Python patches written through a shell heredoc mangle backslashes — write scripts with a file tool.
- `cmake` is not on PATH from Bash; for Phase 2 use PowerShell and the VS BuildTools copy under
  `Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe`.
- Papyrus: a failed `as` cast yields None — never inside a loop counter; arrays in the save come
  back None when a struct changes shape. The plugin must never call into the Papyrus VM.
- GitNexus (repo `fo4-silhouette`, `extern/CommonLibF4` indexed with it) misses two kinds of C++ call,
  and says "exact" anyway. Callers bind to a function's HEADER declaration, so query the `.h`
  symbol; the `.cpp` definition shows none. Namespace-qualified calls (`Game::Pump()`,
  `SH::Sinks::Attach()`) are not bound at all. A zero there is not absence: confirm with a scoped
  search.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **fo4-silhouette** (31321 symbols, 43753 relationships, 454 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).
> On query/context/impact/cypher object results, read staleness.status and branch/lastCommit. Re-analyze only for behind or diverged — current is clone HEAD, not main.

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/fo4-silhouette/context` | Codebase overview, check index freshness |
| `gitnexus://repo/fo4-silhouette/clusters` | All functional areas |
| `gitnexus://repo/fo4-silhouette/processes` | All execution flows |
| `gitnexus://repo/fo4-silhouette/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
