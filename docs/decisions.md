# Decisions

Settled by the owner unless marked otherwise. Each carries the evidence it rests on, so it can be
re-opened only by evidence that addresses that.

## S-1 — The name is Silhouette

Owner poll, 2026-09-23. It replicates OBody NG's feature set in Fallout 4 under our own naming.

## S-2 — Generator first, then plugin

Owner poll, 2026-09-23. **Phase 1** writes LooksMenu BodyGen files and has no runtime code at all;
**Phase 2** is an F4SE plugin (the Rapport pattern) for what needs run time — the picker, ORefit,
run-time faction rules, events. Phase 1's measuring code is the specification Phase 2 reuses.

Why it is safe to start without a plugin: LooksMenu's BodyGen is already installed and enabled
(`f4ee.ini`: `bEnable=1`, `bEnableBodyGen=1`) and was never fed. Its `Loose` folder is read whatever
plugins are loaded, so Phase 1 ships no `.esp`.

## S-3 — v1 is OBody parity, all four areas

Owner poll, 2026-09-23: random + persistent distribution; rules config + blacklists; in-game picker;
ORefit + nipple/genital variety. Mapping and phase of each piece: [obody-feature-map.md](obody-feature-map.md).

## S-4 — Partial-fit presets are included, if they work without issues

Owner poll, 2026-09-23: *"I would pick 3 if it's still work with no issues."*

Partial fit = 50–95% of a preset's sliders exist on the installed body, **and** the preset declares
this body's family (or none). Measured here: 14 presets, e.g. TWB variants at 77–83% (TWB is built on
CBBE, so the shared names are the same shapes). A Fusion Girl preset overlapping CBBE by 53% through
coincident names is excluded by the family rule.

- **Technically verified**: LooksMenu stores unknown morph names and never moves anything for them;
  the generator does not even write them. The shared sliders land exactly (verify_bodygen.py).
- **Still owed**: an in-game look at partial-fit NPCs, with screenshots to the owner, before this is
  called settled. Switch: `--no-partial`.

## S-5 — Base bodies are built zeroed; the tool measures and says so

**Owner decision, 2026-09-23 (poll): "I'll rebuild zeroed."** The standard BodyGen setup: FemaleBody
and MaleBody (and the outfits) are built with zeroed sliders, and templates hold **absolute** preset
values.

**Why it had to be asked.** BodyGen adds morphs on top of the mesh on disk. `tools/base_body.py` fits
the built `.nif` against BodySlide's reference mesh using the `.tri` diffs, and on this machine found
the bases were NOT zeroed: FemaleBody = "CBBE Chubby" on CBBE Body Physics (0.005% of the
displacement unexplained), MaleBody = "BT - Average" on BodyTalk4 (0.015%). Every NPC would have been
off its preset by RMS 0.97 units (female, up to 3.5) and 0.69 (male). Nothing on disk said so.

**What the tool does about it.** It measures the base on every run. A base that is not zeroed gets a
loud warning naming the exact BodySlide body and zeroed preset to rebuild with, and
`verify_bodygen.py` fails in one line per body until the rebuild is done.

**The alternative, kept as an option.** `--compensate` writes every template as `target − baked`.
LooksMenu applies `vertex += diff × value` with no clamp and parses values with `atof`, so this is
exact: all 65 bodies verified within 0.031 units (half a half-float step). It was offered and not
chosen because it ties the files to the current build — rebuild with another preset and NPCs already
met in a save stay off until they are re-derived — and a zeroed base is what every other BodyGen tool
expects. It stays for installs that cannot be rebuilt.

## S-6 — Every template carries a marker morph named after itself

Agent decision, 2026-09-23, from LooksMenu's source.

LooksMenu runs BodyGen for an actor only while it has **no stored morphs**, and skips zero values
before storing. So a roll that sets nothing is re-rolled on every load — with S-5 that is exactly the
roll of the baked preset itself. The marker (`Silhouette_<Preset>@1`) is a morph no body has: stored,
never moves a vertex, makes every roll permanent, and records which preset the NPC got. Phase 2's
`GetPresetAssignedToActor` reads it back, including for NPCs rolled in Phase 1.

