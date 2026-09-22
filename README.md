# Silhouette

OBody NG's body distribution, for Fallout 4. Every NPC gets one of your BodySlide presets the first
time you meet them, and keeps it.

**Status: Phase 1** — a generator that writes LooksMenu BodyGen files. There is no plugin and no
runtime code yet; LooksMenu's own BodyGen does the work at run time. Phase 2 (an F4SE plugin) adds the
in-game picker, ORefit, run-time rules and an API. What maps where:
[docs/obody-feature-map.md](docs/obody-feature-map.md).

## What it does that a hand-written BodyGen file does not

It **measures your install** instead of assuming it.

- **Which presets can do anything.** A preset whose sliders your body's `.tri` does not have is a
  silent no-op. Silhouette reads the `.tri` and hands out only presets that move your body — on the
  machine it was written on, 27 of 120 presets (Fusion Girl, Atomic Beauty on a CBBE body) were left
  out.
- **What your base body already has baked in.** BodyGen adds on top of the mesh on disk, so if you
  built your body with anything but Zeroed Sliders, every NPC preset stacks on it. Silhouette fits
  your built body against BodySlide's reference mesh and names the preset it was built from — exactly
  ("CBBE Chubby", 0.005% unexplained) — then writes every template relative to it. **You do not need to
  rebuild anything**, and your own character keeps the body it has.
- **What it wrote.** `tools/verify_bodygen.py` reads the files the way LooksMenu reads them and
  builds every body they can produce: each lands within 0.031 units of its preset.

It also never randomises the player, never re-rolls an NPC you have already met, and leaves zeroed
presets out of the random pool as OBody does.

## Requirements

- Fallout 4 with F4SE and **LooksMenu**, BodyGen enabled in `Data/F4SE/Plugins/f4ee.ini`
  (`[BodyMorph] bEnable=1`, `bEnableBodyGen=1` — the default).
- **BodySlide**, with your body built with **Build Morphs** ticked (that writes the `.tri`).
- Python 3 to run the generator (standard library only).

## Use

```
python tools/silhouette_gen.py                 # measure and report, write nothing
python tools/silhouette_gen.py --write         # write data/F4SE/Plugins/F4EE/BodyGen/Loose/*.ini
python tools/verify_bodygen.py                 # prove the written files do what they claim
```

Install the `data/` folder as a mod. **Run the generator again whenever you add presets or rebuild a
body in BodySlide.**

Options: `--no-partial` hands out only presets that fit fully; `--no-compensate` writes absolute
values (they stack on whatever the base has baked in); `--data` points at another `Data` folder;
`--report file.json` writes the full classification.

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
