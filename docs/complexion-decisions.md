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

## C-4: Rules carried over from Silhouette (2026-10-02)

- One decision per NPC, made once and kept; nothing re-rolls on load.
- One rebuild per NPC per change: all adds, then a single Update.
- No Papyrus polling, waits or per-NPC faction scans. The plugin decides; the bridge only carries out.
- The dead are left alone (Silhouette S-81).
- Fail closed: a template that is not installed is never handed out; a missing pack shrinks the pool, and
  the shrink is logged.