## S-7 — The player is never randomised: an average body by default, a picker in MCM

**Owner request, 2026-09-23**, replacing an earlier agent decision that left the player untouched:
*"make for player picker from installed presets applicable to him via MCM menu and by default use
average body for both sex of player."*

`All|...|HumanRace` includes the Player record (`Fallout4.esm` `0x7`), so without a rule of their own
a player with no LooksMenu body sliders would be randomised on the next load. `Fallout4.esm|7|Female`
and `|Male` each name ONE template: the **most average** preset (S-10). LooksMenu itself skips a
character that already has body sliders, so an existing LooksMenu look is never overwritten by this.

MCM > Silhouette > Your character: a dropdown per sex of every preset that fits (zeroed ones
included, as OBody's menu shows presets blacklisted from random distribution), and buttons *Apply to
my character*, *Back to the default* (`BodyGen.RegenerateMorphs` — BodyGen's own answer, so there is
one source of truth) and *Which body do I have?* (reads the marker back with `BodyGen.GetMorphs`).

## S-8 — Zeroed presets stay out of random distribution

Parity with OBody NG's shipped config (`blacklistedPresetsFromRandomDistribution`: "Zeroed Sliders",
"HIMBO Zero for OBody", …). Decided by **values** rather than names, so FO4's "CBBE Zeroed Sliders"
and "BT - Zero" are caught without a list.

## S-9 — The player picker needs no plugin

Agent decision, 2026-09-23. MCM buttons can call a **global** Papyrus function
(`"type": "CallGlobalFunction"`) — the shape Rapport's "Show recent narration" already uses in this
install — and dropdowns store an index in a `ModSettingInt`. So `Silhouette:Player` is a script with
global functions and nothing else; there is no quest, no alias and no `.esp`. The preset values are
generated into it, by the same function that writes the BodyGen templates, and `verify_bodygen.py`
checks the two agree preset by preset. The cost: the menu is as fresh as the last generator run, like
the templates. Phase 2 can make both live.

## S-10 — "Average" is measured, in vertex space

Agent decision, 2026-09-23. The average body is the full-fit preset whose built body lies closest,
RMS over the vertices, to the **mean body** of the random pool — the pool's medoid. For men that is
"BT - Average", the preset its author named average: the check that the definition means what the
word means. For women, whose collection has no preset called average, it is "xy - Type 3DCG
(Blessed)(2)(a)" (0.467 units from the mean body). "CBBE Vanilla" was 48th of 58, so "vanilla" and
"average" are not the same thing here. Partial fits are not candidates until S-4 is settled in game.

## S-11 — Rules are OBody's config, compiled in OBody's order

Agent decision, 2026-09-23, from OBody's source. The config file and includes use OBody's keys and
shapes unchanged, so an OBody user needs no new vocabulary. Priority is the one
`OBody::GenerateActorBody` actually implements — per-NPC blacklist, per-NPC preset, plugin/race
blacklist, faction, plugin, race, random — not the one commonly summarised; BodyGen expresses
priority only as line order, so the lines are written in reverse (`tools/rules.py`).

What a morphs.ini line cannot name — an NPC's display name (`npc`, `blacklistedNpcs`) or a faction
(`faction*`) — is read, validated and reported as pending, not guessed: base-game names are localised
into string tables inside `Fallout4 - Interface.ba2`, and the Phase 2 plugin can ask the game
directly. ORefit keys are reported the same way.

One addition, `distributeRaces` (default `["HumanRace"]`): OBody gives a body to every NPC race; in
Fallout 4 only races that wear the human body should, and naming them is the only way a BodyGen line
reaches them.

## S-12 — Every marker carries the build's stamp; a manifest says what it means

Agent decision, 2026-09-23, from the microscope review (judgment lens). A marker's NAME is a
sanitised template name, which loses the exact preset name, and its VALUE was a constant 1.0 —
yet LooksMenu stores any non-zero value and moves no vertex for it. The value is now the build's
stamp: the first 24 bits of a hash of everything the files say (exact in float32), and
`F4SE/Plugins/Silhouette/manifests/<stamp>.json` records, for every marker of that build, the exact
preset, its file and the values written. Manifests are never deleted: an NPC rolled by a build
carries its stamp for the rest of that save, and Phase 2 can interpret it. This had to happen
before the first real save, because a roll cannot be re-stamped afterwards.

