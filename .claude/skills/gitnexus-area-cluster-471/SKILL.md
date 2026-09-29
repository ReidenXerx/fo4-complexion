---
name: gitnexus-area-cluster-471
description: "Skill for the Cluster_471 area of fo4-silhouette. 8 symbols across 1 files."
---

# Cluster_471

8 symbols | 1 files | Cohesion: 61%

## When to Use

- Working with code in `src/`
- Understanding how CancelPicking, ClosePicker, Gone work
- Modifying cluster_471-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `src/Director.cpp` | CancelPicking, ClosePicker, Gone, PendingRestore, PickerKeep (+3) |

## Entry Points

Start here when exploring this area:

- **`CancelPicking`** (Method) — `src/Director.cpp:2117`
- **`ClosePicker`** (Method) — `src/Director.cpp:2112`
- **`Gone`** (Method) — `src/Director.cpp:1768`
- **`PendingRestore`** (Method) — `src/Director.cpp:411`
- **`PickerKeep`** (Method) — `src/Director.cpp:2239`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `CancelPicking` | Method | `src/Director.cpp` | 2117 |
| `ClosePicker` | Method | `src/Director.cpp` | 2112 |
| `Gone` | Method | `src/Director.cpp` | 1768 |
| `PendingRestore` | Method | `src/Director.cpp` | 411 |
| `PickerKeep` | Method | `src/Director.cpp` | 2239 |
| `PutBackChoice` | Method | `src/Director.cpp` | 391 |
| `Resettle` | Method | `src/Director.cpp` | 460 |
| `RestoreOf` | Method | `src/Director.cpp` | 376 |

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

1. `context({name: "CancelPicking"})` — see callers and callees
2. `query({search_query: "cluster_471"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
