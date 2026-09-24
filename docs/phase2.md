# Phase 2 — the Silhouette plugin

What the F4SE plugin adds to Phase 1, how it does it, and why it is shaped this way. The decisions
behind it are S-18 to S-29 and S-40 to S-62 in [decisions.md](decisions.md); this is the map. The first
in-game session follows [phase2-test-plan.md](phase2-test-plan.md).

## What stays as it is

LooksMenu's BodyGen keeps doing **random distribution** from the files the generator writes. It
applies a body when LooksMenu first sees an NPC, before anyone looks at them, and it keeps the roll
in its co-save. Nothing the plugin could do would be faster: the plugin cannot reach LooksMenu's
morph store except through Papyrus (below), which arrives a poll later. So the plugin never
re-does what BodyGen already does well. It adds only what a file cannot express:

| | Why BodyGen cannot | What the plugin does |
| --- | --- | --- |
| Rules by NPC **name** and by **faction** | a morphs.ini line names plugins, form ids and races, nothing else | reads the record's name and factions when an NPC loads and replaces BodyGen's roll where OBody's priority says the rule wins |
| **Blacklist by name** | same | leaves the NPC bare with a stored morph that moves nothing, so BodyGen never rolls them again |
| **ORefit** while clothed | needs equip events | follows TESEquipEvent and puts a clothed shape on, or takes it off, under a keyword of its own |
| **NPC picker** (S-22) | needs aim and a live preview | hotkeys and an MCM page, no custom menu |
| **API and events** | runtime | Papyrus functions shaped like OBody's, and events for other mods |
| **Touch-up** (S-29, S-44) | a file rolls only new NPCs | takes the shaft out of bodies an older build gave, and adds the variety a body lacks |

Variety is NOT on this list: BodyGen can roll it. A template entry `Morph@low:high` gives every NPC
who rolls that template their own value, at load, with nothing at run time — S-17 does the women's
genital shapes that way and S-21 the nipples (both sexes) and the men's ball size.

## How the pieces talk

```
LooksMenu BodyGen ──(on NPC load)──▶ random body + marker, stored in LooksMenu's co-save
        ▲
        │ BodyGen.GetMorphs / GetMorph / SetMorph / RemoveMorphsByKeyword / RegenerateMorphs /
        │ UpdateMorphs   (Papyrus only)
        │
Silhouette:Bridge  (Papyrus, Silhouette.esp's quest 0x802, ONE timer, drains on a stack of its own)
        │   polls:   Silhouette:DLL.NextOrder()     reports: NoteName/NoteMarker/NoteRead, OrderDone(),
        │            Silhouette:DLL.NextEvent()              OrderGone() (not in memory), OrderDefer() (AAF
        │                                                     has them busy), EventDone() (raised)
        ▼
Silhouette.dll  (F4SE, CommonLibF4 OG)
    Catalog   catalog.json + manifests/<stamp>.json, written by silhouette_gen.py
    Rules     OBody's priority, for the rules only the runtime can see
    Director  what each actor should have, against what LooksMenu holds; the orders; the lanes
    Registry  co-save: INTENT only -- who chose which body -- and a picking in progress
    Sinks     TESObjectLoadedEvent (who appeared), TESEquipEvent (who dressed or undressed),
              the crosshair (the picker's target); for 30 s after each load, the process lists
              too (after a load in a running game the first gave nobody, S-43)
```

**The plugin never calls into the Papyrus VM** — dispatching into it from an F4SE task crashed
Rapport twice (`DispatchMethodCallImpl`, the per-thread scrap heap). It decides and queues; the
bridge asks on its own thread, on its one timer, and does every LooksMenu call. The NPC picker's
hotkeys call the bridge directly (MCM runs them on a VM thread), so a preview is instant.

LooksMenu offers other plugins no C++ interface (its `exports.def` has only F4SE's two entry
points and its message handler answers F4SE alone), so Papyrus is the only door there is.

What an order does is fixed by a protocol number both sides state (`Silhouette:DLL.ProtocolVersion`
and `Silhouette:Bridge.Protocol`, now 3). A DLL and scripts of different releases refuse each other at
load instead of half-working -- and the bridge then sweeps refits off (S-54, below). The offline tests drive the whole director through a fake bridge that
does exactly what `RunOrder` does, against a fake LooksMenu that keeps the unkeyed layer, Silhouette's
keyword layer and another mod's, and shows their maximum — so what a body ends up looking like is what
is tested.

