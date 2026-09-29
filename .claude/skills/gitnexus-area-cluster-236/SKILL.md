---
name: gitnexus-area-cluster-236
description: "Skill for the Cluster_236 area of fo4-silhouette. 12 symbols across 1 files."
---

# Cluster_236

12 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `src/`
- Understanding how LaneOf, PickerStart, Ref work
- Modifying cluster_236-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `src/Papyrus.cpp` | LaneOf, PickerStart, Ref, RequestAdopt, RequestPreset (+7) |

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `LaneOf` | Function | `src/Papyrus.cpp` | 38 |
| `PickerStart` | Function | `src/Papyrus.cpp` | 308 |
| `Ref` | Function | `src/Papyrus.cpp` | 34 |
| `RequestAdopt` | Function | `src/Papyrus.cpp` | 372 |
| `RequestPreset` | Function | `src/Papyrus.cpp` | 338 |
| `RequestReapply` | Function | `src/Papyrus.cpp` | 363 |
| `RequestRegenerate` | Function | `src/Papyrus.cpp` | 346 |
| `RequestReset` | Function | `src/Papyrus.cpp` | 356 |
| `Request` | Function | `src/Papyrus.cpp` | 323 |
| `Said` | Function | `src/Papyrus.cpp` | 205 |
| `SetError` | Function | `src/Papyrus.cpp` | 26 |
| `Shapeable` | Function | `src/Papyrus.cpp` | 282 |

## How to Explore

1. `context({name: "LaneOf"})` — see callers and callees
2. `query({search_query: "cluster_236"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
