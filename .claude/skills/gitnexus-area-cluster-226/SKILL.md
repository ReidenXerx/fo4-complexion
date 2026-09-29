---
name: gitnexus-area-cluster-226
description: "Skill for the Cluster_226 area of fo4-silhouette. 9 symbols across 1 files."
---

# Cluster_226

9 symbols | 1 files | Cohesion: 94%

## When to Use

- Working with code in `src/`
- Understanding how FindGlobalSource, SafeFormID, SafeFormType work
- Modifying cluster_226-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `src/EventSources.cpp` | FindGlobalSource, ReadI32, ReadName, ReadU32, SafeFormID (+4) |

## Entry Points

Start here when exploring this area:

- **`FindGlobalSource`** (Function) — `src/EventSources.cpp:301`
- **`SafeFormID`** (Function) — `src/EventSources.cpp:266`
- **`SafeFormType`** (Function) — `src/EventSources.cpp:279`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `FindGlobalSource` | Function | `src/EventSources.cpp` | 301 |
| `SafeFormID` | Function | `src/EventSources.cpp` | 266 |
| `SafeFormType` | Function | `src/EventSources.cpp` | 279 |
| `ReadI32` | Function | `src/EventSources.cpp` | 48 |
| `ReadName` | Function | `src/EventSources.cpp` | 53 |
| `ReadU32` | Function | `src/EventSources.cpp` | 43 |
| `SafeRead` | Function | `src/EventSources.cpp` | 10 |
| `SinkEventType` | Function | `src/EventSources.cpp` | 88 |
| `TypeName` | Function | `src/EventSources.cpp` | 68 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `SafeFormID → SafeRead` | intra_community | 4 |
| `SafeFormType → SafeRead` | intra_community | 4 |

## How to Explore

1. `context({name: "FindGlobalSource"})` — see callers and callees
2. `query({search_query: "cluster_226"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
