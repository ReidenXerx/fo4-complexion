# Complexion: decisions

What is settled and why. Numbered C-#; a later entry may amend an earlier one, never silently.
Research behind them: [complexion-research.md](complexion-research.md).

## C-1: Complexion replaces Random Overlay Framework (owner, 2026-10-02)

ROF stacks overlays on every load, costs a lot, and hands out random overlays in any combination; its
faction rules are buggy and slow too. Complexion keeps ROF's purpose and avoids each of these failures
(research: the done-check that never passes, single-uid removal, a rebuild per category, the faction
else-if chain per load).

## C-2: Who someone is decides their overlays (owner, 2026-10-02)

- Every kind of overlay can go to anyone; **how likely each kind is depends on who they are**. Raiders get a
  lot of tattoos, scars and marks; settlers look ordinary. Each faction has its own odds per category.
- **A universal layer** goes to everyone regardless of faction, and often: moles, pubic hair, skin essentials
  and features.
- **Unique looks** for noticeable NPCs, from their lore and vibe (as Silhouette's named bodies).
- **The whole composition is weighted**, not only each category's odds: no overcrowding, and the count spread
  across different kinds; three different overlays rather than three of the same kind, even when the odds
  would say so.
- **Rapport integration** (an add-on): Rapport's temperament personas shift the odds.
- Categories handed out by default: skin detail, tattoos, body and pubic hair, nails. The player is never
  randomised.

## C-3: Other mods' overlays are kept; Complexion owns only its own (owner, 2026-10-02)

Complexion records which entries it added. When it changes an NPC it rebuilds the list keeping every foreign
entry. It must rebuild (RemoveAll, then add everything back, then one Update), never remove a single entry,
because LooksMenu's single Remove can hand out a live uid again. ROF is detected and the player is asked to
remove it; a one-time button clears ROF's leftovers.

## C-5: How many, and the rough marks (owner, 2026-10-02)

- The count of overlays is drawn per faction (settlers typically 1-3, raiders 3-6; a unique NPC gets what
  their look needs), under one hard ceiling of **6** per NPC. Each overlay is a copy of the skin mesh plus a
  4096² texture, rebuilt on every load and outfit change.
- Bruises, spank and whip marks, dirt and blood: none of the installed packs has them. First find Nexus packs
  that do; if there are none worth using, Complexion makes its own.
- Searched 2026-10-02 (Nexus pages read): **none exist as body overlays on Nexus.** The nearest are face-only
  bruises (Real Bruises 63730, no asset use), wrist and surgery scars, Brotherhood brands (broken on
  next-gen), freckles and tans as skin overrides or baked textures. ROF's spank and whip marks come from
  LoversLab packs, not Nexus. So Complexion makes its own rough marks.

## C-6: Living beside AAF and every other overlay mod (2026-10-02, from AAF's scripts)

AAF keeps the uids LooksMenu gives it: `AAF_MainQuestScript.addOverlays` sends them to its DLL
(`OVERLAY_ID`), and `removeOverlays` / `updateOverlayAlpha` later act by those uids. Rapport's sweat goes
through AAF (`ApplyOverlaySet`), so it is held the same way. Therefore:
- **Never rebuild an NPC while another mod may hold uids on them**: not during an AAF scene (the Busy check
  Silhouette already has), and only when the plan changes (once per NPC in practice). A rebuild between scenes
  is safe: AAF asks again for its next set.
- **Check every Add**: after AAF's single Removes, LooksMenu can hand Complexion a uid that is still live, and
  the new entry is lost. After adding, `GetAll` must show each of ours; if one is missing, the NPC is rebuilt
  clean (RemoveAll, re-add everything) once.
- **Ours sit underneath**: Complexion's entries take NEGATIVE priorities (LooksMenu draws lower first, under
  higher). AAF numbers its sets from 0 upward, so sweat and the like always draw over our skin detail and
  tattoos. Within ours, bottom to top: skin detail, hair, tattoos, nails.

