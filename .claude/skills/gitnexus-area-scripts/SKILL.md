---
name: gitnexus-area-scripts
description: "Skill for the Scripts area of fo4-silhouette. 34 symbols across 6 files."
---

# Scripts

34 symbols | 6 files | Cohesion: 84%

## When to Use

- Working with code in `scripts/`
- Understanding how verifyInstall, main, make_cmake work
- Modifying scripts-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/bearing-verify.mjs` | checkModuleDelivery, checkRuntimeCoversAgent, readRuntime, runtimeSet, checkPackageGates (+7) |
| `scripts/bearing-ci.mjs` | blastRadius, collectDiff, detectChanges, num, gn (+4) |
| `scripts/bearing-token-benchmark.mjs` | classicalCost, cypher, gn, graphCost, pickTargets (+1) |
| `scripts/bearing-agent.mjs` | currentBranch, git, resolveBaseRef |
| `extern/CommonLibF4/CommonLibF4/scripts/glob_files.py` | main, make_cmake |
| `scripts/strip-pex.py` | main, strip |

## Entry Points

Start here when exploring this area:

- **`verifyInstall`** (Function) — `scripts/bearing-verify.mjs:367`
- **`main`** (Function) — `extern/CommonLibF4/CommonLibF4/scripts/glob_files.py:63`
- **`make_cmake`** (Function) — `extern/CommonLibF4/CommonLibF4/scripts/glob_files.py:39`
- **`main`** (Function) — `scripts/strip-pex.py:51`
- **`strip`** (Function) — `scripts/strip-pex.py:34`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `verifyInstall` | Function | `scripts/bearing-verify.mjs` | 367 |
| `main` | Function | `extern/CommonLibF4/CommonLibF4/scripts/glob_files.py` | 63 |
| `make_cmake` | Function | `extern/CommonLibF4/CommonLibF4/scripts/glob_files.py` | 39 |
| `main` | Function | `scripts/strip-pex.py` | 51 |
| `strip` | Function | `scripts/strip-pex.py` | 34 |
| `blastRadius` | Function | `scripts/bearing-ci.mjs` | 110 |
| `collectDiff` | Function | `scripts/bearing-ci.mjs` | 78 |
| `detectChanges` | Function | `scripts/bearing-ci.mjs` | 92 |
| `num` | Function | `scripts/bearing-ci.mjs` | 95 |
| `gn` | Function | `scripts/bearing-ci.mjs` | 57 |
| `main` | Function | `scripts/bearing-ci.mjs` | 331 |
| `render` | Function | `scripts/bearing-ci.mjs` | 155 |
| `riskTag` | Function | `scripts/bearing-ci.mjs` | 147 |
| `structural` | Function | `scripts/bearing-ci.mjs` | 125 |
| `classicalCost` | Function | `scripts/bearing-token-benchmark.mjs` | 175 |
| `cypher` | Function | `scripts/bearing-token-benchmark.mjs` | 68 |
| `gn` | Function | `scripts/bearing-token-benchmark.mjs` | 57 |
| `graphCost` | Function | `scripts/bearing-token-benchmark.mjs` | 143 |
| `pickTargets` | Function | `scripts/bearing-token-benchmark.mjs` | 88 |
| `tok` | Function | `scripts/bearing-token-benchmark.mjs` | 44 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → Git` | intra_community | 3 |
| `Main → Num` | intra_community | 3 |
| `Main → Gn` | intra_community | 3 |
| `VerifyInstall → ReadStealth` | intra_community | 3 |

## How to Explore

1. `context({name: "verifyInstall"})` — see callers and callees
2. `query({search_query: "scripts"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
