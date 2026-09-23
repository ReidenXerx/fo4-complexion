# LooksMenu BodyGen — what the files actually mean

Everything here is read from LooksMenu's own source (expired6978/F4SEPlugins, `f4ee/`), not from
mod-page folklore. File and function names are given so any line can be re-checked. Where the source
contradicts what people commonly say about BodyGen, the source is quoted.

## Where the files are read from

`BodyGenInterface::LoadBodyGenMods`:

1. For every **loaded** plugin, in load order: `F4SE\Plugins\F4EE\BodyGen\<Plugin.esp>\templates.ini`.
2. For every loaded plugin, in load order: `...\BodyGen\<Plugin.esp>\morphs.ini`.
3. Then `Data\F4SE\Plugins\F4EE\BodyGen\Loose\*_templates.ini`, and after all of those,
   `Loose\*_morphs.ini` — loaded **whatever plugins are active**, in **case-sensitive byte order**
   (the intended lowercasing is a no-op: `transform(begin, begin, end, ...)` has an empty range), so
   `Z...` sorts before `a...`.

So the `Loose` folder needs no `.esp`, and loads after (therefore overrides) every per-plugin folder.
Only loose files are seen there (a real `IDirectoryIterator`, not the archive-aware resource
system). BodyGen must be enabled: `f4ee.ini` → `[BodyMorph] bEnable=1, bEnableBodyGen=1`, and
`bEnableModelPreprocessor=1` (it maps a mesh to its `.tri`). Its log lines ("Loaded N template(s)",
"Acquired N ... target(s)", "template not found") only appear with `iLogLevel` of 3 or more — the
default 1 prints errors only.

Both files are read line by line through the ENGINE's `BSResourceTextFile::ReadLine` (F4SE
0.6.23 `0x01B93C40`, disassembled): it returns the number of bytes before the `'\n'`, and both
parsers loop `while (textFile.ReadLine(&str))`. **So an empty line ends the file when the endings
are LF** — everything after it is silently never read. With CRLF an "empty" line is `\r` and
survives, which is the only reason blank lines ever worked. Write CRLF and no empty lines. A line
longer than 32,766 bytes is split into the next line, not cut. After trimming, lines **starting
with `#`** are skipped.

## templates.ini

```
Name = set / set / ...
set  = morph , morph , ...
morph = selector | selector | ...
selector = MorphName@value   or   MorphName@low:high
```

| Separator | Meaning | Source |
| --- | --- | --- |
| `=` | name on the left; only the first two pieces are used | `explode(str, '=')` |
| `/` | alternative **sets** — one chosen uniformly at random | `BodyGenTemplate::Evaluate` |
| `,` | every morph in the set is applied | `BodyGenMorphs::Evaluate` |
| `\|` | alternative selectors for one morph — one chosen at random | `BodyGenMorphSelector::Evaluate` |
| `@` | name, then value | |
| `:` | inside the value: uniform random between low and high | |

- Values are parsed with **`atof`**: negative values are accepted and meaningful.
- **Any malformed entry drops the whole template** (missing `@`, empty name, empty value). A
  `morphs.ini` line that names a dropped template then logs *"template not found"* and silently
  loses that option — the pool shrinks and nothing visible says so.
- A template defined twice: the later definition replaces the earlier.
- Morph names may contain spaces (they are trimmed only at the ends). They must not contain
  `= / , | @`. `:` in a name is harmless — only the value is split on it.

## morphs.ini

```
All|Gender|Race                = templates
Plugin.esp|All|Gender|Race     = templates      (every NPC defined in that plugin)
Plugin.esp|FormID|Gender       = templates      (one NPC, or every NPC in a leveled list)
templates = group , group , ...                 (',' = every group applied)
group     = Template | Template | ...           ('|' = one chosen uniformly at random)
```

- **A later line OVERWRITES an earlier one for the same NPC** (`bodyGenData[gender][npc] = ...`).
  Priority is simply file order, then file-name order, then per-plugin before `Loose`.
- Gender is optional; without it the line applies to both.
- **The race is not optional in practice.** `GetFilteredNPCList` matches with
  `npc->race == nullptr || npc->race == raceFilter`, so `All|Female` with *no* race matches only NPCs
  that have no race at all. Always name one (`HumanRace`).
- **Gender is not a filter on the NPC's sex.** It chooses which of two tables the NPC is put in; at
  run time the table is picked by the actor's actual sex. Same effect, but an NPC is not rejected
  for being "the wrong gender" at parse time.
- Only NPCs **without a template** are listed by `All`/plugin lines (`npc->templateNPC == nullptr`).
  At evaluation the actor's base is followed up its template chain until one is found in the table,
  so generated/leveled actors still resolve through their root.
- FormIDs are written **without** the load-order byte; it is added from the plugin named. Light
  (ESL) plugins are supported with a local id of at most `FFF` (LooksMenu ORs the id into
  `0xFE000000 | light << 12`). A `TESLevCharacter` is expanded to every NPC it can produce.
- A line whose templates are ALL missing still overwrites the NPC's entry — with an empty choice.
  The NPC gets nothing; it does not fall back to an earlier line.
- `Plugin|All|...` reaches only NPCs a plugin DEFINES, not ones it overrides (OBody's plugin keys
  include overrides).
- `_strnicmp(name, "all", 3)`: a plugin whose name *starts with* "all" is read as `All`.
- Weighting is by repetition: list a template twice to double its chance.

## When BodyGen runs, and what makes it stick

