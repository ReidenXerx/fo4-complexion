# OBody NG → Silhouette

What OBody NG does in Skyrim, read from its source (Aietos/OBody-NG, GPL-3), and where each piece
lands in Fallout 4. **Phase 1** is the generator (LooksMenu BodyGen files, no runtime code);
**Phase 2** is an F4SE plugin. v1 = OBody parity, all four areas (decision S-3).

"BodyGen can express it" means LooksMenu's own BodyGen does the work at run time from the files
Silhouette writes — see [bodygen-format.md](bodygen-format.md) for the exact semantics.

## Distribution

| OBody NG | Silhouette | Phase |
| --- | --- | --- |
| Random preset per NPC on first load (`TESInitScriptEvent`, 3D loaded, `ActorTypeNPC`, not a child) | `All\|Female\|HumanRace` / `All\|Male\|HumanRace` pools. Children are `ChildRace`, so naming `HumanRace` excludes them. | **1 — done** |
| Female/male pools from every BodySlide preset | Every preset **measured** against the installed `.tri`: presets that cannot move this body are left out; partial fits count only for the declared family | **1 — done** |
| Preset kept for the save (co-save `ActorRegistry`) | LooksMenu stores the rolled morphs in its co-save. A marker morph named after the template makes every roll permanent — without it an all-zero roll re-rolls on each load | **1 — done** |
| Renaming/removing a preset never breaks a save (`PresetNameIndexMap`) | Stored values do not depend on preset files. The marker records the preset *name*, so Phase 2 can re-derive an NPC's values after a preset is edited | 1 (values) / **2** (re-derive) |
| — (Skyrim bodies are built zeroed by convention) | **The base body is measured** on every run: a baked-in preset is named exactly, with the BodySlide body + zeroed preset to rebuild with (S-5). `--compensate` writes relative templates for installs that cannot be rebuilt | **1 — done** |
| Player not randomised (event timing; no explicit rule) | Explicit: `Fallout4.esm\|7\|Female` / `\|Male` name one template each — the most average preset (S-7, S-10) | **1 — done** |

## Rules, in OBody's priority order

OBody resolves faction → npcFormID → npc name → npcPlugin → race → random. In BodyGen, priority is
**line order**: the random pool first, then each rule below it, most important last.

| OBody key | BodyGen | Phase |
| --- | --- | --- |
| `raceFemale` / `raceMale` | `All\|Female\|<Race>=...` | 1b |
| `npcPluginFemale` / `npcPluginMale` | `<Plugin>\|All\|Female\|HumanRace=...` | 1b |
| `npcFormID` | `<Plugin>\|<FormID>=...` (no load-order byte; ESL supported; leveled lists expand) | 1b |
| `npc` (by name) | Not in BodyGen. Resolved at **build time** by reading the plugins' `NPC_` records (`FULL` name → FormID), then written as FormID lines | 1b |
| `factionFemale` / `factionMale` | Not in BodyGen. Build time: `NPC_` `SNAM` faction list → FormID lines. Run-time faction changes need Phase 2 | 1b / 2 |
| `blacklistedNpcs`, `…FormID`, `…PluginFemale/Male`, `blacklistedRacesFemale/Male` | A dedicated line whose only template sets nothing. Safe as a blacklist **only** because every option on that line is zero (see "A template that sets nothing re-rolls" in bodygen-format.md) | 1b |
| `blacklistedPresetsFromRandomDistribution` | Left out of the pool at generation. Zeroed presets are left out by default, as OBody's shipped config does | **1 — zeroed done**, list 1b |
| `blacklistedPresetsShowInOBodyMenu` | Picker option | 2 |
| `obody_includes/*.json` (only `npc`, `npcFormID`, `npcPluginFemale/Male`; alphabetical, later wins) | `includes/*.json` read by the generator, same keys, same order | 1b |
| `blacklistedRaces… "ElderRace"` default | No elder race in FO4. Ghouls (`GhoulRace`) have their own body meshes and are simply not named | — |

## In-game picker (OBody menu)

**For the player: done without a plugin** (S-7, S-9). MCM > Silhouette lists every preset that fits
the character's body per sex; *Apply*, *Back to the default* and *Which body do I have?* are
`CallGlobalFunction` buttons on the generated `Silhouette:Player` script, which drives LooksMenu's
Papyrus `BodyGen` (`SetMorph`, `GetMorph`, `GetMorphs`, `GetKeywords`, `RemoveMorphsByName`,
`RemoveMorphsByKeyword`, `RemoveAllMorphs`, `RegenerateMorphs`, `UpdateMorphs`, `ClearAll` —
`PapyrusBodyGen.cpp`). `GetMorphs` lists an actor's morph names, so the marker can be read back.

**For NPCs** (target an NPC, preview, apply, reset): Phase 2 — it needs a way to aim at an NPC and a
live preview, which is plugin work.

## ORefit, nipple and genital variety

| OBody NG | Silhouette | Phase |
| --- | --- | --- |
| ORefit: a hand-tuned CBBE-3BA slider list applied while clothed | Re-authored for FO4 CBBE's 84 morphs — the Skyrim names do not exist here. Needs equip events: **Phase 2**. Must write the **final** value under one key: LooksMenu combines keyed values by **max**, so a refit that *lowers* a value cannot be layered under its own keyword | 2 |
| Nipple randomisation (AreolaSize, NippleSize, … with chances) | BodyGen can already express it: a per-morph range (`Morph@low:high`) and chance by repetition of `\|` alternatives — added on top of the preset's own value, minus what is baked | 1b |
| Genital randomisation (SOS/SAM sliders) | BodyTalk's own genital sliders (`Balls`, `BTBallSize`, …) in the same way | 1b |

## Events and API

| OBody NG | Silhouette | Phase |
| --- | --- | --- |
| `OnActorGenerated`, `OnActorNaked`, `OnActorRemovingClothes` | F4SE plugin events, consumable by Rapport / Chemistry | 2 |
| Papyrus `OBodyNative`: `GenActor`, `ApplyPresetByName`, `GetAllPossiblePresets`, `GetPresetAssignedToActor`, `AssignPresetToActor`, `ResetActorOBodyMorphs`, `ReapplyActorOBodyMorphs`, `SetORefit`, `SetNippleRand`, `SetGenitalRand`, database sizes, event registration | Same surface, `Silhouette` naming. `GetPresetAssignedToActor` can read the marker morph — including for NPCs rolled in Phase 1. `GenActor` maps onto LooksMenu's `RegenerateMorphs` | 2 |
| `SetPerformanceMode`, `SetRespectfulMorphApplication`, `SetLegacyStorageUtilUsageEnabled`, `SetDistributionKey` | Skyrim/RaceMenu specifics with no FO4 counterpart | — |