## C-7: The groups, adult pieces, and men (owner, 2026-10-02)

- The faction table and composition rules in [complexion-profiles.md](complexion-profiles.md) are approved
  as drafted. They live in one data file (data/profiles.json), retuned there.
- Adult and degrading pieces (slave stamps and barcodes, chains, sexual tattoos) go to raiders' captives,
  and to raiders and the Nuka-World gangs themselves at low odds. One MCM switch turns all of it off.
- Men's basics (moles, scars, grime, pubic hair) are made by Complexion together with the rough marks:
  the installed packs give men only body hair and tattoos.

## C-8: Composition happens in the game, from the player's own packs (2026-10-02)

Complexion cannot ship other authors' overlays, and every player has different packs. So the plugin reads the
installed overlays.json the way LooksMenu does, joins them with Complexion's shipped tag database (tags are
keyed by pack and template id), and composes each NPC's look from data/profiles.json. A template the tag
database does not know is never handed out at random (fail-closed); a player can add tags for their own packs
in an include file. A tool runs the same composition over thousands of rolls to prove the odds, caps and
variety rules hold.

## C-9: Complexion paints its own rough marks and men's basics (2026-10-02, from C-5 and C-7)

tools/paint/ paints them on the body in 3D and bakes them into the body's own UV map, read straight out of the
NIF the game loads (FemaleBody.nif shape CBBE, MaleBody.nif shape BaseMaleBody:0): every texel knows the 3D point
and normal it lands on, so a bruise is a blob around a point on the body, crossing UV seams whole, and whip marks
cross the back. No guessed layout. Templates: fresh and fading bruises, light and heavy grime, dried blood with
drips and spatter, fresh whip welts and healed lash scars, spank marks (a handprint), and for men moles, scars
(plain and stitched) and pubic hair (full, trimmed, with a trail). BC3 with mipmaps, 1024 for soft marks and
2048 for fine ones; the material is a BGEM the game already draws (INVB's), its paths swapped. LooksMenu loads them
from Overlays\Complexion.esp\overlays.json.

The profiles gain a feature kind `rough` (bruises, welts and spank marks, dried blood) for raiders, the gangs,
captives and Gunners -- weights taken from their other kinds, so each group's feature COUNT stays as approved --
and men get the universal layer women have: pubic hair 60%, moles 30% (C-2's "generic" overlays).

## C-10: Named characters get looks of their own (2026-10-02, from C-2)

The 60 named characters Silhouette knows (its tools/pool/characters.json, record by record) each have a look in
data/profiles.json "characters": their own count, kinds, styles and emblems, drawn from their lore (Cait scarred
and bruised from the Combat Zone, Piper all but plain, Danse scarred under the Brotherhood's mark, Fahrenheit
inked). A character is matched by NPC record, or any template up its chain, BEFORE any faction. Ivy is left
untouched -- the owner's own companion, whose bud owns her look.

## C-11: ROF stays for its tattoo packs; Complexion switches its distributor off (owner, 2026-10-02)

Invictusblade's tattoo pack (~990 templates, the biggest) has INVB_OverlayFramework.esp as a master, and LooksMenu
loads a pack's overlays only while its plugin is loaded: uninstalling ROF loses them. So ROF stays installed and
Complexion turns its hands off, without touching its files or anything a save depends on: a RobCo Patcher ini
(F4SE/Plugins/RobCo_Patcher/race/Complexion_ROF.ini) adds ROF's own "already done" keywords to the Human and Ghoul
races -- kw_SpellWorked (Spread_Overlays' guard) and kw_Overlay_1 + kw_Overlay_2 (Overlay_Manager's full skip,
corpses included). An actor answers HasKeyword for its race's keywords, so ROF exits for everyone after one wait.
Rejected: emptying ROF's ability's effects in memory, or removing it from the races -- a save that already holds
the ability's active effect stores which effect runs, and could find none. What remains of ROF: 119 idle quests,
its MCM pages, and a load-time update routine that its own Performance Settings limit to new versions. The plugin
checks at the first poll that the three keywords are on the Human race and says so either way.

## C-12: Complexion's marks multiply the skin (measured in game, 2026-10-03)

Our first material copied INVB's: alpha blending (SRC_ALPHA / INV_SRC_ALPHA), which Fallout 4 draws unlit -- pale
healed scars glowed like neon in a dark corner; with the BGEM's "effect lighting" switched on, the marks did not
show at all. porcOverlays' moles and scars, which draw right, MULTIPLY: blend DEST_COLOR / ZERO, so the frame is
skin x texture x base colour x scale. Complexion's materials now copy porc's header with base colour 1,1,1 and
scale 2: each texel stores the factor the skin is multiplied by, times 1/2; off the marks and off the UV islands it
is exactly neutral grey. A mark darkens (grime, bruises, blood, moles, hair) or lightens (old scars) the skin under
it, lit and shadowed with it, on any skin tone. Textures are BC1 (no alpha needed). Shared note:
fo4-overlay-bgem-multiply.

**0.1.1 (a player's report, 2026-10-04):** BC1 cannot store 0.5. The neutral lands on (132, 130, 132)/255 (5-6-5
bits), so every overlay multiplied the WHOLE body by about 1.035 / 1.02 / 1.035. Six of them made the body about 20%
brighter and pinker than the face, which is another mesh. The materials' base colour is now (255/264, 255/260,
255/264), so the stored neutral multiplies by exactly 1.

**0.1.2 (the same player, after 0.1.1):** a patch remained around every mole, pimple and hair. Each mark's faint
soft edge (1-4 levels off neutral, up to ~20 texels wide) decoded to 126/129 in BC1 blocks, 2-5% darker than the
clean skin once 0.1.1's correction applied. The textures are now **BC7**, which holds 128 exactly. The base colour
is 255/256, and the worst 8x8-texel patch error is measured at 0.1-0.3% (it was 5%). tools/paint/check_encoding.py
decodes every shipped texture against its painting and fails above 1%. Twice the video memory of BC1, still far
below the 4K packs Complexion replaces.

## C-13: Complexion paints its own realism layer and drawn tattoos (owner, 2026-10-03)

To cut players' dependence on LoversLab packs, Complexion paints its own:
- **the realism layer:** skin detail (moles, freckles, birthmarks, pores, veins, stretch marks, pimples), female
  pubic hair in styles and colours, nipple and areola detail, and body hair for both sexes;
- **script tattoos:** words in open-licence tattoo fonts;
- **geometric and tribal tattoos:** bands, mandalas, barcodes, prison dots;
- **faction emblems:** drawn as vector shapes.

Art tattoos (illustrations) stay with the packs, which become optional additions: Complexion works complete with
none installed. All of it is painted on the body in 3D and baked into its own UV map (C-9), multiplied onto the
skin (C-12); tattoos are projected decals from a point on the body, flat on the skin there.

## C-14: Rapport's vulgar persona wears lewd marks; ex-captives among raiders (owner, 2026-10-03)

- NPCs whose Rapport persona is "vulgar" (Rapport:Core.PersonaOf, a hash of the form id, about a quarter of
  everyone; some pinned, e.g. Cait) get crude, explicit lewd marks on top of their look: "ENTRY", "INSERT HERE",
  "CUM HERE", "FREE USE", "OPEN 24/7" with an arrow down to the genitals; "Back Door", "TIP JAR", "CUM DUMP" over
  the arse; "SLUT", "WHORE", "SPREAD ME", "BITCH" on the buttocks; "RIDE ME", "FUCK ME" on the inner thighs;
  tally marks. "Don't be too soft." data/profiles.json "personas": 90% of them, one to three marks, drawn after
  the everyday layer and before the features, so the cap cannot crowd them out.
- Adult content: the MCM adult switch turns every one of them off. Rapport stays optional: the bridge asks it
  through Complexion:Persona, a script of its own on the bridge's quest, so without Rapport only that script fails
  to load. Ivy stays untouched (C-10).
- PROPERTY, SOLD and OWNED are also crude ink: a raider whose adult roll passes may wear them -- a captive who
  joined the raiders.

## C-15: Four more sets: rough life, faction flavour, ordinary skin, wrapped tattoos and nails (owner, 2026-10-03)

The owner chose all four proposed sets. All painted in 3D as C-9/C-13, multiplied onto the skin (C-12):
- **Captives and rough life** (tools/paint/life.py): rope marks and shackle chafe around the wrists and ankles, a
  collar's chafe, grip bruises (upper arms; hips from behind), cigarette burns, bite marks, hickeys, lipstick kisses,
  words in marker pen ("NEXT", "USED", "10 CAPS", "SLAVE", "CUM RAG"...). The sexual and degrading ones are adult
  (the MCM switch). Rapport's vulgar persona step now draws any KIND wearing its style, not only tattoos, so its
  NPCs can also get hickeys, kisses and marker words (both composers; parity checked).
- **Faction flavour:** the Disciples' ritual cuts and bloody handprints (emblem `disciples`), the Children of Atom's
  radiation sores and an Atom cut as a scar (`atom`), bullet, shrapnel, laser and burn scars for anyone hard-living,
  the Pack's body paint (emblem `pack`, feature kind `paint` = tag kind `makeup`), Gunners kill tallies, gamblers'
  ink (style `gambling`: Triggermen and Operators), and Vault 81 tattoos for a new group `vault81` (its citizen and
  guard factions). Emblems keep each faction's own marks on its members (C-7).
- **Ordinary life:** tan lines (T-shirt, tank top, bikini, shorts) and sunburn -- a new tag kind `tan`, feature kind
  `sun` for settlers, Minutemen and Gunners; mud on the legs; age spots, varicose veins, cellulite and surgery
  scars in the universal skin and scar pools; men's back hair, happy trails and more pubic colours; women's
  unshaved underarms.
- **Wrapped tattoos:** armbands, an anklet, a garter and sleeves wrap all the way round the limb (decals.wrap: a
  cylinder about the limb's own axis, the design repeated a whole number of times so it meets itself).
- **Nails:** on the hands mesh (LooksMenu slot 4, as the packs' nails). Found on the mesh, not guessed: the back of
  each finger's last bone, the nail's facing measured from the female hands texture, where nails are drawn pale
  (tools/paint/hands.py). Polish colours, chipped polish, dirty nails.

## C-16: Every mark fades out before the neck and wrist seams (owner, 2026-10-03)

A body overlay covers only the body mesh, which stops at the neck and the wrists, where the head and hands meshes
take over. Seen in game: sunburn over a man's torso and arms ended in a hard line against his pale head and hands.
So every body template fades to nothing over the last ~3 units (4 cm) before those seams -- "cheaply fixes seams".
The seams are the body shape's open edges (UV splits welded), measured: a loop at each wrist and the neck opening
(tools/paint/seams.py); the female body's crotch opening is not a seam with another mesh and is left alone. Marks
that belong AT a seam keep their edge: the collar's chafe and the rope and shackle marks.

## C-17: Our own art tattoos -- traditional flash; the LoversLab packs become optional (owner, 2026-10-03)

The owner: "we can even handle full replacement of all LoversLab dependencies with our own overlays", and chose
"flash set, packs optional". The packs were the only source of art tattoos (animals, florals, skulls, pin-ups,
cartoons), so without them those faction styles ran thin. Complexion now draws its own in American-traditional
flash -- bold black outline, flat pigments, whip-shading -- the style a wasteland tattooist would ink, and the one
that can be drawn as clean vector art (tools/paint/flash.py): roses, skulls, a skull and crossbones, daggers, a heart
with a banner (MOM, TRUE LOVE, NUKA), swallows, an anchor, snakes, a spider and its web, the nautical star,
lightning, the mushroom cloud, the radiation sign, a Nuka-Cola cap, cherries, an eye, flames, a geometric wolf, an
eagle, a koi, a butterfly, a revolver, a grenade, a tombstone, an eight ball, a compass -- each at one or two classic
spots, styled to match the faction tables. They carry colour (decals were single-ink), multiplied onto the skin.
Photo-realistic pieces and pin-ups stay with the packs, which remain supported as optional variety; with our flash in
place ROF no longer has to stay installed for its packs (C-11), the player's choice.

## C-18: Body places come from measured landmarks, never assumed heights (owner review, 2026-10-03)

Reviewing the breast overlays the owner called "especially important" showed the areolas off-centre (a woman's
"most forward point" is the front of the breast, not the nipple) and the upper-body anchors at assumed heights: the
"chest" at 0.80 (under the bust on CBBE, whose nipples are at 0.857), the "shoulder" on the side of the breast, the
"nape" between the shoulder blades. tools/paint/marks.landmarks measures each body once -- the nipple tips (the vertex
ring standing out most from its neighbourhood along the local normal), the crotch, the torso's top -- and derives the
chest, upper back, nape, shoulder, underbust, navel, belly, lower back, hip and thigh from them. Every anchor and
painter that places by height uses them; the leg spots centre on the leg. Rule: a new place on the body is measured
on the mesh, and checked on a render, before anything is painted there.

## C-19: An overlay window, ported from Silhouette's picker (owner, 2026-10-04)

The owner asked for Silhouette's picker window (S-79) in Complexion, and chose (poll 2026-10-04):
- **target:** NPCs AND the player ("Them" = the NPC under the crosshair, "Me" = the player -- the player is never
  randomised, so this is how they give themselves overlays);
- **contents:** every tagged, usable overlay -- Complexion's own and the installed packs' -- by category, with search;
- **preview:** live on the target (the camera frames them; Cancel undoes everything) AND thumbnail pictures now.
Built as Silhouette's is (its S-79 lessons carried over): an ActionScript 3 SWF compiled by Flex, opened by F4SE's
custom-menu API from Papyrus, the panel and Bridge talking through UI.Invoke and external events; native camera and
crosshair from the plugin. What differs: multi-select (toggle overlays on and off, several per category) instead of
one preset, and a hand-picked look is the NPC's decision from then on (never re-rolled, C-4) until rolled again.

The owner's first use (2026-10-04) and the fixes:
- **The camera goes to the mark.** Putting an overlay on moves the camera close to where it sits, and *Whole body*
  goes back. The spots are measured by tools/paint/thumbs.py: the centroid, normal and spread of the texels each
  template changes. Arm spots are re-hung from the mesh's 45-degree arms to the idle pose. Other packs' overlays
  use their tagged region, and a wide mark frames the whole body.
- **Categories** had never filtered. Papyrus returned the category in another case: the plugin missed its map and
  the panel dropped the answer. The fix: the plugin lower-cases the category, and pages are matched by a request
  number, never by an echoed string.
- **The wheel** arrives as a stream of CameraZUp/CameraZDown under the free camera. One flick turns one page.
- **Pictures:** ONE 4096 atlas per sex, because the second 2048 atlas's pictures did not show. The atlas layout is
  part of the build name.

## C-20: One body hair colour per person, matching the head (owner poll, 2026-10-04)

The owner's photo showed a dark-haired man with dark pubic hair and a ginger chest stripe: the composer picked each
hair overlay on its own. Now:
- **The person's family.** The plugin reads their head hair colour from the NPC record (TESNPC::headRelatedData ->
  hairColor, up the face template chain; checked on the player first, with the other members). It maps the colour
  to a family through profiles.json hair_colours: the game's 22 natural colours, by editor id, resolved offline by
  tools/make_data.py.
- **The templates' family.** Every pubic_hair and body_hair tag carries hair (tools/paint/hair.py). Ours come from
  the colour their painter got. The packs' come from their pictures, the real textures, for packs whose material
  draws them as they are; porcPubes from the colour its names state.
- **The rule.** A family accepts the same or darker, never another hue: brown takes brown, dark brown and black;
  ginger takes ginger and auburn; grey only grey. A hair template whose colour nobody could tell is never handed out.
- **Unknown colours.** Another mod's colour or a dye rolls one family per person, so all their hair still matches.
- **Old saves.** A look decided before this (co-save v3) is checked once, when the person is next seen. If its hair
  clashes with the head, it is decided again. A look chosen by hand stays.
- **The "sternum" chest pattern** was a narrow even band down to the navel and read as a painted stripe. It is now a
  ragged patch over the breastbone, thinning into a faint trail.

## C-21: Who someone is shapes the whole look: place, rough living, age, skin (owner, 2026-10-04)

The owner approved five improvements, plus one rule of their own: the nasty marks belong to the Commonwealth's
margins, not its elite ("DC citizens ... kinda elite of Commonwealth"). In profiles.json and both composers:
- **Places as groups.** "Everyone else" was one bucket. It is now nine groups by their game factions, after the
  gangs and factions: Diamond City Security, Diamond City, Covenant, Goodneighbor, the Atom Cats, caravans, Bunker
  Hill, scavengers and drifters, farmers and workshop settlers. 22 groups in all; "settlers" keeps whoever is left.
- **Squalor.** Each group (and each named character) has the percent of its people who live rough. One roll per
  person: only they get a nasty template (tools/paint/traits.py marks 100 of them):
  - grime, dirt, blood and open wounds;
  - pustules and body acne;
  - fresh bruises, fresh cigarette burns and radiation sores;
  - welts and chafe.

  Measured (compose.py --simulate):

  | People with a nasty mark | Groups |
  | --- | --- |
  | 0% | Diamond City, its Security, Covenant, BoS, Institute, Vault 81 |
  | 1–6% | settlers, farmers, caravans, Minutemen |
  | 22% | Goodneighbor |
  | 44–54% | raiders, Disciples, captives, scavengers |
- **The universal layer by group.** universal scales the base odds per kind (percent of the base): little acne
  for the Institute and BoS, trimmed body hair for BoS, the Institute and operators, more for raiders and drifters.
- **Age.** Grey hair (C-20) means old: acne and pimples never; age spots, varicose veins and cherry angiomas only
  then.
- **Skin tone.** The plugin reads the record's body tint (TESNPC::bodyTintColor, the QNAM the game tints the body
  with) as pale, light, olive or dark. The thresholds come from the game's records: Cait and the default are
  pale, Deacon light, Amari olive, Preston dark. Freckles, sunburn and redness go on pale and light skin only; tan
  lines up to olive; the slate-blue birthmark on olive and dark.
- **Life history** sits in the groups' kinds: guards, caravans and gunners carry more scars, Diamond City and
  Covenant fewer.
- **Old saves (co-save v5).** A look decided before these rules is checked once, when the person is next seen and
  read. If one of its marks is one they would not get now, the look is decided again. A look chosen by hand stays.
- **Reads wait for the layout check.** Nobody is read before the layout check passes, so hair and skin are never
  read as unknown.

## C-4: Rules carried over from Silhouette (2026-10-02)

- One decision per NPC, made once and kept; nothing re-rolls on load.
- One rebuild per NPC per change: all adds, then a single Update.
- No Papyrus polling, waits or per-NPC faction scans. The plugin decides; the bridge only carries out.
- The dead are left alone (Silhouette S-81).
- Fail closed: a template that is not installed is never handed out; a missing pack shrinks the pool, and
  the shrink is logged.
