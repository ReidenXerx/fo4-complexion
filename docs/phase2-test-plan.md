# Phase 2 — the first in-game session

Eighteen steps for the first session with Silhouette.dll, each with what to expect and what a failure
means. Written from the second and third microscope waves' measurements of the owner's own install (809
plugins, 1,609 built .tri files, the saves that hold Silhouette bodies); the log lines are quoted from the
code. Everything the offline tests cannot reach is here: LooksMenu itself, the engine's events, the frame
each Papyrus call costs.

Before any of it: the generated files must be of the body that is installed. When another project
rebuilds FemaleBody (fo4-anatomy does), regenerate after it, not before.

**Never load an older Silhouette.esp over this one** -- not the Phase-1 file, not an earlier build. One
without the refit keyword (0x803) turns every refit on anyone into her own body for good (decisions S-27).
To go back, remove Silhouette entirely, or remove only Silhouette.dll (step 17).

## Setup

1. **Game closed.** Back up the save's `.fos` and `.f4se`. Run `scripts\deploy-dev.ps1` -- it refuses a
   catalog and BodyGen files of two generator runs, a Player.pex compiled from another run, files the
   verifier fails, an edited committed manifest, and a Silhouette.esp without the refit keyword (whether
   the bridge's scripts and the DLL are of one release is checked by the bridge at every load). It
   stages the Silhouette-dev mod's files in place, refusing before the first write if any of them is held
   open: every file Data already links goes live at once. Then it reads Data itself and lists by name every
   file Data does not hold as the staged one yet, which waits for Vortex's Deploy -- press Deploy before
   launching whenever it lists any. Silhouette.esp (two quests, two form lists, a keyword: well over the Phase-1 file's 304
   bytes) is already enabled. Set `f4ee.ini` `iLogLevel=3`, and in `Fallout4Custom.ini`
   `[Papyrus] bEnableLogging=1, bEnableTrace=1`.

## First load

2. Load the save and stand still for 60 seconds. In `Documents\My Games\Fallout4\F4SE\Silhouette.log`,
   expect, in this order:
   - `papyrus: Silhouette:DLL bound (protocol 3)`
   - `catalog: build <build>, stamp <stamp>, rules <rules>, N presets, N manifest(s), 0 faction rule(s), 1 refit set(s)`
     -- the build, stamp and rules the generator printed last; one manifest per build ever generated
     (five: waves 3 and 4 kept the build and stamp). A `manifest <file> says it is build stamp <n>: not
     read` means a manifest was renamed by hand.
   - `events: TESObjectLoadedEvent attached (holder scan, ...)` and `events: TESEquipEvent attached (holder scan, ...)`
   - `after loading: N record(s); loaded: yes, equip: yes, crosshair: ...`
   - `bridge: bridge connected - ready: build ...`
   - about 30 seconds after the bridge's first poll, `after loading: N actor(s) around the player read; the
     game reported M of them as loaded, and K it reported were not among them; the first poll came T s after
     the load`, with N about the number of people, creatures and robots nearby. M is large after a load from
     the main menu and 0 after one in a running game (27 and 0 in wave 4's run): the game reports only the
     first (S-43's amendment), and N is what makes up for it. K is 0, or 1 after a main-menu load: the game
     reports the player, whom the process lists do not hold (and Silhouette never shapes). More would mean
     the sweep misses people the game reports. With `bAlwaysActive=0` -- the owner's `Fallout4Custom.ini`
     sets 1, which keeps the game running unfocused and masks this -- load in the running game and alt-tab
     out for 40 seconds at once: T reads about 40, and the line and step 13's restore still come.

   What a failure means:
   - no Silhouette.log at all -- the plugin did not load: F4SE's own `f4se.log` says why (another runtime,
     or "disabled, fatal error occurred while loading plugin"). Before the fifth wave, a Documents path with
     a Cyrillic, Polish or Chinese user name did exactly that, and looked like a plugin that never ran.
   - `catalog refused` -- files of two generator runs. Regenerate and deploy them together.
   - `equip: no` in the after-loading line -- ORefit will not follow undressing. Stop. (An earlier
     `events: no source for TESEquipEvent yet - ...` is only a warning that the source was attached
     later.)
   - `the bridge has not polled in the minute since the save loaded` -- Silhouette.esp disabled, its
     scripts missing, or LooksMenu missing. `Silhouette's scripts answered but the bridge does not
     poll` -- the bridge's script missing or of another release, or LooksMenu missing. `nobody is shaped
     one by one this session - <why>` -- the catalog was refused.
   - a notification "Silhouette.dll and its scripts are from different releases" -- stale .pex files.
   - a notification "LooksMenu is not loaded" -- F4EE is missing; nothing can be shaped.
3. `f4ee.log`: the Silhouette templates load and their targets are acquired. LooksMenu's
   `template <name> not found.` means a template was dropped (the verifier would have failed that build).
4. MCM > Silhouette > Settings > "How is Silhouette doing?" at about 10 and 60 seconds: "order(s)
   waiting" reaches 0 by 60. Every half minute when something was done or can be done, Silhouette.log
   says what (work only held back by a scene, or waiting for people out of memory, is said with the next
   line that has news):
   `bridge: N probe(s), N body order(s), N refit(s), N touch-up(s), N snapshot(s); N failed, N out of
   reach, N deferred; N waiting (N urgent, N normal, N background)`, then `N held while another mod has
   them busy` and `N for people out of memory` when there are. A waiting count that never falls means
   Papyrus is congested: check `Logs\Script\Papyrus.0.log`.
5. The first load touches up the bodies an older build shaped (it had no nipple, genital or ball
   ranges) as the probe meets them: one line of `XXXXXXXX: N slider(s) healed or topped up on <preset>`
   per body in the loaded cells -- 22 Silhouette bodies are in the newest Goodneighbor save, the rest
   when met. None at all means the touch-up is not firing (the probe, or the manifests). The heal to
   look for: the BT - Chubby men 0002A8A7 and 00034684 and the BT - Bodybuilder men 001D1F49 and
   33009A54 lose `Penis Width` and `TipShape` (S-29). (The Sirius men already lost their erection in
   that save: they prove nothing.) Silhouette.log names people by their NPC RECORD's name: someone
   Rapport or We Are Unique renamed reads differently in MCM.
6. **The MCM switches reach the plugin.** MCM > Silhouette > Settings, ORefit off: within about 10
   seconds Silhouette.log has `ORefit off by the settings` and the push-ups relax; on again, they come
   back. (Wave 2 looked for MCM under the wrong name and every switch was ignored.)

## ORefit

7. Aim at a woman whose preset has less push-up than the floors -- Imitation UNP #2, xy Type 3DCG
   (Blessed)(2)(Bigger), a Josie, CBBE Slim or Athletic body -- and open MCM > The NPC in your sights >
   "Which body do they have?". Expect `<name>: <preset>. nobody chose their body: it is BodyGen's;
   dressed, refit on.` and a visible push-up; Silhouette.log has `XXXXXXXX "<name>": refit on
   (builtin:female)`. A Rocket Bomb Body woman gives the same text and no visible change: her own values
   are already above the floors (0.3 / 0.2). `dressed, not refit` means no body was found, or ORefit is
   off.
8. Undress a companion through the trade menu, then dress her again. The push-up relaxes within about
   a second and comes back within about a second; "Which body" follows, and the log has `refit off`
   then `refit on`. If the shape does not come back: the equip events (step 2), or `order N (kind 3) not
   completed by the bridge`. Watch for a physics jolt when a refit lands.
9. Heavy clothes (S-48), told by the item's name:
   - A combat armour chest piece over her outfit: the log has, once, `clothing XXXXXXXX "Combat Armor
     Chest Piece" (Fallout4.esm): heavy - the name says "armor"`, and "Which body" says `dressed
     heavily (Combat Armor Chest Piece), refit on`. Nothing shows: no vanilla or DLC heavy garment's
     mesh carries the refit sliders (two light vanilla clothes carry NipBGone; they are never flattened).
   - Where it shows: a mod outfit built with them. Mercenary.esp 000941 "Merc Combat Jacket A", or
     Clothing Of The Commonwealth.esp 000896 "Western Coat": heavy, nipples flat under it. The light
     control, Mercenary.esp 000938 "Rebel Shirt": nipples as they are.
   - Eli_Armour_Compendium.esp's "Danse's BoS Armour No Jacket [M]", "Elijah's Armour" and "X6's Courser
     Armour" are built as shirts: `light - listed as light`. Its "Institute Courser Uniform": `heavy -
     listed as heavy`.
   - A Nezzar bra, a DX Adventurer outfit, an ObiCozy shirt: light -- no line, no flattened cups (wave 2
     measured the old rating and slot rules flattening exactly these).
   - Power armour: getting into a frame raises no OnActorNaked or OnActorRemovingClothes. Her refit may
     come off while she is in the frame (the frame is not clothes) and comes back once she is out and
     dressed.
10. Save to a new slot, quit, relaunch, load it.
   - `co-save: N record(s) written (N held)` at the save, `co-save: N record(s) after loading` after.
     The first save's count is about one per body the probes met (what was announced and touched is
     remembered), not only the choices.
   - No refit pop this time: the refits are LooksMenu's data, not the plugin's.
   - If the push-up lands again on every load, LooksMenu is dropping the light plugin's keyword layer --
     a blocker for S-40. Stop and report.

## The picker

11. Bind the five hotkeys in MCM (unbound by default). Pick someone WITH THE HOTKEY, aiming at them from
    talking distance (the crosshair is the game's activate pick, S-64; `DLL.PickerStart` from the console
    skips the crosshair, and that is how the first run missed that Pick never found anyone). Aim at a door
    and press Pick: the notification asks for an NPC, and Silhouette.log has `pick: nobody to pick - the
    crosshair is on <door>, not an NPC`. Wait a second after a Pick ("Still reading" otherwise). Next three times -- each preset lands about a second after its notification -- then
    Keep. "Which body" says `chosen: <preset> (picked)`. Save and reload: she keeps it. Lanes (S-55):
    press MCM's Refresh with a crowd around, and at once Pick someone and press Next -- the preview
    still lands within about a second.
12. Pick another NPC, Next twice, Cancel: exactly her previous body, her own hand edits included.
13. Pick someone, Next, and SAVE with the preview on her; load that save from the pause menu, without
    quitting: she is back on her own body, and Silhouette.log has `a picking left unfinished - the body they
    had goes back` (S-47), and probes after the load. (Wave 3 failed exactly this: nobody was read after such
    a load.) Then undress a companion through the trade menu: `refit off` within about a second, so the
    equip events still arrive after a load in a running game.
14. "Back to random" (MCM, The NPC in your sights) on a woman who is not in a scene: a new body within a
    second, other mods' keyed morphs kept -- the anatomy arousal layer included (fo4-mcp's `bodygen
    morphs` verb shows its keyword layer before and after). (A Back to random saved before it lands is carried out after the
    load, S-59: too quick to catch by hand, the offline tests cover it.)

## With AAF

15. An AAF scene with a dressed woman showing the refit: it comes off within about a second of the strip
    and returns after the redress -- also while a "Back to random" on her waits for the scene (wave 3).
    "Back to random" on someone in the middle of a scene logs `XXXXXXXX: another mod has them busy - the
    change waits`, the message box says the new body comes when the scene ends, and the roll lands
    after it (`the change that waited for another mod is done`). No touch-up or roll changes her shapes
    mid-scene. A heavily dressed woman who is aroused keeps her nipples flat once fo4-anatomy reads the
    refit marker (S-49).

## Clean

16. `Papyrus.0.log`: no Silhouette errors or stack dumps. Silhouette.log: no `not completed by the
    bridge`, no `the bridge fell behind`.
17. On a COPY of the save only:
    - Disable just Silhouette.esp and load: every push-up is gone (LooksMenu drops the keyword's
      values), and the log warns that the bridge did not poll. Enable it again: refits return on sight.
      (Disabling is safe. Loading an older Silhouette.esp is not -- see the top.)
    - Game closed, MOVE Silhouette.dll out of `Data\F4SE\Plugins` -- move, not copy: Vortex hardlinks
      Data to its staging folder -- and do not Deploy in Vortex until it is back. Load: within about half
      a minute the women around you lose their refits, and `Papyrus.0.log` has `Silhouette bridge: N
      refit(s) left on people without a working Silhouette.dll taken off` (S-54). Save to a new slot,
      quit, move the DLL back, load that save: someone picked in step 11 still reads `chosen: <preset>
      (picked)`, and Silhouette.log has `rebuilt from the choice LooksMenu keeps beside the body` (S-51).
18. Optional, on a copy: press Refresh with a crowd around (15 to 30 seconds of work) and quicksave in
    the middle; load it. Anyone the save cut short gets `half a body of <preset> (a save cut it short) -
    given again, whole`, and nobody is left with half a body (S-58).

## Not checked offline

- Whether LooksMenu's co-save keeps values under a keyword from a light plugin (step 10 catches it).
- Whether a refit landing jolts physics (step 8).
- Heavy by name reads names as the game shows them: on a localized Fallout4.esm no vanilla item is heavy
  until `heavyWords` holds that language's words.
- CompanionIvy.esm's `SkinNaked_Ivy` is an equippable naked-body armour in slots 33-35. If anything
  equips it, Silhouette reads Ivy as clothed and refits her naked body; `blacklistedOutfitsFromORefitFormID`
  takes it out.
- The frame cost of LooksMenu's natives and of `Game.GetForm`: every timing above assumes about one
  frame per call.
