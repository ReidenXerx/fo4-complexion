---
name: gitnexus-area-cluster-222
description: "Skill for the Cluster_222 area of fo4-silhouette. 43 symbols across 1 files."
---

# Cluster_222

43 symbols | 1 files | Cohesion: 89%

## When to Use

- Working with code in `src/`
- Understanding how replaces, unkeyed, AfterProbe work
- Modifying cluster_222-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `src/Director.cpp` | replaces, ChoiceOf, Chosen, ContainsI, unkeyed (+38) |

## Entry Points

Start here when exploring this area:

- **`replaces`** (Function) — `src/Director.cpp:810`
- **`unkeyed`** (Function) — `src/Director.cpp:1493`
- **`AfterProbe`** (Method) — `src/Director.cpp:437`
- **`AnnounceBody`** (Method) — `src/Director.cpp:817`
- **`BodyNamed`** (Method) — `src/Director.cpp:711`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `replaces` | Function | `src/Director.cpp` | 810 |
| `unkeyed` | Function | `src/Director.cpp` | 1493 |
| `AfterProbe` | Method | `src/Director.cpp` | 437 |
| `AnnounceBody` | Method | `src/Director.cpp` | 817 |
| `BodyNamed` | Method | `src/Director.cpp` | 711 |
| `BodyPending` | Method | `src/Director.cpp` | 356 |
| `BodyReplacing` | Method | `src/Director.cpp` | 808 |
| `CheckTouch` | Method | `src/Director.cpp` | 836 |
| `Claimed` | Method | `src/Director.cpp` | 468 |
| `DecideBody` | Method | `src/Director.cpp` | 610 |
| `Done` | Method | `src/Director.cpp` | 1674 |
| `Find` | Method | `src/Director.cpp` | 1358 |
| `FinishBody` | Method | `src/Director.cpp` | 1864 |
| `FinishPendingBody` | Method | `src/Director.cpp` | 594 |
| `FinishRefit` | Method | `src/Director.cpp` | 2019 |
| `FollowReset` | Method | `src/Director.cpp` | 497 |
| `FollowResetEveryone` | Method | `src/Director.cpp` | 543 |
| `FollowRoll` | Method | `src/Director.cpp` | 530 |
| `Intend` | Method | `src/Director.cpp` | 364 |
| `Log` | Method | `src/Director.cpp` | 2400 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `PickerKeep → BodyPending` | cross_community | 7 |
| `PickerKeep → PresetNamedBy` | cross_community | 7 |
| `PickerStart → BodyPending` | cross_community | 7 |
| `PickerStart → PresetNamedBy` | cross_community | 7 |
| `PickerKeep → Intend` | cross_community | 6 |
| `PickerKeep → Log` | cross_community | 6 |
| `PickerKeep → QueueBody` | cross_community | 6 |
| `PickerKeep → Chosen` | cross_community | 6 |
| `PickerKeep → RefitOn` | cross_community | 6 |
| `PickerStart → Intend` | cross_community | 6 |

## How to Explore

1. `context({name: "replaces"})` — see callers and callees
2. `query({search_query: "cluster_222"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
