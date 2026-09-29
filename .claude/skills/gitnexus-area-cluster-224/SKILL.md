---
name: gitnexus-area-cluster-224
description: "Skill for the Cluster_224 area of fo4-silhouette. 8 symbols across 1 files."
---

# Cluster_224

8 symbols | 1 files | Cohesion: 58%

## When to Use

- Working with code in `src/`
- Understanding how Admit, Configure, Dressed work
- Modifying cluster_224-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `src/Director.cpp` | RefitOn, Admit, Configure, Dressed, LeaveAlone (+3) |

## Entry Points

Start here when exploring this area:

- **`Admit`** (Method) — `src/Director.cpp:225`
- **`Configure`** (Method) — `src/Director.cpp:127`
- **`Dressed`** (Method) — `src/Director.cpp:318`
- **`LeaveAlone`** (Method) — `src/Director.cpp:271`
- **`ReconcileRefit`** (Method) — `src/Director.cpp:873`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `Admit` | Method | `src/Director.cpp` | 225 |
| `Configure` | Method | `src/Director.cpp` | 127 |
| `Dressed` | Method | `src/Director.cpp` | 318 |
| `LeaveAlone` | Method | `src/Director.cpp` | 271 |
| `ReconcileRefit` | Method | `src/Director.cpp` | 873 |
| `Seen` | Method | `src/Director.cpp` | 290 |
| `SetSwitch` | Method | `src/Director.cpp` | 150 |
| `RefitOn` | Function | `src/Director.cpp` | 39 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `PickerKeep → PresetNamedBy` | cross_community | 7 |
| `PickerStart → PresetNamedBy` | cross_community | 7 |
| `PickerKeep → RefitOn` | cross_community | 6 |
| `PickerStart → RefitOn` | cross_community | 6 |
| `Done → PresetNamedBy` | cross_community | 6 |
| `Done → RefitOn` | cross_community | 5 |
| `Dressed → PresetNamedBy` | cross_community | 5 |
| `Seen → PresetNamedBy` | cross_community | 5 |
| `Dressed → RefitOn` | intra_community | 4 |
| `Seen → RefitOn` | intra_community | 4 |

## How to Explore

1. `context({name: "Admit"})` — see callers and callees
2. `query({search_query: "cluster_224"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
