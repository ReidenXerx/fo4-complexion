# Complexion

Skin overlays for Fallout 4's NPCs, chosen for who they are: the replacement for Random Overlay Framework.

Every NPC gets overlays the first time you meet them, and keeps them. Raiders are inked, scarred and grimy;
settlers mostly plain, with a mole or a small tattoo; the Brotherhood clean but for a scar and its own mark; the
Institute almost untouched. Everyone gets an everyday layer -- moles, body hair, skin detail. Never more than six
on anyone, one style per person, never three of a kind, and a faction's emblem only on its own people.

**Status:** 0.1.0 in development. Not released.

## How it works

- **Your packs, Complexion's taste.** Complexion ships no overlays of other authors. It reads the LooksMenu
  overlay packs you have installed, the way LooksMenu loads them, and hands out only those it knows: about 1,900
  templates of 16 popular packs are tagged from their pictures (kind, body region, size, style, emblem, whether
  it fits the wasteland). Lore-breaking pieces (superheroes, real brands) and poor ones are never handed out.
- **Who they are decides.** Twelve groups by faction (raiders, the three Nuka-World gangs, Gunners, Triggermen,
  the Brotherhood, the Minutemen, the Railroad, the Children of Atom, the Institute, raiders' captives), and
  everyone else. Each has its own odds and styles: data/profiles.json.
- **Cheap.** One decision per NPC, made in the plugin; one rebuild per NPC, ever. No cloak, no waits, no per-NPC
  faction scans in Papyrus -- Random Overlay Framework's costs (docs/complexion-research.md).
- **Plays well with others.** Overlays other mods put on an NPC (AAF's, Rapport's sweat) are kept, and draw on top.
  Nobody is touched during an AAF scene. The player, the dead and children are never touched.

## The overlay window

Choose overlays by hand: aim at someone (or no one, for yourself) and press the window's hotkey (MCM >
Complexion), or use its buttons in the MCM. They stand still, undressed, framed by the camera, and the window
lists every overlay that fits them -- Complexion's own with a picture, other packs' by name -- by category, with a
search. A click puts one on or takes it off, live; Random rolls a look; Clear takes Complexion's off. Apply keeps
it as their look from then on; Cancel puts back exactly what they had, clothes included. It is the only way the
player gets overlays from Complexion: the player is never given a random look.

Putting one on takes the camera close to where it sits; *Whole body* takes it back. The mouse wheel, Page Up/Down
and the bumpers turn pages. The hotkey is unbound until you set it in the MCM. Up to 24 of Complexion's overlays at
a time. Other packs' overlays show by name, without a picture.

## Requirements

Fallout 4 1.10.163 (old-gen), 1.10.984 (next-gen) or 1.11.x (Anniversary), F4SE, Runtime Database, LooksMenu,
MCM, and LooksMenu overlay packs.

## Moving from Random Overlay Framework

Uninstall it, load your save, and press MCM > Complexion > *Clear every overlay* once (outside any AAF scene), then
save and load. Complexion puts its own looks back as you meet people.

## Building

See CLAUDE.md, "Build".

## Credits

LooksMenu's overlay system is expired6978's (F4SEPlugins, f4ee). The research into Random Overlay Framework read
Invictusblade's scripts to learn what not to do; none of its code or assets are in Complexion.