## S-13 — The character-creation dummies get the player's default

Agent decision, 2026-09-23, found by two review lenses independently. See bodygen-format.md "A new
game clones a dummy onto the player". Without their lines, S-7 fails on every new game. The spouse
in the intro therefore wears the player's default body too.

## S-14 — "Zeroed" is about BODY sliders, and some builds cannot follow a body at all

Agent decision, 2026-09-23. A zeroed build puts every body slider (a morph the body's `.tri` has)
at 0 and leaves an outfit's own sliders (FootShape, OFFSET, ...) at their authored defaults. A
preset's name proves nothing: "CBBE Zeroed Sliders" names one slider, so on a BodyTalk set it
leaves 26 body sliders at 100. `audit_builds.py` also reports STATIC builds — zeroed but unable to
follow any body: a set made for another body family, or an empty `.tri` because the mod ships the
wrong slider data. On the owner's install four were fixed by building a CBBE variant instead of a
Fusion Girl one or a broken one; two have no alternative (FurbyKnight 1st-person sleeves, BodyTalk4
Suit Clean).

## S-15 — A 24-in-game-hour regeneration window for people other mods marked first

**Owner, 2026-09-23:** *"Maybe we need kinda overwrite mod? That temporary will regenerate them and
that aaf set morphs?"* ... *"this regeneration feature will be kinda enable on 24 in game hour and
after that it will automatically disabled."*

LooksMenu runs BodyGen only for an actor with no stored morphs at all, so anyone another mod marked
before Silhouette arrived never gets a body (measured: a Diamond City guard, `000F61B6`, holding
AAF's `Erection` under `AAF_MorphKeyword`). AAF and other mods write under their OWN keywords, so
the fix can keep their morphs:

- `Silhouette.esp` (flagged light, no load-order slot): one self-starting quest running
  `Silhouette:Adopter`, and a form list of people already handled.
- The window opens on the first load with Silhouette and closes itself after 24 in-game hours;
  MCM opens a new one and reports its status.
- Every 10 seconds while it is open, people around the player who hold ONLY keyed morphs are
  rolled by BodyGen (`RegenerateMorphs` -- the same rules, blacklists and player lines as everyone
  else) and their keyed morphs are put back. Left alone: anyone with an unkeyed value (a
  Silhouette body, or sliders set by hand), anyone AAF has busy (`AAF_ActorBusy`) or locked
  (`AAF_ActorLocked`), anyone already handled.
- This is Silhouette's only plugin; everything else still works without it (S-9).

## S-16 — A runtime STATE is never part of a body

Agent decision, 2026-09-23, from the rapport session's co-save reading: two men carried
`Erection=1` in the UNKEYED layer, rolled from `Sirius_Male_preset`, which sets Erection at 100%.
AAF raises Erection under its own keyword for a scene and takes it away after. A preset that sets
it writes it where nothing ever takes it away, so those two had it for good.

- `STATE_MORPHS` in `silhouette_gen.py` lists the morphs something drives at runtime: Erection,
  Erection Up/Down and CErection (AAF), plus VaginaPenetrate and AnusPenetrate (the opening
  sliders of the genital body in `fo4-anatomy`). They are never written into a template or the
  picker, and never compensated either; the base's own state is not ours to change. The
  generator says which presets lost one.
- `verify_bodygen.py` fails any template that sets one. It was proven on the unfixed files first
  (1 failure: Sirius). It also compares each body with its preset MINUS the states.
- Bodies an older build already gave are healed by the regeneration window (S-15). Only the
  unkeyed value of a state morph goes: `SetMorph(..., None, 0.0)` erases exactly that key, per
  LooksMenu's `UserValues::SetValue`. Only bodies carrying a Silhouette marker are touched, so a
  state another mod keeps under its keyword, or one set by hand on a body that is not ours, stays.
  "Refresh the people around me" fixes them as well, because Give re-applies the preset.
- Build dffb550bfd66, stamp 14678869. Its manifest joins the old one; manifests are never deleted
  (S-12).

A related question from the same report: does an actor whose last keyed morph was removed keep
BodyGen away for good? No. The emptied entry lasts until the next save and load. LooksMenu does
not load an empty morph map (`BodyMorphInterface::Load`: `if(morphValueMap->empty()) return
true;`, and `MorphValueMap::Load` skips a morph with no values). BodyGen then rolls the actor as
new, because `ActorUpdateManager` evaluates only when `GetMorphMap` returns null.

## S-17 — Genital shape variety per woman (owner poll, 2026-09-23)

The owner chose, for the labia: jiggle and react (fo4-anatomy A-13), change their look, and vary
per woman. The anatomy body carries Nahka's genital SHAPE sliders (VaginaLabiaSize, VaginaInnie,
VaginaInnie2, VaginaSize, VaginaNarrower, VaginaClitSize, AnusDonut, AnusBack) in its .tri, so
BodyGen can roll them.
- `tools/genital_shapes.json` holds `{morph: [low, high]}`. Every female template gets
  `Morph@low:high` for the morphs the female body has, so LooksMenu rolls each woman her own shape.
  The centre is the owner's chosen look, picked in BodySlide on "Anatomy Body ZeX". It is empty
  until then, and with it empty the generator's output is unchanged.
- Runtime states are refused by name (S-16). VaginaSpread and ButtcheeksSpread join STATE_MORPHS:
  like VaginaPenetrate and AnusPenetrate, they are what scenes animate, never a body.
- `verify_bodygen.fixed_values` sets these ranges aside and compares the rest of each template with
  its preset, so the body check still covers every template.
- AnusBack stays out of the random variety for now. It moves the anal ring ~0.85 back toward ZeX's
  anus bones, so it is an alignment control for fo4-anatomy's anus decision, not a taste.

## S-18 — Phase 2: the plugin decides, a Papyrus bridge applies, BodyGen keeps distributing

Owner poll, 2026-09-23: production-ready means **full v1 with the F4SE plugin**. Agent decisions on
its shape, from the sources (the map: [phase2.md](phase2.md)):
- LooksMenu offers other plugins no C++ interface: `f4ee/exports.def` exports only F4SE's entry
  points, and its message handler answers only F4SE's own messages. Its Papyrus `BodyGen` is the
  only door to the morph store.
- A plugin must not dispatch into the Papyrus VM. Rapport crashed twice in
  `DispatchMethodCallImpl`, because F4SE tasks run on a BSJobs thread and the VM packs arguments
  through the per-thread scrap heap. So `Silhouette.dll` decides and queues, and
  `Silhouette:Bridge` (one quest script, ONE timer, per Rapport's scar) asks and does every
  LooksMenu call. MCM hotkeys call the bridge directly, so the picker previews instantly.
- BodyGen keeps doing random distribution. It applies a body at load, before anyone looks, and a
  plugin reaching LooksMenu through Papyrus arrives a poll later. The plugin adds only what a file
  cannot express.
- Built against alandtse/CommonLibF4 (the commit Rapport runs, `ba22620e`), OG 1.10.163 only,
  refusing any other runtime.

## S-19 — The generator stays the compiler; the plugin reads a catalog

**Amended by the first microscope wave: the build names the bodies, a rules hash names the rules.** Both
BodyGen files state "Build <hex>, marker stamp <n> (<mode>), rules <hex>", the catalog carries the same
rules hash, and the plugin refuses the set when any of the three differs: two runs with different rules
had produced the same build. The build scripts run the plugin's own parser on the generated files
(`SilhouetteTests.exe --check`), and the generator refuses a config value of the wrong shape, so what
the game would refuse at load is refused before anything is deployed.

Agent decision, 2026-09-23. `silhouette_gen.py --write` also writes
`F4SE/Plugins/Silhouette/catalog.json`: every preset that fits, per sex, with its final values and
its classification; the player defaults; the compiled rules, including the tiers BodyGen already
carries, so the plugin knows when NOT to act; and the ORefit sets. The plugin re-derives nothing
the generator measures. The catalog carries the build and stamp, and the plugin refuses to act on
rules or ORefit when they disagree with the BodyGen files, and says so.

## S-20 — ORefit writes final values and restores a snapshot

**Superseded in its mechanism by S-40 (owner, 2026-09-23): the refit is a keyword layer of floors, not final
values with a snapshot. The clothed slots and the order of refit sets below still stand.**

Agent decision, 2026-09-23, from both sources. OBody puts the clothed set under a second key
("OClothe"), and RaceMenu adds keys, so a negative delta works. LooksMenu takes the MAXIMUM over
keys (`UserValues::GetEffectiveValue` is `std::max_element`), so a refit that lowers a value cannot
live under a key of its own. While an NPC is clothed, Silhouette's own (unkeyed) layer holds the
refit's final values. Before writing them, the bridge snapshots exactly those morphs into the
plugin's co-save, and puts the snapshot back on undressing. An NPC's values are their preset plus
their own rolled variety, or a picker choice, or a hand edit, and only a snapshot knows which.
Clothed follows OBody in Fallout 4's slots: BODY (33), [U] Torso (36) or [A] Torso (41), not
blacklisted, or any force-refit item. A refit comes, in order, from the outfit's own refit preset,
`<Preset>-Refit`, `Female-Refit`/`Male-Refit`, and finally the built-in set for this body.

## S-21 — Variety rides on BodyGen ranges; men get nipples and balls only

Owner polls, 2026-09-23. Nipple variety for both sexes, plus ball size for men. Shaft length and
width are NEVER varied. The owner asked whether it would harm "alignment of penis-hole-mouth", and it
would: animations aim the penis bones, and fo4-anatomy's collision spheres are sized to BodyTalk's
current shaft (r 2.0 against a visible 1.55). A wider shaft clips through the lips; a thinner one
opens them with nothing inside. Same mechanism as S-17: `Morph@low:high` entries in the templates,
from `tools/variety.json`. One loader reads both range files, refuses runtime states (S-16), and
FAILS if both files name the same morph. AnusBack is never randomised (S-17).

Addendum, 2026-09-23 (the ranges, agent's choice within the poll): `tools/variety.json` rolls, for
women, NippleSize -0.2..0.5, NippleAreola -0.2..0.5, NippleTip 0..0.35, NippleLength 0..0.25; for men,
BTNippleSize 0..0.5, BTNippleWidth -0.2..0.3, BTNippleTipSize 0..0.35, BTBallSize 0.1..0.7,
BTBallAsymmetry 0..0.4. Measured per unit of slider on the deployed bodies: the worst local stretch is
1.1x to 1.9x for each of them except NippleLength (3.6x, hence the narrowest range); each range spans
what the installed presets themselves use, without their extremes. Left to the presets: nipple
placement and breast-point shape, which are a preset's design; `Balls`, the big size control; NipBGone,
which is ORefit's. Ranges stay ABSOLUTE per sex, as S-17's are, so a range replaces the preset's own
value for that morph (OBody's nipple randomisation does the same under its key) and the verifier can
still check every range exactly. The build hash now covers the ranges: files that roll differently are
a different build. The loader refuses the shaft by name (`Penis Length`, `Penis Width`, `TipShape` and
the BT penis sliders) and AnusBack.

## S-22 — The NPC picker is hotkeys and an MCM page

Owner poll, 2026-09-23. Aim at an NPC and press Pick: they become the target. Next and Previous
cycle every preset that fits their body, live, with the name shown. Keep records the choice; Cancel
restores exactly what they had. The MCM page shows the target with a dropdown of every preset,
plus Apply, Back to random and Which body. There is no custom Scaleform menu: it would be several
times the work, and menu code is where FO4 plugins crash (CommonLibF4's `VisitMembers` on 1.10.163).

## S-23 — Rules only the runtime can see: name, faction, name blacklist

**Amended by the first microscope wave, from OBody NG's source (Body.cpp): a name rule matches the NPC
RECORD's name (`actorBase->GetName()`), not the display name.** A reference renamed at runtime (Rapport names
the settlers it befriends) keeps the rule its record matched; by display name, a blacklisted "Settler"
renamed by Rapport would have been rolled by BodyGen on the next sighting. Faction rules read the record's
own factions, as OBody does, not every template's up the chain. The plugin tier (BodyGen's) reads the
plugin of the chain's root, which is where LooksMenu applies a plugin line.

Agent decision, 2026-09-23. OBody's priority stands (S-11). The plugin acts only when a NAME or
FACTION tier wins for an NPC: it assigns that preset, and the bridge replaces BodyGen's roll. A name
blacklist leaves the NPC bare, with a stored blacklist marker (a morph no body has), so BodyGen
never rolls them again. OBody's `obody_blacklisted` morph does the same job. Names are the NPC's
in-game display name, as OBody's users write them.

## S-24 — The API and events are OBody's, in Papyrus

Agent decision, 2026-09-23. `Silhouette:API` offers global functions named as in OBodyNative. The
bridge raises the events as custom events that any script can register for: OnActorGenerated,
OnActorNaked, OnActorRemovingClothes and OnORefitChanged. The plugin never raises an event itself
(S-18).

## S-25 — The plugin's co-save: who it assigned, why, and what ORefit took

**Superseded by S-43 and S-47: the co-save keeps intent and a picking in progress, nothing of ORefit.** A
placed reference's record is always written, even when its cell is out of memory at save time (the form
map does not hold it then, and dropping it lost picked presets); a created (0xFF) reference's record goes
with the reference.

Agent decision, 2026-09-23. It keeps a record per reference: the preset it assigned and the tier
that chose it (name rule, faction rule, picker, API), the stamp, whether ORefit is on, and ORefit's
snapshot. Form ids are resolved through F4SE, so load-order changes are followed. A new game
starts empty.

## S-26 — ORefit's sets: a built-in one, and OBody's refit presets

**Amended by S-40 and S-42: every entry is a floor now, and the built-in set is BreastsTogether ≥ 0.3, PushUp ≥
0.2, and NipBGone 1 under heavy clothes only.**

Agent decision, 2026-09-23. `builtin:female`, for CBBE: BreastsTogether at least 0.3, BreastGravity2 at
most 0.2, PushUp at least 0.2, NipBGone 1 with NippleLength, NipplePerkiness, NipplePerk2 and NippleTip
at 0, Butt and AppleCheeks 0.05 less. Floors, ceilings and small steps, so a modest body changes little.
There is no male set. OBody's refit presets -- a BodySlide preset named "<Preset>-Refit",
"Female-Refit" or "Male-Refit" -- are compiled into sets (every slider they carry, as `set`), are never
handed out as bodies, and outfits name theirs by the outfit's in-game name
(`refitOutfitPresetsFemale/Male`, OBody's keys). Outfits that never refit and outfits that always do
are OBody's keys too, by form id, name or plugin. The player is never refit.

## S-27 — Reset, Back to random, and leaving

**Amended by S-40/S-41: Reset also removes the refit layer and nothing is refit until she has a body again;
leaving needs no step at all -- removing Silhouette.esp removes every refit.**

Agent decision, 2026-09-23, from LooksMenu's source. Reset removes Silhouette's (unkeyed) layer: the NPC
is bare now, and LooksMenu drops emptied entries when it loads a save (MorphValueMap::Load skips them),
so BodyGen gives them a body again after the next load. Back to random (GenActor) runs BodyGen at once
through RegenerateMorphs, which clears every key, so the bridge keeps other mods' keyed values and puts
them back -- the regeneration window's way. For uninstalling, MCM > Silhouette > Settings takes ORefit
off everyone the save remembers with a refit on: the people in memory at once, the rest when next seen,
as long as ORefit stays off. BodyGen bodies need nothing: they are LooksMenu's data.

## S-28 — The bridge's protocol is fixed, and tested where it is decided

Agent decision, 2026-09-23. The plugin builds each order when the bridge asks for it, from the state at
that moment, one order per actor at a time, the latest decision winning while it waits. The bridge does
exactly: regenerate, probe, read, Prepare, clear, write, update, Done -- nothing else -- and the offline
tests run the same steps against a fake LooksMenu layer, so what a body ends up holding is tested, not
only the orders. The native script is `Silhouette:Plugin` (Papyrus reserves `Native`) -- renamed `Silhouette:DLL` by S-46. Functions that
touch only the plugin's own state are callable from tasklets (no frame each); anything that reads an
actor runs on the main thread, where the game changes it. Actors travel as form ids.

## S-29 — The shaft is never part of a body

Owner poll, 2026-09-23: "Should Silhouette strip shaft sliders from every body, as it already does
for erection states?" -- "yes". Two of the eight installed male presets set `Penis Width` (0.2 and
1.0), the width the owner had already ruled out for variety (S-21): animations aim the penis bones
and fo4-anatomy's collision is sized to BodyTalk's current shaft, so a wider one clips through the
lips. Like the runtime states (S-16), the shaft's sliders -- `Penis Length`, `Penis Width`,
`TipShape` and BodyTalk's `BTPenis*`, `BTShaftRootSize`, `BTUrethraCurve`, `BTSmoothPenis*` -- are
never written into a template, the player's picker, the catalog or a refit set, and the verifier fails
a template that has one. Bodies an older build already gave are healed the way S-16 heals states: the
plugin reads, from the manifest of the stamp an NPC's marker carries, whether that template held any
morph that is now never part of a body, and zeroes exactly those in the unkeyed layer once; the
regeneration window does the same for Silhouette-marked NPCs without the plugin. The player keeps
their own body until they apply a preset again in MCM.

## S-40 — ORefit is a keyword layer that only raises (supersedes S-20's mechanism)

Owner poll, 2026-09-23, after the first microscope wave showed that S-20's design keeps a clothed
woman's naked values only in Silhouette's co-save, so one save without the DLL, a save that lands in the
middle of a refit, or an NPC whose cell unloads makes the clothed shape her naked body for good. The owner
chose the recommended option and added: "dressed and undressed bodyshape should be in sync (besides that
intentional difference u named)".
- The refit lives under Silhouette's own keyword (Silhouette.esp, KYWD 0x803). LooksMenu shows the
  MAXIMUM over keyword layers, so each entry is a FLOOR: while dressed she has at least that value, and
  everything else is her own body. The clothed shape therefore follows every change to her body -- a new
  preset, the picker, variety -- with nothing to keep in step.
- Refit on replaces Silhouette's keyword layer with the set's floors and a refit marker; refit off removes
  the layer. Both are safe to repeat and to interrupt. Nothing about a refit is kept in the co-save: the
  marker in LooksMenu's own data says whether one is on.
- Removing Silhouette.esp removes every refit: LooksMenu drops keyed values whose keyword no longer
  resolves when it loads a save.
- The cost: a refit cannot lower anything. No cap on breast sag, no easing of the seat, and a
  "<Preset>-Refit" preset raises its sliders only. OBody's other refit rules (S-20's slots and order of
  sets, S-26's refit presets and outfits by name) stand.

## S-41 — Who is refit

Owner poll, 2026-09-23: only bodies that should be, "but we need to be sure we didnt miss something we
should cover and also i think custom followers should be included by default if user didnt blacklist them".
Every clothed woman of a distributed race who HAS a body is refit: a Silhouette body, a body another
mod's BodyGen files gave, a custom follower's, one edited by hand in LooksMenu. Never refit:
- anyone blacklisted -- by name, by form id, by plugin or by race;
- anyone reset this session (S-27): she is bare until BodyGen gives her a body after a load;
- anyone with no body at all: the refit would be her first stored morph, and LooksMenu never runs BodyGen
  for an actor that holds one;
- the player and the character-creation dummies.
Having a body is read from LooksMenu: a Silhouette marker, or a non-zero value of her own.
Nobody outside this -- the player, the dummies, creatures, races Silhouette does not distribute to -- is
ever probed: that is most actors in the world. A race taken out of `distributeRaces` keeps the refits its
women already have until they are reset, or until Silhouette.esp is removed.

## S-42 — Nipples are flattened under heavy clothes only

Owner poll, 2026-09-23 ("would be cool to flatten nipples only on heavy clothes like in reality with rough
tissue"; then "Armour pieces + armoured outfits"). Measured in the base game and DLCs: most clothes take
BODY (33) AND [A] Torso (41) -- dresses, suits, lab coats, even the bathrobe -- so the slot says nothing;
366 of 492 BODY items are rated 0. Heavy is: a separate chest armour piece ([A] Torso without BODY), or an
outfit whose armour rating is 10 or more (the Brotherhood uniform 10, the Courser jacket 30, Maxson's coat
50). Config lists name single items heavy or light by form id or name (`heavyOutfitsFormID`,
`heavyOutfits`, `lightOutfitsFormID`, `lightOutfits`; the rating is `heavyArmorRating`). The built-in CBBE set is
BreastsTogether at least 0.3 and PushUp at least 0.2 whenever she is dressed, and NipBGone 1 under heavy
clothes. An arousal bump for nipples is the anatomy project's (owner); under a keyword of its own it
combines with this one by the same maximum.

## S-43 — Truth first: the co-save keeps intent, LooksMenu keeps the body

Agent decision, 2026-09-23, from the first microscope wave. The co-save and LooksMenu's own data are two
files that can disagree -- a save that lands between two bridge calls, a save made without the DLL, a
non-persistent NPC whose morphs LooksMenu drops at load, a reroll that goes around the plugin. So:
- The first order for an actor in a session is a probe of LooksMenu: her markers (body and refit) and the
  names she holds.
- The co-save keeps only INTENT -- who chose which body (a rule, the picker, the API, the name
  blacklist) -- and it is written when the choice is made, not when the bridge finishes.
- After each probe the plugin makes reality match intent: a body that is not the chosen one is given
  again (once a session), a refit that should not be there comes off, one that should is put on.
- Every order is safe to repeat. Order ids start at a random number each launch, and the bridge checks
  that an order still names its actor before it writes: a script stack a save resumed cannot act on
  someone else's order.
- A record belongs to its reference. Only a created (0xFF) reference's id can be handed to somebody new,
  so only there does a different NPC record mean somebody else; a placed leveled NPC is given a new
  temporary record when it respawns and stays the same person to LooksMenu, and keeps its record.
- Work goes in three lanes: the player's own actions first (picker, menu, API, a refit coming off),
  then decisions (rules, refits, top-ups), then probes.

## S-44 — Top-up: existing bodies get the variety they lack

Owner poll, 2026-09-23 ("i aggree with recommended, but force regen on 24h function ofc will override
it"). The first time the plugin sees a Silhouette body that lacks a variety slider the current build rolls
(S-17, S-21), it writes a drawn value for just those sliders; everything else about her body stays. The
same order carries the S-29 heal. A regeneration (the window, Back to random, GenActor) replaces the body
and its variety with a new roll. The variety switches (S-24) apply.

## S-45 — The player is never randomised (S-7, restored)

Agent decision, 2026-09-23, from the first microscope wave: S-21 had put ranges on the player's template,
because the player's line named the same template as the random pool. The player and the two
character-creation dummies now name range-free templates with the same values and marker, so a new
character is the most average preset exactly, and "Back to the default" gives the same body.

## S-46 — The API's events and names

Agent decision, 2026-09-23. The bridge sends its custom events under the names the compiler gives them,
"silhouette:bridge_<Event>": sent under the bare name, no listener ever receives them (the vanilla scripts
and Rapport do the same). The native script is `Silhouette:DLL` -- "Plugin" also means an .esp in this
project's own config. OBody's exact names (ResetActorOBodyMorphs, ReapplyActorOBodyMorphs) are aliases.
Calls that change a body return before it changes; OnActorGenerated says it happened.

## S-47 — The NPC picker survives a save

Agent decision, 2026-09-23. The picker's copy of the body and the choice the NPC had before are kept in
the co-save while picking. A save made mid-preview loads as a Cancel: the preview never becomes a body
nobody kept.