## Truth first (S-43)

The co-save and LooksMenu's own data are two files that can disagree: a save between two bridge calls,
a save made without the DLL, a non-persistent NPC LooksMenu forgets. So LooksMenu is the truth about
bodies, and the co-save holds only intent:

- the first order for an actor in a session is a **probe**: the markers she holds (body and refit) and
  the names of her morphs;
- a choice (a rule, the picker, the API, the name blacklist) is written to the co-save the moment it is
  made, not when the bridge finishes;
- after each probe the plugin makes the body match the intent — once a session — and every order is
  safe to repeat, so a save that lands in the middle of one is repaired by the next session's probe;
- a picked or API-given body carries a choice marker beside it in LooksMenu (S-51), so a save made
  without the DLL -- which F4SE keeps no co-save chunk for -- loses no choice: the probe rebuilds it;
- orders go in three lanes (S-55): urgent -- the picker, the NPC page, a refit coming off; normal --
  other mods' calls, the rules, a refit going on, touch-ups, first contact with someone dressing;
  background -- probes, the bulk buttons, the regeneration window. Order ids start at a random number
  each launch, and the bridge checks that an order still names its actor before it writes;
- work waits instead of being lost (S-56): an actor not in memory keeps their order until they are seen
  again, and a roll for someone in an AAF scene is tried again 10 seconds later, as long as it lasts.

Only actors Silhouette could shape are probed: the player, the character-creation dummies, creatures
and undistributed races never are.

## The catalog: the generator stays the compiler

The generator already measures everything that makes a body right: which presets fit, what is
baked, what is a runtime state (S-16) or the shaft (S-29). The plugin does not re-derive any of it.
`--write` adds `F4SE/Plugins/Silhouette/catalog.json`:

- per sex: every preset that fits (name, marker, final values, fit, family, zeroed, in the random
  pool, in the menu), the player default, the runtime states, what is never part of a body, and the
  variety ranges;
- the compiled rules: what BodyGen got (form id, plugin, race, blacklists — the plugin needs them
  to know when NOT to override) and what only the runtime can do (names, factions, name blacklists);
- ORefit: the clothed slots, OBody's outfit lists, the refit sets as floors, and what counts as heavy.

The rules come from `F4SE/Plugins/Silhouette/Silhouette_presetDistributionConfig.json`, which ships with
every key written out at its default (S-61) and the owner's tuning; the plugin never reads it. Edit it,
run the generator, and install what it writes: the change is in the catalog and the BodyGen lines, not in
the file. An empty `distributeRaces` is refused -- the default is ["HumanRace"].

Both BodyGen files and the catalog carry the same build, stamp and **rules hash**; the plugin refuses
a set whose three disagree (S-19). `manifests/<stamp>.json` (S-12) stays the record of what each build
wrote, and the plugin reads them to name the preset behind any marker, including markers an older
build wrote. `SilhouetteTests.exe --check <data>` runs the plugin's own parser on the generated files,
and the build and deploy scripts call it.

## ORefit (S-20, S-40 to S-42, S-48 to S-50, S-54)

LooksMenu shows the **maximum** over keyword layers (`UserValues::GetEffectiveValue` is
`std::max_element`). So the refit lives under Silhouette.esp's own keyword (0x803) as **floors**: while
dressed she has at least these values, and everything else is her own body. The clothed shape follows
every change to her body with nothing to keep in step, and undressing removes the layer: she is exactly
her own body again. A refit cannot lower anything — that is the price. Nothing about a refit is kept in
the co-save: a refit marker under the same keyword says which set is on (S-50: a whole number naming the
set and its floors, ODD under light clothes and EVEN under heavy ones), and 0.25 while one is being
written, so a probe knows. A build with new floors reaches a woman who never undresses; a refit already
right is not written again. Removing Silhouette.esp outright removes every refit, because LooksMenu drops
the values of a plugin that is not loaded; a missing or mismatched Silhouette.dll, or a refused catalog,
makes the bridge sweep refits off the people around the player instead (S-54). Loading an OLDER
Silhouette.esp, without the keyword, is the one way to lose this: LooksMenu checks only that the plugin's
name is loaded and files each value whose keyword form is missing under her own body -- every refit
becomes a body for good (S-27). The deploy and release scripts refuse such an esp; never roll back to one.

