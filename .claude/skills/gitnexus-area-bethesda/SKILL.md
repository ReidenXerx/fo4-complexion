---
name: gitnexus-area-bethesda
description: "Skill for the Bethesda area of fo4-silhouette. 651 symbols across 125 files."
---

# Bethesda

651 symbols | 125 files | Cohesion: 74%

## When to Use

- Working with code in `extern/`
- Understanding how calloc, free, aligned_alloc work
- Modifying bethesda-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/FormComponents.h` | BGSMenuDisplayObject, BSISoundCategory, TESDescription, TESFullName, TESReactionForm (+56) |
| `extern/CommonLibF4RD/CommonLibF4/include/RE/Bethesda/TESForms.h` | BGSMessage, BGSPerk, BGSSoundCategory, EffectSetting, TESClass (+34) |
| `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/TESForms.h` | BGSCollisionLayer, BGSColorForm, BGSConstructibleObject, BGSKeyword, BGSLensFlare (+33) |
| `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/TESBoundObjects.h` | TESObject, BGSMovableStatic, TESObjectARMA, TESObjectSTAT, BGSAddonNode (+18) |
| `extern/CommonLibF4RD/CommonLibF4/include/RE/Bethesda/TESBoundObjects.h` | BGSMovableStatic, TESObjectARMA, TESObjectSTAT, BGSComponent, BGSNote (+18) |
| `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/BSTArray.h` | assign, decay_iterator, insert, operator=, resize (+17) |
| `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/BSTHashMap.h` | clear, do_erase, empty, get_entries, get_entry_for (+16) |
| `extern/CommonLibF4RD/CommonLibF4/include/RE/Bethesda/BSTHashMap.h` | clear, do_erase, empty, get_entries, get_entry_for (+16) |
| `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/IMenu.h` | InventoryUserUIInterface, ContainerMenuBase, ExamineMenu, GameMenuBase, HolotapeMenu (+13) |
| `extern/CommonLibF4RD/CommonLibF4/include/RE/Bethesda/BSTArray.h` | BSTArray, BSTArray, begin, end, erase (+13) |

## Entry Points

Start here when exploring this area:

- **`calloc`** (Function) — `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/MemoryManager.h:289`
- **`free`** (Function) — `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/MemoryManager.h:316`
- **`aligned_alloc`** (Function) — `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/MemoryManager.h:277`
- **`aligned_free`** (Function) — `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/MemoryManager.h:322`
- **`malloc`** (Function) — `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/MemoryManager.h:265`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ActorValueInfo` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/ActorValueInfo.h` | 203 |
| `BGSHeadPart` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/BGSHeadPart.h` | 10 |
| `Mod` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/BGSMod.h` | 17 |
| `Container` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/BGSMod.h` | 102 |
| `Item` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/BGSMod.h` | 219 |
| `BGSStoryManagerBranchNode` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/BGSStoryManagerTreeForm.h` | 199 |
| `BGSStoryManagerNodeBase` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/BGSStoryManagerTreeForm.h` | 179 |
| `BGSStoryManagerTreeForm` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/BGSStoryManagerTreeForm.h` | 20 |
| `TESQuest` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/BGSStoryManagerTreeForm.h` | 118 |
| `BGSMenuDisplayObject` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/FormComponents.h` | 32 |
| `BSISoundCategory` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/FormComponents.h` | 301 |
| `TESDescription` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/FormComponents.h` | 44 |
| `TESFullName` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/FormComponents.h` | 46 |
| `TESReactionForm` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/FormComponents.h` | 60 |
| `TESTexture` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/FormComponents.h` | 18 |
| `BSNavmesh` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/NavMesh.h` | 118 |
| `NavMesh` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/NavMesh.h` | 163 |
| `TESObject` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/TESBoundObjects.h` | 31 |
| `TESFaction` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/TESFaction.h` | 87 |
| `BGSCollisionLayer` | Class | `extern/CommonLibF4/CommonLibF4/include/RE/Bethesda/TESForms.h` | 172 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Operator= → Capacity` | cross_community | 8 |
| `Operator= → Size` | cross_community | 8 |
| `AddExtra → Allocate` | cross_community | 7 |
| `AddExtra → GetSingleton` | cross_community | 7 |
| `Operator= → Decay_iterator` | cross_community | 7 |
| `Operator= → Cbegin` | intra_community | 4 |
| `Operator= → Size` | intra_community | 4 |
| `Operator= → Allocate` | intra_community | 4 |
| `Operator= → Get_entries` | intra_community | 4 |
| `BSTArray → Size` | cross_community | 4 |

## How to Explore

1. `context({name: "calloc"})` — see callers and callees
2. `query({search_query: "bethesda"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
