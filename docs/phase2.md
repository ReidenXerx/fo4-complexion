# Phase 2 — the Silhouette plugin

What the F4SE plugin adds to Phase 1, how it does it, and why it is shaped this way. The decisions
behind it are S-18 to S-25 in [decisions.md](decisions.md); this is the map.

## What stays as it is

LooksMenu's BodyGen keeps doing **random distribution** from the files the generator writes. It
applies a body when LooksMenu first sees an NPC, before anyone looks at them, and it keeps the roll
in its co-save. Nothing the plugin could do would be faster: the plugin cannot reach LooksMenu's
morph store except through Papyrus (below), which arrives a poll later. So the plugin never
re-does what BodyGen already does well. It adds only what a file cannot express:

| | Why BodyGen cannot | What the plugin does |
| --- | --- | --- |
| Rules by NPC **name** and by **faction** | a morphs.ini line names plugins, form ids and races, nothing else | reads the name and factions when an NPC initialises and overrides BodyGen's roll where OBody's priority says the rule wins |
| **Blacklist by name** | same | marks the NPC with a stored morph that moves nothing, so BodyGen never rolls them again |
| **ORefit** while clothed | needs equip events | follows TESEquipEvent and switches the NPC between the clothed and naked values |
| **NPC picker** (S-22) | needs aim and a live preview | hotkeys and an MCM page, no custom menu |
| **API and events** | runtime | Papyrus functions shaped like OBody's, and events for other mods |

Variety is NOT on this list: BodyGen can roll it. A template entry `Morph@low:high` gives every NPC
who rolls that template their own value, at load, with nothing at run time — S-17 does the women's
genital shapes that way and S-21 the nipples (both sexes) and the men's ball size.

## How the pieces talk

```
LooksMenu BodyGen ──(on NPC load)──▶ random body + marker, stored in LooksMenu's co-save
        ▲
        │ BodyGen.SetMorph / GetMorphs / RemoveMorphsByKeyword / UpdateMorphs   (Papyrus only)
        │
Silhouette:Bridge  (Papyrus, on Silhouette.esp's quest, ONE timer)
        │   polls:   Silhouette:Plugin.NextOrder()       reports: NoteMarker/NoteRead, OrderDone()
        ▼
Silhouette.dll  (F4SE, CommonLibF4 OG)
    Catalog   catalog.json + manifests/<stamp>.json, written by silhouette_gen.py
    Rules     OBody's priority, for the rules only the runtime can see
    Registry  co-save: who we assigned, why, with which stamp; ORefit state; variety applied
    Sinks     TESInitScriptEvent (who appeared), TESEquipEvent (who dressed or undressed)
```

**The plugin never calls into the Papyrus VM** — dispatching into it from an F4SE task crashed
Rapport twice (`DispatchMethodCallImpl`, the per-thread scrap heap). It decides and queues; the
bridge asks on its own thread, on its one timer, and does every LooksMenu call. The NPC picker's
hotkeys call the bridge directly (MCM runs them on a VM thread), so a preview is instant.

LooksMenu offers other plugins no C++ interface (its `exports.def` has only F4SE's two entry
points and its message handler answers F4SE alone), so Papyrus is the only door there is.

## The catalog: the generator stays the compiler

The generator already measures everything that makes a body right: which presets fit, what is
baked, what is a runtime state (S-16). The plugin does not re-derive any of it. `--write` adds
`F4SE/Plugins/Silhouette/catalog.json`:

- per sex: every preset that fits (name, marker, final values, fit, family, zeroed, in the random
  pool, in the menu), the player default, the body's morph names;
- the compiled rules: what BodyGen got (form id, plugin, race, blacklists — the plugin needs them
  to know when NOT to override) and what only the runtime can do (names, factions, name blacklists);
- the ORefit sets, as data, so tuning them never needs a compiler.

`manifests/<stamp>.json` (S-12) stays the record of what each build wrote, and the plugin reads
them to name the preset behind any marker, including markers an older build wrote.

## ORefit in Fallout 4 (S-20)

