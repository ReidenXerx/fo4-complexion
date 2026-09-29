---
name: gitnexus-area-pool
description: "Skill for the Pool area of fo4-silhouette. 30 symbols across 9 files."
---

# Pool

30 symbols | 9 files | Cohesion: 87%

## When to Use

- Working with code in `tools/`
- Understanding how check, main, archetypes_of work
- Modifying pool-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tools/pool/generate.py` | check, generate, main, preset_xml, sheets (+2) |
| `tools/pool/mesh.py` | build, name_at, __init__, string32, string8 (+1) |
| `tools/pool/factions.py` | archetypes_of, build, check, main |
| `tools/pool/measure.py` | measure, hull, over, section |
| `tools/tests/support.py` | bodies_missing, game_data, needs_data |
| `tools/pool/characters.py` | check, main |
| `tools/tests/test_pool.py` | test_every_record_is_where_it_was, test_every_body_measures_as_its_tier |
| `tools/pool/render.py` | render_sheet |
| `tools/tests/test_factions.py` | test_every_body_measures_as_its_tier_and_every_faction_is_there |

## Entry Points

Start here when exploring this area:

- **`check`** (Function) — `tools/pool/characters.py:316`
- **`main`** (Function) — `tools/pool/characters.py:332`
- **`archetypes_of`** (Function) — `tools/pool/factions.py:173`
- **`build`** (Function) — `tools/pool/factions.py:188`
- **`check`** (Function) — `tools/pool/factions.py:221`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `check` | Function | `tools/pool/characters.py` | 316 |
| `main` | Function | `tools/pool/characters.py` | 332 |
| `archetypes_of` | Function | `tools/pool/factions.py` | 173 |
| `build` | Function | `tools/pool/factions.py` | 188 |
| `check` | Function | `tools/pool/factions.py` | 221 |
| `main` | Function | `tools/pool/factions.py` | 247 |
| `check` | Function | `tools/pool/generate.py` | 147 |
| `generate` | Function | `tools/pool/generate.py` | 76 |
| `main` | Function | `tools/pool/generate.py` | 175 |
| `preset_xml` | Function | `tools/pool/generate.py` | 115 |
| `sheets` | Function | `tools/pool/generate.py` | 166 |
| `slider_names` | Function | `tools/pool/generate.py` | 106 |
| `tier_of` | Function | `tools/pool/generate.py` | 54 |
| `measure` | Function | `tools/pool/measure.py` | 61 |
| `render_sheet` | Function | `tools/pool/render.py` | 41 |
| `bodies_missing` | Function | `tools/tests/support.py` | 52 |
| `game_data` | Function | `tools/tests/support.py` | 42 |
| `needs_data` | Function | `tools/tests/support.py` | 68 |
| `name_at` | Function | `tools/pool/mesh.py` | 69 |
| `hull` | Function | `tools/pool/measure.py` | 5 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → Perimeter` | cross_community | 7 |
| `Main → Pts` | cross_community | 7 |
| `Main → Cross` | cross_community | 7 |
| `Main → Norm_path` | cross_community | 6 |
| `Main → Perimeter` | cross_community | 6 |
| `Main → Pts` | cross_community | 6 |
| `Main → Truthy` | cross_community | 5 |
| `Main → _fields` | cross_community | 5 |
| `Main → _zstring` | cross_community | 5 |
| `Main → Norm_path` | cross_community | 5 |

## How to Explore

1. `context({name: "check"})` — see callers and callees
2. `query({search_query: "pool"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
