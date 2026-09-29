---
name: gitnexus-area-tools
description: "Skill for the Tools area of fo4-silhouette. 139 symbols across 20 files."
---

# Tools

139 symbols | 20 files | Cohesion: 63%

## When to Use

- Working with code in `tools/`
- Understanding how is_refit, body_values, catalog_presets work
- Modifying tools-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tools/silhouette_gen.py` | body_values, catalog_presets, describe, fmt, is_zeroed (+32) |
| `tools/catalog.py` | is_refit, check, at, fail, need (+17) |
| `tools/verify_bodygen.py` | check_lines, line_kind, fixed_values, main, sets_nothing (+11) |
| `tools/base_body.py` | build_choice, locate, measure, norm_path, output_of (+5) |
| `tools/rules.py` | distribute_races, encodable, has_word, load, validate (+4) |
| `tools/plugin_forms.py` | resolve, _fields, _zstring, editor_ids, header (+3) |
| `tools/audit_builds.py` | main, fit, judge, matches, zeroes (+1) |
| `tools/make_esp.py` | _records, check, main, field, quest_fields (+1) |
| `tools/tests/test_rules.py` | refusal, test_an_emptied_race_list_is_refused_not_read_as_the_default, test_load_refuses_an_emptied_race_list_in_the_file, test_a_light_plugin_keeps_three_digits, test_the_player_and_both_dummies_as_form_key_writes_them |
| `tools/nif_geometry.py` | read_shapes, export_string, sized_string, take |

## Entry Points

Start here when exploring this area:

- **`is_refit`** (Function) — `tools/catalog.py:49`
- **`body_values`** (Function) — `tools/silhouette_gen.py:523`
- **`catalog_presets`** (Function) — `tools/silhouette_gen.py:1411`
- **`describe`** (Function) — `tools/silhouette_gen.py:679`
- **`fmt`** (Function) — `tools/silhouette_gen.py:714`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `is_refit` | Function | `tools/catalog.py` | 49 |
| `body_values` | Function | `tools/silhouette_gen.py` | 523 |
| `catalog_presets` | Function | `tools/silhouette_gen.py` | 1411 |
| `describe` | Function | `tools/silhouette_gen.py` | 679 |
| `fmt` | Function | `tools/silhouette_gen.py` | 714 |
| `is_zeroed` | Function | `tools/silhouette_gen.py` | 1471 |
| `main` | Function | `tools/silhouette_gen.py` | 1661 |
| `resolve_presets` | Function | `tools/silhouette_gen.py` | 1892 |
| `manifest_templates` | Function | `tools/silhouette_gen.py` | 1478 |
| `marker_moves` | Function | `tools/silhouette_gen.py` | 508 |
| `merge_characters` | Function | `tools/silhouette_gen.py` | 565 |
| `morph_values` | Function | `tools/silhouette_gen.py` | 721 |
| `never_in_body` | Function | `tools/silhouette_gen.py` | 197 |
| `random_line_names` | Function | `tools/silhouette_gen.py` | 631 |
| `refit_sets` | Function | `tools/silhouette_gen.py` | 1445 |
| `target_values` | Function | `tools/silhouette_gen.py` | 641 |
| `template_name` | Function | `tools/silhouette_gen.py` | 637 |
| `template_text` | Function | `tools/silhouette_gen.py` | 648 |
| `write_manifest` | Function | `tools/silhouette_gen.py` | 1617 |
| `write_papyrus` | Function | `tools/silhouette_gen.py` | 1006 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Build → _fields` | cross_community | 6 |
| `Build → _zstring` | cross_community | 6 |
| `Main → Norm_path` | cross_community | 6 |
| `Main → Truthy` | cross_community | 5 |
| `Main → Fail` | cross_community | 5 |
| `Main → _fields` | cross_community | 5 |
| `Main → _zstring` | cross_community | 5 |
| `Main → Norm_path` | cross_community | 5 |
| `Check_lines → _fields` | cross_community | 5 |
| `Check_lines → _zstring` | cross_community | 5 |

## How to Explore

1. `context({name: "is_refit"})` — see callers and callees
2. `query({search_query: "tools"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
