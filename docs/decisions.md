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
