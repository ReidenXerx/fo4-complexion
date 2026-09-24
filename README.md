# Silhouette

OBody NG's body distribution, for Fallout 4. Every NPC gets one of your BodySlide presets the first
time you meet them, and keeps it.

**Status:** Phase 1 (the generator; LooksMenu's own BodyGen does the work at run time) is in use.
Phase 2 — `Silhouette.dll`, an F4SE plugin, with `Silhouette.esp` — adds the rules only a running game
can see, ORefit, the NPC picker, the touch-up and an API with OBody's names. It is built and tested
offline; its first in-game session ([docs/phase2-test-plan.md](docs/phase2-test-plan.md)) is next. What
maps where: [docs/obody-feature-map.md](docs/obody-feature-map.md); how Phase 2 works:
[docs/phase2.md](docs/phase2.md).

## What it does that a hand-written BodyGen file does not

It **measures your install** instead of assuming it.

- **Which presets can do anything.** A preset whose sliders your body's `.tri` does not have is a
  silent no-op. Silhouette reads the `.tri` and hands out only presets that move your body — on the
  machine it was written on, 27 of 120 presets (Fusion Girl, Atomic Beauty on a CBBE body) were left
  out.
- **What your base body already has baked in.** BodyGen adds on top of the mesh on disk, so if you
  built your body with anything but Zeroed Sliders, every NPC preset stacks on it. Silhouette fits
  your built body against BodySlide's reference mesh and names the preset it was built from — exactly
  ("CBBE Chubby", 0.005% unexplained) — and tells you which zeroed preset to rebuild with. If you
  cannot rebuild, `--compensate` writes every template relative to what is baked instead, and every
  NPC still lands exactly on its preset.
- **What it wrote.** `tools/verify_bodygen.py` reads the files the way LooksMenu reads them and
  builds every body they can produce: each lands within 0.031 units of its preset.

It never re-rolls an NPC you have already met, and leaves zeroed presets out of the random pool as
OBody does.

## Your character

Never randomised. A character with no LooksMenu body sliders gets the **most average** of your
presets — measured: the one whose body is closest to the mean of them all ("BT - Average" for men,
which is reassuring). **MCM > Silhouette** lists every preset that fits your character's body:
choose one and press *Apply to my character*; *Back to the default* and *Which body do I have?* are
next to it. No plugin is involved — the menu calls a small script LooksMenu drives.

## People other mods marked first

LooksMenu only gives a body to someone who holds no body morphs at all, so an NPC another mod
already marked (an AAF morph left behind by a scene) never gets one. With `Silhouette.esp` enabled
(a light plugin, no load-order slot), for 24 in-game hours after Silhouette first loads, such people
around you are given a body and the other mod's morphs are kept; MCM shows the window and can open a
new one.

## With the plugin (Phase 2)

`Silhouette.dll` decides; a Papyrus script on `Silhouette.esp` carries its decisions out through
LooksMenu, a moment after they are made (LooksMenu is reached through Papyrus, about a frame a value).
Without the DLL, everything above keeps working.

- **Rules by name and faction, and a name blacklist** — OBody's keys and OBody's priority, in
  `F4SE/Plugins/Silhouette/Silhouette_presetDistributionConfig.json`, which lists every key, written out:
  the defaults, plus a few entries for known mods (Eli's armour compendium: which of its armours count as
  heavy). The plugin reads what the generator compiles from it, not the file: after editing it, run the
  generator and install what it writes. A name is the NPC record's, as OBody reads it. BodyGen carries
  every rule it can (form ids, plugins, races); the plugin applies the rest. Someone a rule gave one of
  several presets keeps it while the rule still lists it; *Back to random* draws from the rule again.
- **ORefit** — while someone is dressed: breasts held together and lifted, and nipples flattened under
  heavy clothes -- armour, jackets, coats, told by the item's name (`heavyWords` in the config; items can
  be named heavy or light too). The flattening shows only on outfits whose meshes carry the refit sliders
  (mod outfits built with them; no vanilla heavy outfit does). It only ever raises a slider, under a keyword of
  its own: the moment they undress they are exactly their own body. Removing `Silhouette.esp` takes every
  clothed shape off by itself, and without a working DLL the bridge takes them off the people around you.
  Nobody in power armour is refit. `<Preset>-Refit` BodySlide presets and OBody's outfit lists work as in
  OBody.
