# Phase 2 — the first in-game session

Fourteen steps for the first session with Silhouette.dll, each with what to expect and what a failure
means. Written from the second microscope wave's measurements of the owner's own install (809 plugins,
1,609 built .tri files, three saves); the log lines are quoted from the code. Everything the offline
tests cannot reach is here: LooksMenu itself, the engine's events, the frame each Papyrus call costs.

Before any of it: the generated files must be of the body that is installed. When another project
rebuilds FemaleBody (fo4-anatomy does), regenerate after it, not before.

## Setup

1. **Game closed.** Back up the save's `.fos` and `.f4se`. Run `scripts\deploy-dev.ps1` -- it refuses a
   catalog, BodyGen files, scripts or a DLL of different builds -- then Deploy in Vortex. The new
   Silhouette.esp (two quests, two form lists, a keyword: well over the 304-byte Phase-1 one) must win
   over the Phase-1 mod, and be enabled. Set `f4ee.ini` `iLogLevel=3`, and in `Fallout4Custom.ini`
   `[Papyrus] bEnableLogging=1, bEnableTrace=1`.

## First load

2. Load the save and stand still for 60 seconds. In `Documents\My Games\Fallout4\F4SE\Silhouette.log`,
   expect, in this order:
   - `papyrus: Silhouette:DLL bound (protocol 3)`
   - `catalog: build <build>, stamp <stamp>, rules <rules>, 68 presets, N manifest(s), 0 faction rule(s), 1 refit set(s)`
     -- the build, stamp and rules the generator printed last
   - `events: TESObjectLoadedEvent attached (holder scan, ...)` and `events: TESEquipEvent attached (holder scan, ...)`
   - `after loading: N record(s); loaded: yes, equip: yes, crosshair: ...`
   - `bridge: bridge connected - ready: build ...`

   What a failure means:
   - `catalog refused` -- files of two generator runs. Regenerate and deploy them together.
   - `events: no source for TESEquipEvent` -- ORefit will not follow undressing. Stop.
   - `the bridge has not polled in the minute since the save loaded` -- the old esp or old scripts.
   - a notification "Silhouette.dll and its scripts are from different releases" -- stale .pex files.
   - a notification "LooksMenu is not loaded" -- F4EE is missing; nothing can be shaped.
3. `f4ee.log`: the Silhouette templates load and their targets are acquired. A `template not found`
   means a template was dropped (the verifier would have failed that build).
4. MCM > Silhouette > Settings > "How is Silhouette doing?" at about 10 and 60 seconds: "order(s)
   waiting" reaches 0 by 60. Every half minute while there is work, Silhouette.log says what was done:
   `bridge: N probe(s), N body order(s), N refit(s), N touch-up(s), N snapshot(s); N failed, N out of
   reach, N deferred; N waiting (N urgent, N normal, N background)`. A waiting count that never falls
   means Papyrus is congested: check `Logs\Script\Papyrus.0.log`.
5. The first load touches up nearly everyone an older build shaped (it had no nipple, genital or ball
   ranges): about twenty lines of `XXXXXXXX: N slider(s) healed or topped up on <preset>`. None at all
   means the touch-up is not firing (the probe, or the manifests). A naked man with the Sirius preset
   has no erection any more (S-16, S-29 heal).

## ORefit

6. Aim at a woman whose preset has less push-up than the floors -- Imitation UNP #2, xy Type 3DCG
   (Blessed)(2)(Bigger), a Josie, CBBE Slim or Athletic body -- and open MCM > The NPC in your sights >
   "Which body do they have?". Expect `<name>: <preset>. nobody chose their body: it is BodyGen's;
   dressed, refit on.` and a visible push-up; Silhouette.log has `XXXXXXXX "<name>": refit on
   (builtin:female)`. A Rocket Bomb Body woman gives the same text and no visible change: her own values
   are already above the floors (0.3 / 0.2). `dressed, not refit` means no body was found, or ORefit is
   off.
7. Undress a companion through the trade menu, then dress her again. The push-up relaxes within about
   a second and comes back within about a second; "Which body" follows, and the log has `refit off`
   then `refit on`. If the shape does not come back: the equip events (step 2), or `order N (kind 3) not
   completed by the bridge`. Watch for a physics jolt when a refit lands.
8. Heavy clothes (S-48), told by the item's name:
   - A combat armour chest piece over her outfit: the log has, once, `clothing XXXXXXXX "Combat Armor
     Chest Piece" (Fallout4.esm): heavy - the name says "armor"`, and "Which body" says `dressed
     heavily, refit on`. Nothing shows on vanilla meshes: they carry no NipBGone.
   - A Nezzar bra, a DX Adventurer outfit, an ObiCozy shirt: light -- no line, no flattened cups (wave 2
     measured the old rating and slot rules flattening exactly these).
   - Power armour: no refit on entering or leaving a frame.
9. Save to a new slot, quit, relaunch, load it.
   - `co-save: N record(s) written (N held)` at the save, `co-save: N record(s) after loading` after.
   - No refit pop this time: the refits are LooksMenu's data, not the plugin's.
   - If the push-up lands again on every load, LooksMenu is dropping the light plugin's keyword layer --
     a blocker for S-40. Stop and report.

## The picker

10. Bind the five hotkeys in MCM (unbound by default). Pick someone and wait a second ("Still reading"
    otherwise). Next three times -- each preset lands about a second after its notification -- then
    Keep. "Which body" says `chosen: <preset> (picked)`. Save and reload: she keeps it.
11. Pick another NPC, Next twice, Cancel: exactly her previous body, her own hand edits included.

## With AAF

12. An AAF scene with a dressed woman showing the refit: it comes off within about a second of the strip
    and returns after the redress. "Back to random" on someone in the middle of a scene logs
    `XXXXXXXX: another mod has them busy - the change waits` and the roll lands after the scene. A
    heavily dressed woman who is aroused keeps her nipples flat once fo4-anatomy reads the refit
    marker (S-49).

## Clean

13. `Papyrus.0.log`: no Silhouette errors or stack dumps. Silhouette.log: no `not completed by the
    bridge`, no `the bridge fell behind`.
14. On a COPY of the save only:
    - Disable just Silhouette.esp and load: every push-up is gone (LooksMenu drops the keyword's
      values), and the log warns that the bridge did not poll. Enable it again: refits return on sight.
    - Game closed, move Silhouette.dll out of `Data\F4SE\Plugins`, load: within about half a minute the
      women around you lose their refits, and `Papyrus.0.log` has `Silhouette bridge: N refit(s) left on
      people without a working Silhouette.dll taken off` (S-54). Put the DLL back.

## Not checked offline

- Whether LooksMenu's co-save keeps values under a keyword from a light plugin (step 9 catches it).
- Whether a refit landing jolts physics (step 7).
- CompanionIvy.esm's `SkinNaked_Ivy` is an equippable naked-body armour in slots 33-35. If anything
  equips it, Silhouette reads Ivy as clothed and refits her naked body; `blacklistedOutfitsFromORefitFormID`
  takes it out.
- The frame cost of LooksMenu's natives and of `Game.GetForm`: every timing above assumes about one
  frame per call.
