# Complexion: what ROF does wrong, and what LooksMenu allows (research, 2026-10-02)

Complexion replaces Random Overlay Framework (ROF, Invictusblade, `INVB_OverlayFramework` 2.483). This file
records what was read, from where, so every design rule below can be re-checked.

Sources:
- ROF's 26 scripts decompiled with Champollion 1.3.2 (kept out of the repo, it is not our code:
  `D:\F4CustomMods\Complexion-research\rof-psc`), its ESP's records, MCM configs and inis, and those of
  "ROF Performance Settings v2".
- LooksMenu's source: expired6978/F4SEPlugins, `f4ee/` (OverlayInterface.cpp/.h, PapyrusOverlays.cpp, main.cpp,
  ActorUpdateManager.cpp). Its code targets 1.11.221 (AE); the OG build is LooksMenu 1.6.20.
- The overlay packs installed on the owner's machine (`D:\F4CustomMods\Complexion-research\inventory`).

## LooksMenu's overlays, from the source

- **Templates**: `F4SE\Plugins\F4EE\Overlays\<plugin file name>\overlays.json` for every loaded plugin, in load
  order, then `Overlays\Loose\*.json` alphabetically (LoadOverlayMods). A folder not named exactly after a
  plugin file is never read. Keys: `id`, `gender` (0 male, 1 female; anything above 1 is clamped to female, a
  missing one skips the entry), `name`, `slots[{slot, material}]`, `playable`, `transformable`, `sort`.
  `playable`/`transformable`/`sort` only feed the UI. Same id twice: later files overwrite the flags, the
  FIRST material per slot wins. A `.bgem` material makes an effect-shader layer, anything else a lighting one.
- **Per actor**: one priority multimap per actor form id per sex (equal priorities allowed, insertion order).
  An entry is uid, template, tint, UV offset/scale. Saved in LooksMenu's cosave (`OVRL`); an entry whose
  template is gone at load is **dropped silently**, so it is lost at the next save.
- **Papyrus** (`Overlays`): `Add`, `Set`, `Get`, `Remove`, `RemoveAll`, `GetAll`, `Update(actor)`, `ClearAll`.
  `Add`/`Remove`/`Set` change data only; nothing shows until `Update`, which tears down and rebuilds every
  overlay of that actor on the main thread. `Set` overwrites tint, offset and scale every time.
- **The uid bug**: `RemoveOverlay` never returns the uid to the free list, and the next uid is `size()+1`, so
  after removing ONE overlay the next `Add` can be handed a uid that is still live; the duplicate is ignored
  by `m_dataMap.emplace`. `RemoveAll` frees uids properly. (OverlayInterface.cpp GetNextUID 266-279,
  RemoveOverlay 310-335, RemoveAll 379-403.)
- **Cost**: each overlay is a clone of every skin-tint shape in its biped slot (slot 3 body, 4 hands), with its
  own material: N overlays = N extra draw calls per shape, plus the texture. Rebuilt on every 3D load, every
  equip change of that slot (the AttachSkinnedObject hook) and every `Update`. No per-frame cost, no cap.
- **Not overlays**: the head. Face tints are a different system (CharGenTint); no installed pack targets it.
- No C++ interface for other plugins: Papyrus and the character-creation Scaleform only.

## What ROF does, and where it breaks

- **Trigger**: RobCo Patcher gives Human and Ghoul races an ability; its effect runs `Spread_Overlays` on every
  NPC each time the effect starts (every load of them).
- **The stacking bug**: the "already done" check needs BOTH `kw_Overlay_1` AND `kw_Overlay_2`, but a run adds
  only one of them, so the full manager runs again on every load. Only the tattoo roll is guarded; the
  "unique" overlay is added again each time with no check for a duplicate, and the base skin override is
  re-applied. Its cleaners remove overlays one uid at a time, which is exactly LooksMenu's uid bug.
- **Choice**: a 50% master roll, then per category a 50% roll (times a modifier), then a uniform pick over all
  installed packs' ids flattened together. Categories are independent coin flips: nothing ties a
  person's tattoos, scars and hair into one look. "All" mode adds Back AND Chest together. Every tattoo shares
  one priority (2).
- **Factions**: an `IsInFaction` else-if chain over 20 slots, per NPC, per load; the Performance mod's own
  comment blames it for about 75% of post-load Papyrus stack overload.
- **Cost**: per NPC, several random `Utility.Wait`s of 0.1-2.5 s, an `Update` after EVERY category (each one a
  full rebuild), arrays built with ~20 `Game.IsPluginInstalled` calls x3 per category, repeat timers holding a
  thread in `WaitGameTime` per NPC per repeating category, and on every load (default `fUpdateOption`=2)
  ~25 quests stopped and restarted with 5.5 s of waits. Some arrays exceed Papyrus's 128-element limit.
- **Packs**: the ROF ESP hard-codes every supported pack's plugin name and template ids; a new pack needs an
  ESP edit. Corpses get overlays too.

## The installed overlays (owner's machine)

About 1,800 templates in 19 packs, all the same schema. Mostly tattoos (INVB ~990, porcTattoos 292, Render
128, LMBT 113, DNX 28, Rutah 47, RJs 6); skin detail (porcOverlays: moles 15, skin texture 20, scars 20,
pimples 10; Titkit nipple detail 28); hair (porcPubes 85, two pubic hair packs 55, TBOS male body hair 7);
nails (Nail Salon 48); CumOverlays 57 (not deployed); Rapport sweat 3 (folder `Rapport` matches no plugin
file, so LooksMenu never loads it). Female-only almost everywhere. No dirt, blood or bruise pack. Nearly every
texture is 4096x4096, many without mipmaps: ~16 MB of video memory per distinct overlay on screen.
