# Overlay tags: what every template is (the schema of data/tags/*.json)

Each overlay template the scanner finds (tools/overlay_scan.py) is tagged once, from its picture (tools/
overlay_sheets.py). Names alone lie: "Pubic_Sperm1" is a tattoo design, "SvarogNLTheShortCut" is hair. Tags are
data, kept in the repo, and reviewed like code. A template with no tags is never handed out.

One JSON object per template, keyed by `<f|m>:<template id>`:

| field | values | meaning |
| --- | --- | --- |
| `kind` | `tattoo`, `scar`, `wound`, `burn`, `bruise`, `marks` (spank/whip/rope), `dirt`, `blood`, `mole`, `freckles`, `skin` (texture, pores, veins, stretch marks), `acne`, `birthmark`, `pubic_hair`, `body_hair`, `nipple`, `nails`, `makeup` (also body paint and lipstick), `brand`, `tan` (tan lines, sunburn; C-15), `other` | what it depicts |
| `regions` | `face`, `neck`, `shoulders`, `chest`, `breasts`, `belly`, `back`, `lower_back`, `pelvis`, `pubic`, `butt`, `arm_l`, `arm_r`, `hand_l`, `hand_r`, `leg_l`, `leg_r`, `feet`, `full_body` | where it sits, read from the whole-UV picture |
| `size` | `tiny` (a mole), `small` (palm-sized), `medium`, `large` (a whole back), `full` (most of the body) | coverage |
| `style` | for tattoos and brands: `tribal`, `crude` (prison/stick-and-poke), `military`, `emblem` (a faction or brand mark), `skull`, `animal`, `floral`, `geometric`, `script` (words), `religious`, `pinup`, `sexual`, `degrading` (slave/owned text), `lewd` (crude sexual words near the genitals; Rapport's vulgar persona, C-14), `gambling` (cards, dice, LUCKY, $; C-15), `cartoon`, `realistic_art` | the look, for matching to who wears it |
| `emblem` | `bos`, `minutemen`, `vault_tec`, `atom`, `institute`, `railroad`, `gunners`, `raiders`, `nuka`, `disciples`, `pack` (C-15), `other_fo` , `real_world` | a recognisable mark |
| `lore` | `fits`, `stretch`, `breaks` | `breaks`: real-world brands, superheroes, modern logos, anime -- never handed out at random |
| `adult` | true/false | explicit or degrading content; only for rules that ask for it |
| `quality` | `ok`, `poor` | `poor`: blurry, misaligned, cut off at a seam -- never handed out at random |
| `note` | free text, short | what it shows, in a few words |
