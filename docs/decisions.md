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

## S-5 — Templates are written relative to the measured base body

Decided by the agent, 2026-09-23; see the poll in the session log for owner confirmation.

**Evidence.** BodyGen adds morphs on top of the mesh on disk. `tools/base_body.py` fits the built
`.nif` against BodySlide's reference mesh using the `.tri` diffs, and on this machine identifies the
baked presets exactly: FemaleBody = "CBBE Chubby" on CBBE Body Physics (0.005% of the displacement
unexplained), MaleBody = "BT - Average" on BodyTalk4 (0.015%). Uncompensated, every NPC would be off
its preset by RMS 0.97 units (female, up to 3.5) and 0.69 (male). LooksMenu applies
`vertex += diff × value` with no clamp and parses values with `atof`, so a template of
`target − baked` lands every NPC on its preset: all 65 verified within 0.031 units, which is half a
half-float step of the installed mesh.

**What it buys.** No rebuild. The player and every NPC Silhouette does not touch keep exactly the
body they have today; the usual BodyGen requirement "build your body with Zeroed Sliders" is gone.

**What it costs.** The files are tied to the current build. Rebuild a body with another preset and
the generator must be run again — and NPCs already rolled in an existing save keep values computed
against the old base until Phase 2 re-derives them from their marker (S-6). The alternative, requiring
a zeroed base, has the mirror-image hazard (a non-zero rebuild breaks every NPC) and forces the
player's look to be re-made in LooksMenu. `--no-compensate` writes absolute values.

If the base cannot be identified (a hand-moved slider never saved as a preset), the generator says
so loudly and writes absolute values rather than guess.

## S-6 — Every template carries a marker morph named after itself

Agent decision, 2026-09-23, from LooksMenu's source.

LooksMenu runs BodyGen for an actor only while it has **no stored morphs**, and skips zero values
before storing. So a roll that sets nothing is re-rolled on every load — with S-5 that is exactly the
roll of the baked preset itself. The marker (`Silhouette_<Preset>@1`) is a morph no body has: stored,
never moves a vertex, makes every roll permanent, and records which preset the NPC got. Phase 2's
`GetPresetAssignedToActor` reads it back, including for NPCs rolled in Phase 1.

## S-7 — The player is never given a body

Agent decision, 2026-09-23. `All|...|HumanRace` includes the Player record, and a player without
LooksMenu body sliders has no stored morphs, so BodyGen would randomise them on the next load.
`Fallout4.esm|7` gets a template that sets nothing — here the re-roll is the point: it evaluates to
nothing every time, so the player is never touched. OBody NG leaves the player alone too (by event
timing rather than by rule). Choosing a body for the player is the picker's job (Phase 2).

## S-8 — Zeroed presets stay out of random distribution

Parity with OBody NG's shipped config (`blacklistedPresetsFromRandomDistribution`: "Zeroed Sliders",
"HIMBO Zero for OBody", …). Decided by **values** rather than names, so FO4's "CBBE Zeroed Sliders"
and "BT - Zero" are caught without a list.