- **The NPC picker** — MCM hotkeys: aim at someone close enough to talk to, *Pick*, *Next*/*Previous*
  to try every preset on them live, *Keep* or *Cancel*. The MCM page *The NPC in your sights* gives a preset, a new random body, or names
  the one they have. A choice is kept like a rule's, and marked in LooksMenu, so a save made without the
  DLL keeps it (MCM's *Refresh* pressed without the DLL gives the body again without the mark).
- **Touch-up** — bodies an older build gave get the nipple and genital variety they lack, and lose any
  shaft slider (never part of a body); a value you take off afterwards stays off.
- **API** — `Silhouette:API`, OBody NG's function names (`GetPresetAssignedToActor`,
  `ApplyPresetByName`, `GenActor`, `ResetActorOBodyMorphs`, `SetORefit`, ...) and its events
  (`OnActorGenerated`, `OnActorNaked`, `OnActorRemovingClothes`, `OnORefitChanged`) on the bridge quest,
  plus `IsHeavilyDressed` for mods that raise nipples.

Requirements, in addition: Fallout 4 **1.10.163** with F4SE 0.6.23 (the plugin refuses other
runtimes), the **Microsoft Visual C++ 2015-2022 Redistributable 14.40 or newer** (x64), `Silhouette.esp`
enabled (light, no load-order slot), MCM for the picker. Build: `scripts/build-plugin.ps1` (the DLL, 400+
offline tests, the tools' own tests, and the plugin's own parser run on the generated files),
`scripts/build-papyrus.ps1`, then `scripts/deploy-dev.ps1` with the game closed -- it stages in place and
names any new file that waits for Vortex's Deploy. MCM > Silhouette > *How is Silhouette doing?* says what is
loaded and what is missing; the plugin logs to `Documents\My Games\Fallout4\F4SE\Silhouette.log`.

Removing it: disable `Silhouette.esp` and remove the files. Bodies stay as they are (they are
LooksMenu's); every clothed shape goes with the esp. **Never go back by installing an older
`Silhouette.esp`**: one without the refit keyword makes LooksMenu keep every clothed shape as the body
itself, for good. Remove Silhouette entirely instead, or remove only `Silhouette.dll` (the bridge then
takes the clothed shapes off).

## Requirements

- Fallout 4 with F4SE and **LooksMenu**, BodyGen enabled in `Data/F4SE/Plugins/f4ee.ini`
  (`[BodyMorph] bEnable=1`, `bEnableBodyGen=1` — the default).
- **BodySlide**, with your body — and your outfits — built from a **zeroed** preset ("CBBE Zeroed
  Sliders", "BT - Zero") with **Build Morphs** ticked. The generator checks and tells you if not.
- **MCM** (Mod Configuration Menu) for the character picker.
- Python 3 to run the generator (standard library only).

## Use

```
python tools/silhouette_gen.py                 # measure and report, write nothing
python tools/silhouette_gen.py --write         # write the BodyGen files, the MCM menu, the script source
powershell scripts/build-papyrus.ps1           # compile the character picker
python tools/verify_bodygen.py                 # prove the written files do what they claim
python tools/audit_builds.py                   # which bodies AND outfits are zeroed, and which are not
```

All three read the built meshes from Data by default. If BodySlide builds somewhere else (its
`OutputDataPath`), pass `--built <folder>` (repeatable) to check a rebuild **before** it is
deployed.

Install the `data/` folder as a mod, with `Silhouette.dll` under `F4SE/Plugins/` and every compiled script
from `build/papyrus/Silhouette/` under `Scripts/Silhouette/` -- the Player, Adopter, Bridge, API and DLL
scripts, since `Silhouette.esp`'s quests run them. `scripts/deploy-dev.ps1` stages exactly this;
`scripts/make-release.ps1` packs it, with this README and the licence under `F4SE/Plugins/Silhouette/` (S-63). **Run the generator
again whenever you add presets, rebuild a body
in BodySlide, or edit `Silhouette_presetDistributionConfig.json`** -- the game never reads that file
itself, only what the generator makes of it.

Options: `--no-partial` hands out only presets that fit fully; `--compensate` writes templates
relative to a base that is not zeroed; `--data` points at another `Data` folder; `--report file.json`
writes the full classification.

## How it decides

| | |
| --- | --- |
| Full fit | ≥ 95% of the preset's sliders exist on your body |
| Partial fit | 50–95%, and the preset declares your body's family (read from the full fits) or none |
| Left out | the rest; outfit-tuned variants ("(Outfit)", "Clothed"); zeroed presets |
| Base body | the reference mesh and preset that reproduce your built `.nif` exactly |

The LooksMenu and BodySlide behaviour all of this relies on is written up, from their source, in
[docs/bodygen-format.md](docs/bodygen-format.md). Decisions and their evidence:
[docs/decisions.md](docs/decisions.md).

## Credits

OBody NG (Aietos and contributors) for the design this follows. LooksMenu (expired6978) and
BodySlide (ousnius, Caliente) for the tools it feeds — this project reads their source to get their
behaviour right, and ships none of it.

## Licence

GPL-3.0.