Clothed, as OBody decides it and in Fallout 4's slots: something in **BODY (33)**, **[U] Torso (36)**
or **[A] Torso (41)** that is not blacklisted, or any force-refit item (OBody's keys in
`Silhouette_presetDistributionConfig.json`). A refit comes from, in order: the outfit's own refit
preset, `<Preset>-Refit`, `Female-Refit`/`Male-Refit`, else the built-in set for this body (CBBE:
BreastsTogether at least 0.3 and PushUp at least 0.2).

**Heavy** clothes also flatten the nipples (NipBGone 1). Heavy is told by the item's NAME (S-48): the
config's lists first (`heavyOutfitsFormID`, `heavyOutfits`, `lightOutfitsFormID`, `lightOutfits`), then a
whole word or phrase of `heavyWords` -- by default armor, armour, armored, armoured, chest piece,
chestpiece, breastplate, chestplate, plate, cuirass, carapace, kevlar, torso, jacket, coat, trenchcoat,
overcoat, greatcoat, longcoat, raincoat, dreadcoat, battlecoat, duster, parka. Anything else is light: a
chest flattened under a shirt is worse than a nipple showing through a coat. Silhouette.log names each
heavy or listed item once, with its reason, and "Which body" names the item. A mod that raises nipples
(fo4-anatomy's arousal) holds them flat while the refit marker is even (S-49):
`Silhouette:API.IsHeavilyDressed`, or the marker read from LooksMenu directly.

What the flattening shows depends on the garment: NipBGone moves a nipple only where the outfit's own
mesh carries the slider. No vanilla or DLC heavy garment does (two light vanilla clothes carry it, and light
clothes are never flattened); mod outfits built with the refit sliders do (Mercenary's jackets, Clothing
Of The Commonwealth's coats). Names are read as the game shows them, so on
a localized Fallout4.esm no vanilla item is heavy until `heavyWords` holds that language's words.

Refit: every clothed woman of a distributed race who HAS a body — a Silhouette body, another BodyGen
mod's, a custom follower's, a hand-edited one — except anyone blacklisted, anyone reset this session,
anyone in power armour, and the player. A woman with no body gets nothing stored, so BodyGen can still
give her one.

## Variety (S-17, S-21) and the touch-up (S-29, S-44)

BodyGen rolls it, per NPC, at load: a template entry `Morph@low:high` gives each NPC who rolls the
template a value of their own, stored with the rest of their body. The ranges are data
(`tools/genital_shapes.json` for S-17, `tools/variety.json` for S-21). As OBody's variety does under
its key, a range replaces the preset's own value for that morph. A body the plugin gives draws the same
ranges from the reference id.

- Women: nipples (the CBBE nipple sliders, S-21) and the genital SHAPE sliders of the anatomy body
  (S-17). Never an opening (VaginaPenetrate, AnusPenetrate, VaginaSpread, ButtcheeksSpread: runtime
  states, S-16) and never AnusBack (it moves where the anus is).
- Men (owner, S-21): nipples and ball size only. Never the shaft (S-29): animations aim the penis bones,
  and the anatomy body's collision is fitted to the shaft's current width.

The first time the plugin sees a Silhouette body that lacks a range the current build rolls, it draws
just those; in the same order it zeroes any morph an older build put into that template that is never
part of a body now. Once per body and per build of what is wanted of it (its marker, the heals and the
ranges switched on): a later build's heal still reaches a body touched before, and a value the player
takes off afterwards stays off. Presence is read from her own layer, not another mod's keyed value. A
regeneration replaces the body and its variety with a new roll.

The player and the character-creation dummies are never rolled (S-45): they name a template of their
own with the default preset's values and marker and none of the ranges.

## The NPC picker (S-22, S-47)

Aim at an NPC, press **Pick** (MCM hotkey): they become the target. **Next / Previous** cycle every
preset that fits their body live, starting from the one they have, with the name shown and their own
variety kept; **Keep** records it (it then survives, like a rule, and is marked in LooksMenu); Keep on
the preset they had is a Cancel; **Cancel** puts back exactly what they had. A save made while picking
loads as a Cancel, one saved picking per NPC, and a decision made elsewhere ends a picking. MCM >
Silhouette > *The NPC in your sights* offers a dropdown of every preset, with Give them this preset, Back
to random, and Which body; the menu acts on the NPC last aimed at within 30 seconds of the crosshair
leaving them.

## Runtime rules (S-23)

OBody's priority, highest first: per-NPC blacklist (name or form id) → per-NPC preset (form id or
name) → plugin and race blacklists → faction → plugin → race → random. BodyGen already carries
every tier it can name; the plugin sees an NPC load and acts only where a NAME or FACTION tier is the
winner: it assigns that preset (the bridge replaces BodyGen's roll), or, for a name blacklist, leaves
the NPC bare with a stored blacklist marker so BodyGen never rolls them again. Names are the NPC
record's, as OBody reads them, so a rename at runtime changes nothing. A rule with several presets draws
one per person, and a met NPC keeps that draw while the rule still lists it (S-52); Back to random draws
from the rule again, onto another of its presets, and that draw is kept from then on (S-60). Race and faction
editor ids are found in the load order when the generator runs, in any case; a race no plugin defines
is refused there, since a rule naming it would match nobody.

## API and events (S-24, S-46)

`Silhouette:API` (global functions, OBody's names): `IsReady`, `GetPresetAssignedToActor`,
`GetAllPossiblePresets`, `AssignPresetToActor`/`ApplyPresetByName`, `GenActor`,
`ResetActorMorphs`/`ResetActorOBodyMorphs`, `ReapplyActorMorphs`/`ReapplyActorOBodyMorphs`,
`SetORefit`/`IsORefitEnabled`/`IsORefitApplied`, `IsHeavilyDressed`, `RefitMarkerValue`,
`SetNippleRand`, `SetGenitalRand`, `LastError`, `ShowStatus`. A call that would change a body answers
False, with LastError saying why, unless the plugin is ready and Silhouette.esp is there to carry it out.
`IsORefitApplied`, `IsHeavilyDressed` and `RefitMarkerValue` read LooksMenu, not the plugin. Reset leaves
someone bare and gives them a new body at the next load (S-53). Events, raised by the bridge as custom
events on `Silhouette:Bridge` and sent under the names the compiler gives them: `OnActorGenerated(Actor,
String preset)`, `OnActorNaked(Actor)`, `OnActorRemovingClothes(Actor)`, `OnORefitChanged(Actor, Bool
applied)`. A listener compiled against the decompiled base sources registers the mangled name
("silhouette:bridge_OnActorGenerated"); one compiled against the Creation Kit's sources, the plain one. A
call that changes a body returns before the body changes; OnActorGenerated says when it has, for every body
given on request, and an announcement a save cut off is made again after the load.

## Failure behaviour

- No DLL, or the wrong runtime: Phase 1 is untouched — BodyGen still distributes, the player picker
  still works (S-9). The MCM says the plugin is missing instead of offering dead buttons. Refits left
  from a working session are swept off the people around the player (S-54).
- A DLL and scripts of different releases: the bridge stays off, says so, and sweeps refits off.
- A catalog missing, or of another run than the BodyGen files: the plugin refuses to act on rules and
  ORefit and says so in its log, at load in a notification, and in the MCM's status; refits are swept.
- LooksMenu missing: nothing can be shaped; the bridge stays off and says so once, and the API and MCM
  name LooksMenu as the reason.
- Silhouette.esp missing or disabled: nothing polls; the plugin's log says so a minute after the load --
  naming a refused catalog, or scripts of another release, when that is the reason instead.
  An older Silhouette.esp without the refit keyword: ORefit stays off rather than writing into the body --
  but the refits a save already holds become bodies (S-27): never load one.
- Every order the bridge cannot complete is reported back, never dropped silently; an actor out of
  memory keeps their order until they are seen again, and a roll or touch-up for someone AAF has busy
  waits for the scene to end, while the rest of their work goes on (S-56). A load forgets the orders of
  the save being left; what was asked for is still owed (S-59), and a body a save cut short is given
  again whole (S-58).
- Silhouette.log says every half minute what the bridge did (probes, bodies, refits, touch-ups, failures)
  and what still waits, lane by lane, while there is any of it -- with what a scene holds back and what
  waits for people out of memory.
- A save written by a newer Silhouette: its records are kept unchanged and written back into every save,
  and this version remembers nothing new until the newer one is installed again.
