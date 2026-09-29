---
name: gitnexus-area-tests
description: "Skill for the Tests area of fo4-silhouette. 231 symbols across 25 files."
---

# Tests

231 symbols | 25 files | Cohesion: 78%

## When to Use

- Working with code in `tools/`
- Understanding how KindOf, ParseCatalog, ParseFilesHeader work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tests/main.cpp` | BaseCatalog, Cat, Check, CheckData, Drain (+40) |
| `tools/tests/test_verify_damage.py` | c10_current_manifest_value_a_string, c11_old_manifest_value_a_bool, c1_current_manifest_templates_a_list, c2_current_manifest_entry_a_string, c3_old_manifest_templates_a_list (+33) |
| `tools/tests/test_markers.py` | markers, suffixed, write_manifest, history, setUp (+32) |
| `tools/silhouette_gen.py` | refuse_foreign_config, first_difference, same_bodies, judge_base, manifest_files (+8) |
| `tools/tests/test_generator_main.py` | test_a_catalog_whose_manifest_is_nowhere_is_said, test_no_catalog_at_all_is_nothing_to_say, test_one_preset_under_two_markers_is_said_and_the_first_compared, test_the_verifier_reads_the_same_folders, files_under (+5) |
| `tools/tests/test_shipped_config.py` | refusal, test_a_config_in_the_root_when_only_the_defaults_were_compiled, test_a_copy_of_the_compiled_config, test_a_root_without_a_config_takes_the_compiled_one, test_another_config_in_the_root_is_refused_not_replaced (+4) |
| `tools/tests/test_judge_base.py` | measured, test_a_base_measured_zeroed_or_unknown_is_left_as_it_is, test_a_body_slider_baked_in_keeps_it_a_preset, test_a_value_below_what_a_file_can_say_is_not_baked, test_describe_says_what_the_build_owns (+4) |
| `tools/tests/test_picker_parts.py` | picker, written, test_locate_and_at_count_each_part_from_its_first_entry, test_no_generated_array_is_built_past_the_limit, test_the_part_count_follows_the_longer_list (+3) |
| `tools/tests/test_make_esp.py` | check, test_an_esp_not_flagged_light_is_refused, test_an_esp_without_the_refit_keyword_is_refused_first, test_each_quest_and_list_is_required, test_the_phase_1_esp_is_refused (+3) |
| `src/Plan.h` | BodyFor, Draw, BodyHash, RefitFloors, RefitMarker (+2) |

## Entry Points

Start here when exploring this area:

- **`KindOf`** (Function) — `src/Catalog.h:21`
- **`ParseCatalog`** (Function) — `src/Catalog.h:196`
- **`ParseFilesHeader`** (Function) — `src/Catalog.h:215`
- **`BodyFor`** (Function) — `src/Plan.h:29`
- **`Draw`** (Function) — `src/Plan.h:21`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `Scratch` | Class | `tools/tests/support.py` | 112 |
| `KindOf` | Function | `src/Catalog.h` | 21 |
| `ParseCatalog` | Function | `src/Catalog.h` | 196 |
| `ParseFilesHeader` | Function | `src/Catalog.h` | 215 |
| `BodyFor` | Function | `src/Plan.h` | 29 |
| `Draw` | Function | `src/Plan.h` | 21 |
| `KeepInCoSave` | Function | `src/Registry.h` | 152 |
| `Decide` | Function | `src/Rules.h` | 41 |
| `CheckData` | Function | `tests/main.cpp` | 3019 |
| `DumpPresets` | Function | `tests/main.cpp` | 3660 |
| `TestInstalledPresets` | Function | `tests/main.cpp` | 3572 |
| `one` | Function | `tests/main.cpp` | 3619 |
| `Tri` | Function | `tests/main.cpp` | 3535 |
| `u16` | Function | `tests/main.cpp` | 3538 |
| `main` | Function | `tests/main.cpp` | 3691 |
| `c10_current_manifest_value_a_string` | Function | `tools/tests/test_verify_damage.py` | 233 |
| `c11_old_manifest_value_a_bool` | Function | `tools/tests/test_verify_damage.py` | 242 |
| `c1_current_manifest_templates_a_list` | Function | `tools/tests/test_verify_damage.py` | 161 |
| `c2_current_manifest_entry_a_string` | Function | `tools/tests/test_verify_damage.py` | 166 |
| `c3_old_manifest_templates_a_list` | Function | `tools/tests/test_verify_damage.py` | 172 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → Foreign` | cross_community | 4 |
| `Check_picker → Papyrus_unescape` | cross_community | 3 |

## How to Explore

1. `context({name: "KindOf"})` — see callers and callees
2. `query({search_query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