`ActorUpdateManager` evaluates BodyGen for an actor **only when it has no stored morphs**
(`GetMorphMap(actor) == nullptr`): on `TESObjectLoadedEvent`, on `TESInitScriptEvent` for new
references, and for actors that loaded during a save load. The result is stored per actor in the
F4SE co-save.

Two consequences nobody writes down:

1. **A template that sets nothing re-rolls every load.** A morph whose value evaluates to 0 is
   skipped before `SetMorph` (`if (val != 0)`), so an all-zero template leaves the actor with no
   stored morphs, and the next load evaluates it again. A zero template is not "keep the base
   body" — it is "roll again next time". It only behaves as a blacklist when *every* option it can
   pick is zero (e.g. the only template on a dedicated line).
2. **The player is not special-cased.** `All|...|HumanRace` includes the Player record
   (`Fallout4.esm` `0x7`). A player who never set a LooksMenu body slider has no stored morphs and
   is randomised on the next load like anybody else.
3. **A new game clones a dummy onto the player.** The mirror at character creation shows
   `MQ101PlayerSpouseMale` (`A7D34`) and `MQ101PlayerSpouseFemale` (`A7D35`) — HumanRace, no
   template, so `All` lines roll them. On confirm, LooksMenu's `CloneBodyMorphs` copies the chosen
   dummy's morphs onto the player (`CloneMorphs`), past any line for `0x7`. Give the dummies what
   the player should get.

4. **Another mod's morph shuts BodyGen out.** "No stored morphs" means none from anyone: an actor
   that already holds, say, AAF's `Erection` morph from an earlier scene (measured in a real
   co-save) is never evaluated, so it never gets a BodyGen body. Silhouette's MCM "Give the
   people around me new bodies" (`RegenerateMorphs`) clears such actors and rolls them.

Stored morphs survive save and load with any name: `MorphValueMap::Save` writes every entry and
`Load` drops only zero values and keywords that no longer resolve — nothing is checked against a
`.tri`. So a marker is permanent.

## How a value becomes a shape

`BodyMorphInterface::ApplyMorphsToShape` restores the original vertex block, then for every stored
morph with a non-zero effective value: `vertex += diff * value` (`TriShape*VertexData::ApplyMorph`).

- **No clamp.** Negative values push the other way, values above 1 go further.
- **Unknown morph names are harmless.** `SetMorph` stores any name; a name absent from the shape's
  `.tri` is simply skipped when applying. This is what makes a marker morph possible.
- **Keyed values combine by MAX, not by sum.** A morph can hold one value per keyword;
  `UserValues::GetEffectiveValue` returns the largest (`std::max_element`). BodyGen writes with no
  keyword. Anything layering on top with its own keyword *replaces* the value when larger and is
  *ignored* when smaller — it does not add. (Skyrim's RaceMenu sums. Do not assume the same here.)
- Setting a value of 0 erases that key.
- The `.tri` is found from the mesh path; a `BSDynamicTriShape` (heads) cannot be morphed.

## The Papyrus API

LooksMenu registers these on the script `BodyGen` (`PapyrusBodyGen.cpp`, `RegisterFuncs`); the
`.pex` ships inside `LooksMenu - Main.ba2`, so a build needs an import stub (`papyrus-stubs/BodyGen.psc`
here is declared argument for argument from the registrations):

```
SetMorph(Actor, Bool isFemale, String morph, Keyword, Float value)
Float GetMorph(Actor, Bool isFemale, String morph, Keyword)
String[] GetMorphs(Actor, Bool isFemale)          ; every morph name the actor holds
Keyword[] GetKeywords(Actor, Bool isFemale, String morph)
RemoveMorphsByName(Actor, Bool, String) / RemoveMorphsByKeyword(Actor, Bool, Keyword)
RemoveAllMorphs(Actor, Bool isFemale)
RegenerateMorphs(Actor, Bool update)              ; clear, run BodyGen again, apply if update
UpdateMorphs(Actor)                               ; re-apply stored morphs to the 3D
ClearAll()
Bool SetSkinOverride(Actor, String id) / Bool RemoveSkinOverride(Actor)
```

`None` as the keyword writes the same key BodyGen and LooksMenu's own body editor use.

## How BodySlide produced what BodyGen moves

From BodySlide's source (ousnius/BodySlide-and-Outfit-Studio):

- **`BuildBodies`**: the built mesh is `reference + Σ value_i × diff_i`. A slider the preset does
  not name is built at the **slider set's default**, not 0 (BodyTalk 4 has 26 sliders defaulting to
  100). `invert="true"` turns `v` into `1 − v`, default included. Fallout 4 sets never generate
  weights, so only the **big** value is used.
- **`WriteMorphTRI`** ("Build Morphs"): every non-zap, non-UV, non-clamp slider is written at
  **1.0 into an empty vector** — the `.tri` holds raw diffs and does not depend on the preset.
- **`LoadPresetFile`**: `size="big"` sets big, `"both"` sets both, `"small"` sets only small, a
  `SetSlider` without `size` is ignored; files are gathered **recursively** and the **first** preset
  of a name wins. Preset XML values are 0–100; BodyGen wants 0–1.
- A preset's `set` attribute records which slider set was open when it was saved. It is **not** what
  the preset is for; its `<Group>` tags are.

Therefore BodyGen morphs stack on whatever the base mesh has baked in. A base built from anything but
zeroed sliders makes every NPC preset land on top of it. See `tools/base_body.py`, which measures
what is baked and compensates for it.