OBody layers the clothed preset under a second key ("OClothe") and Skyrim's RaceMenu **adds**
keys. LooksMenu takes the **maximum** over keys (`UserValues::GetEffectiveValue` is
`std::max_element`), so a refit that lowers a value cannot live under its own key. The plugin
therefore writes the clothed values into Silhouette's own (unkeyed) layer while an NPC is dressed,
and puts back what was there when they undress — from a **snapshot** the bridge took of exactly
those morphs before the refit, kept in the plugin's co-save. Not from the preset: an NPC's values
are their preset plus their own rolled variety (S-17, S-21), or a picker choice, or a hand edit, and
only a snapshot knows which.

Clothed, as OBody decides it and in Fallout 4's slots: something in **BODY (33)**, **[U] Torso
(36)** or **[A] Torso (41)** that is not blacklisted, or any force-refit item (both lists in
`Silhouette_presetDistributionConfig.json`, OBody's keys). A refit comes from, in order: the
outfit's own refit preset, `<Preset>-Refit`, `Female-Refit`/`Male-Refit`, else the built-in set for
this body (CBBE: breasts pulled together and lifted, nipples flattened so they do not poke through).

## Variety (S-17, S-21)

BodyGen rolls it, per NPC, at load: a template entry `Morph@low:high` gives each NPC who rolls the
template a value of their own, stored with the rest of their body. The ranges are data
(`tools/genital_shapes.json` for S-17, `tools/variety.json` for S-21). As OBody's variety does under
its key, a range replaces the preset's own value for that morph.

- Women: nipples (the CBBE nipple sliders, S-21) and the genital SHAPE sliders of the anatomy body
  (S-17). Never an opening (VaginaPenetrate, AnusPenetrate, VaginaSpread, ButtcheeksSpread: runtime
  states, S-16) and never AnusBack (it moves where the anus is).
- Men (owner, S-21): nipples and ball size only. Shaft length and width stay as built: animations
  aim the penis bones, and the anatomy body's physics is fitted to the shaft's current width.

## The NPC picker (S-22, owner)

Aim at an NPC, press **Pick** (MCM hotkey): they become the target. **Next / Previous** cycle every
preset that fits their body live, with the name shown; **Keep** records it (it then survives, like
a rule); **Cancel** puts back exactly what they had. MCM > Silhouette > *The NPC in your sights*
shows the target and a dropdown of every preset, with Apply, Back to random, and Which body.

## Runtime rules (S-23)

OBody's priority, highest first: per-NPC blacklist (name or form id) → per-NPC preset (form id or
name) → plugin and race blacklists → faction → plugin → race → random. BodyGen already carries
every tier it can name; the plugin sees an NPC initialise and acts only where a NAME or FACTION
tier is the winner: it assigns that preset (the bridge replaces BodyGen's roll), or, for a name
blacklist, leaves the NPC bare with a stored blacklist marker so BodyGen never rolls them again. The
co-save remembers what it assigned and why (S-25), so a rule is applied once, and again only when
the rule itself changes.

## API and events (S-24)

`Silhouette:API` (global functions, OBody's names): `IsReady`, `GetPresetAssignedToActor`,
`GetAllPossiblePresets`, `AssignPresetToActor`/`ApplyPresetByName`, `GenActor`,
`ResetActorMorphs`, `ReapplyActorMorphs`, `SetORefit`/`IsORefitEnabled`/`IsORefitApplied`,
`SetNippleRand`, `SetGenitalRand`. Events, raised by the bridge (custom events on
`Silhouette:Bridge`): `OnActorGenerated(Actor, String preset)`, `OnActorNaked(Actor)`,
`OnActorRemovingClothes(Actor)`, `OnORefitChanged(Actor, Bool applied)`.

## Failure behaviour

- No DLL, or the wrong runtime: Phase 1 is untouched — BodyGen still distributes, the player picker
  still works (S-9). The MCM says the plugin is missing instead of offering dead buttons.
- A catalog missing or from another build than the BodyGen files: the plugin refuses to act on
  rules and ORefit (a stamp mismatch means values it cannot trust) and says so in its log and MCM.
- Every order the bridge cannot complete is reported back, never dropped silently.
