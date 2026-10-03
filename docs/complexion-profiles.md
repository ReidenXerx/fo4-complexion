# Complexion: who gets what (draft for the owner, 2026-10-02)

Built from what is installed and tagged (tools/overlay_tags.py): 1158 usable female templates, 409 male.
Held back from random distribution: poor quality (247), lore-breaking (67: superheroes, real brands).

## Two layers, one budget

Everyone gets at most **6** overlays (C-5). The budget is filled in this order:

1. **The universal layer** (C-2), the same odds for every group:

   | | female | male |
   | --- | --- | --- |
   | pubic hair (112 styles) | 75% | (none installed) |
   | body hair (TBOS, 4) | - | 40% |
   | moles (11) | 40% | (none installed) |
   | nipple detail (Titkit, 26) | 35% | - |
   | acne (7) | 8% | - |

   The pubic hair STYLE follows the group: wild and full for raiders and the Pack, trimmed for Operators and the
   Institute, anything for settlers.

2. **The feature layer**: how many features a person has depends on their group, and so do the kinds and the
   style they are drawn from.

## The groups (by faction, as Silhouette's faction pools match them)

`count` is the chance of 0 / 1 / 2 / 3 / 4 features.

| group | count 0/1/2/3/4 | features drawn from | style of the tattoos |
| --- | --- | --- | --- |
| Settlers and everyone else | 55/30/12/3/0 | small tattoos 80%, a scar 20%; tan lines or sunburn (C-15) | floral, animal, script, geometric; small |
| Raiders | 5/15/35/30/15 | tattoos 55%, scars and burns 25%, grime 15%, brands 5% | crude, skull, tribal, the raider emblem; any size |
| Disciples | 5/15/30/30/20 | tattoos 45%, scars and wounds 40%, grime 15% (C-15: their ritual cuts and bloody handprints) | skull, script, crude |
| Pack | 5/20/35/30/10 | tattoos 70%, scars 20%, grime 10%, body paint (C-15) | animal, tribal; large pieces |
| Operators | 20/45/30/5/0 | tattoos 70%, nails 30% | pin-up, geometric, realistic art, script, gambling (C-15) |
| Gunners | 25/45/25/5/0 | tattoos 60%, scars 40% | military, skull, the Gunners emblem |
| Triggermen | 30/45/20/5/0 | tattoos 80%, scars 20% | script, pin-up, crude (prison ink), gambling (C-15) |
| Brotherhood | 70/25/5/0/0 | scars 50%, tattoos 50% | military, the BoS emblem only |
| Minutemen | 55/35/10/0/0 | tattoos 75%, scars 25% | the Minutemen emblem, military, script, floral |
| Railroad | 65/30/5/0/0 | tattoos 80%, scars 20% | the Railroad mark (tiny), geometric |
| Children of Atom | 20/50/25/5/0 | tattoos 60%, burns and scars 40% | the Atom emblem, religious, geometric |
| Institute | 95/5/0/0/0 | a tiny Institute emblem, nails | - |
| Vault 81 (C-15) | 40/45/15/0/0 | tattoos 60%, scars 40% | the Vault-Tec gear and Vault 81's number, script, geometric; small |

## Composition rules (what keeps it from looking random)

- **One style per person**: a style is drawn first from the group's list, and 3 of 4 tattoos come from it.
- **Variety over repetition**: the second feature of the same kind is half as likely as the first, the third a
  quarter. Two tattoos never share a region, and only one large or full piece per person.
- **Emblems only for members**: a Gunners skull only on a Gunner, a Vault-Tec gear only on a vault dweller.
- **Nothing lore-breaking or poor** at random. Adult and degrading pieces: see the open question.
- **Unique NPCs**: hand-set looks, like Silhouette's named bodies (a list to write, from their lore).
- **Rapport add-on**: a persona shifts the counts (e.g. a wild temperament +1 feature, a prim one -1).
