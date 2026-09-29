---
name: gitnexus-area-cluster-219
description: "Skill for the Cluster_219 area of fo4-silhouette. 10 symbols across 2 files."
---

# Cluster_219

10 symbols | 2 files | Cohesion: 89%

## When to Use

- Working with code in `src/`
- Understanding how ParseCatalog, ParseManifest, FindRefit work
- Modifying cluster_219-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `src/Catalog.cpp` | ParseCatalog, ParseManifest, Ref, Refs, Sex (+4) |
| `src/Catalog.h` | FindRefit |

## Entry Points

Start here when exploring this area:

- **`ParseCatalog`** (Function) — `src/Catalog.cpp:372`
- **`ParseManifest`** (Function) — `src/Catalog.cpp:612`
- **`FindRefit`** (Method) — `src/Catalog.h:168`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ParseCatalog` | Function | `src/Catalog.cpp` | 372 |
| `ParseManifest` | Function | `src/Catalog.cpp` | 612 |
| `FindRefit` | Method | `src/Catalog.h` | 168 |
| `Ref` | Function | `src/Catalog.cpp` | 104 |
| `Refs` | Function | `src/Catalog.cpp` | 120 |
| `Sex` | Function | `src/Catalog.cpp` | 83 |
| `Str` | Function | `src/Catalog.cpp` | 43 |
| `Strings` | Function | `src/Catalog.cpp` | 95 |
| `Unsigned` | Function | `src/Catalog.cpp` | 75 |
| `Words` | Function | `src/Catalog.cpp` | 250 |

## How to Explore

1. `context({name: "ParseCatalog"})` — see callers and callees
2. `query({search_query: "cluster_219"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
