"""Complexion's FOMOD installer, written into a release folder (nexus-tools/docs/FOMOD-STANDARD.md, the owner's
house standard of 2026-10-01; Complexion 0.1.0 is built under it).

    python tools/fomod_pack.py <release folder> <version>

What it writes, in <release folder>/fomod/:
- ModuleConfig.xml: the install refused unless LooksMenu.esp is active and the game is 1.10.163 or newer (the only
  requirements a FOMOD can see in both Vortex and MO2 -- F4SE, Runtime Database and MCM are checked by the plugin
  in game and listed on the Nexus page); every top-level entry of the release folder installed as it is (read
  from the folder, so the installer and the archive cannot disagree). Pages, as the standard has them (rule 4 and
  4a, owner 2026-10-01): first "Checking your setup", ONE option holding the whole checklist; then one page per
  feature, its card and text shown without a click (MO2 highlights a page's first control, Vortex shows the first
  selected option of the first group -- so one Required option, alone in its group); last, a note shown only when
  AAF is missing.
- info.xml, images/*.jpg (the cards at 1000 px), and screenshot.png (MO2 shows that, not moduleImage).

Then it validates ModuleConfig.xml against tools/fomod/ModuleConfig5.0.xsd -- the schema Vortex itself validates
with (Nexus-Mods/fomod-installer, XmlScript5.0.xsd, GPL-3.0; one stray space in a type name,
type=" xs:string", taken out: .NET reads past it, lxml does not) -- and checks that every image and
every source the installer names exists. Any failure exits non-zero: scripts/make-release.ps1 packs nothing.
"""
import html
import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
XSD = ROOT / 'tools' / 'fomod' / 'ModuleConfig5.0.xsd'
IMG = ROOT / 'docs' / 'img'
SCHEMA = 'http://qconsulting.ca/fo3/ModConfig5.0.xsd'  # exactly: Vortex reads the version out of this text

# What Complexion does: (name, picture in docs/img, plain-text description). Facts as README.md has them.
FEATURES = [
    ('Who they are decides', 'groups.jpg',
     'Every NPC gets skin overlays the first time you meet them, and keeps them, chosen for who they are: raiders '
     'inked, scarred and grimy; settlers mostly plain; the Brotherhood clean but for a scar and its own mark; the '
     'Institute almost untouched. Twelve faction groups and everyone else, each with its own odds and styles.'),
    ('One look, not a pile', 'composition.jpg',
     'Never more than six overlays on anyone, one style per person, never three of a kind, no two tattoos on one '
     'spot, and a faction emblem only on its own people. Lore-breaking and poor pieces are never handed out.'),
    ('The named people', 'characters.jpg',
     '59 named characters have a look of their own, from their stories: Cait scarred from the Combat Zone, Piper '
     'all but plain, Danse under the Brotherhood\'s mark, Fahrenheit inked.'),
    ('Its own marks', 'marks.jpg',
     'Complexion paints 699 overlays of its own for the CBBE and male bodies: a realism layer (areolas, moles, '
     'freckles, birthmarks, stretch marks, body and pubic hair, tan lines, scars of every kind), traditional flash '
     'tattoos, bruises, grime and blood. Each fades out before the neck and wrist seams.'),
    ('Choose by hand', 'window.jpg',
     'Aim at anyone, or no one for yourself, and press the window\'s hotkey (set it in MCM > Complexion). They stand '
     'still, undressed, and the window lists every overlay that fits them by category, with a search: Complexion\'s '
     'own with pictures, every pack\'s by name. A click puts one on, live, and the camera goes to where it sits. '
     'Random rolls a look, Apply keeps it, Cancel puts back what they had, clothes included. It is how the player '
     'gets overlays: the player is never given a random look.'),
    ('Your packs, read the way LooksMenu reads them', 'packs.jpg',
     'Packs are optional. Complexion ships no other author\'s overlays, but hands out the ones you installed '
     'alongside its own. About 1,900 templates of '
     '16 popular packs are tagged from their pictures; a pack it does not know is left alone.'),
    ('Cheap, and kind to other mods', 'cheap.jpg',
     'One decision per NPC, one rebuild, ever: no cloak, no waits, no faction scans in Papyrus. Overlays other mods '
     'put on someone (AAF, Rapport) are kept and draw on top; nobody is touched in an AAF scene; the player, the '
     'dead and children never.'),
]
# Rule 4a: every requirement on one option, so the whole list shows at once. "found" is plain fact on this page: the
# install is refused before it when LooksMenu is missing.
SETUP = ('Your setup',
         'LooksMenu: found -- its overlays are what Complexion hands out.\n'
         'F4SE: check this yourself -- runs every DLL mod (f4se.silverlock.org).\n'
         'Runtime Database: check this yourself -- finds the game\'s functions on old-gen, next-gen and Anniversary (Nexus 108394).\n'
         'MCM: check this yourself -- the switches and the buttons.\n'
         'Body: CBBE or CBBE 3BBB for women (any BodySlide preset); the vanilla male body or BodyTalk for men. The vanilla female body is not supported: marks land in the wrong places.\n'
         'LooksMenu overlay packs: optional -- Complexion paints its own, and hands out the packs you have alongside.\n'
         'Random Overlay Framework: keep it for its tattoo packs -- with RobCo Patcher, Complexion switches its handing-out off; or uninstall it. Then MCM > Complexion > Clear every overlay, once.\n'
         'Complexion checks the rest in game and says what is missing.')
AAF_NOTE = ('AAF is not active',
            'Without AAF there are no AAF scenes to wait for; everything works.')
# Shown when CBBE's plugin is not active: women's overlays are drawn on CBBE's UV map (owner, 10-04: a player saw
# rectangles and outlines, most likely on the vanilla female body).
CBBE_NOTE = ('CBBE is not active',
             'Complexion\'s overlays for women are made for CBBE\'s body: on the vanilla female body they land in the wrong '
             'places (stray rectangles and outlines). Install CBBE or CBBE 3BBB, any BodySlide preset. Men need the vanilla male body '
             'or BodyTalk.')
# C-11: shown only while ROF's plugin is active. Its tattoo packs (Invictusblade's) need that plugin, so it stays;
# Complexion's RobCo Patcher ini switches ROF's handing-out off -- which needs RobCo Patcher.
ROF_NOTE = ('Random Overlay Framework is active',
            'Keep it if you use its tattoo packs: they need its plugin. Complexion switches ROF\'s handing-out off through '
            'RobCo Patcher, so install RobCo Patcher too; Complexion says in game if ROF still hands overlays out. '
            'Not using its packs? Uninstall ROF instead. Either way, after loading your save press MCM > Complexion > '
            'Clear every overlay once, outside any AAF scene.')


def esc(text):
    return html.escape(text, quote=True)


def option(name, description, image=None, flag='shown'):
    picture = f'\n              <image path="fomod\\images\\{image}"/>' if image else ''
    return f'''            <plugin name="{esc(name)}">
              <description>{esc(description)}</description>{picture}
              <conditionFlags><flag name="{flag}">1</flag></conditionFlags>
              <typeDescriptor><type name="Required"/></typeDescriptor>
            </plugin>'''


def module_config(entries):
    installs = []
    for e in entries:
        kind = 'folder' if e.is_dir() else 'file'
        installs.append(f'    <{kind} source="{esc(e.name)}" destination="{esc(e.name)}" priority="0"/>')
    def page(step, group, opt, visible=''):
        return f'''    <installStep name="{esc(step)}">{visible}
      <optionalFileGroups order="Explicit">
        <group name="{esc(group)}" type="SelectAll">
          <plugins order="Explicit">
{opt}
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>'''
    pages = [page('Checking your setup', 'Requirements', option(SETUP[0], SETUP[1], flag='setup'))]
    pages += [page(n, n, option(n, d, img)) for n, img, d in FEATURES]
    pages.append(page('Note: CBBE', 'Read this', option(CBBE_NOTE[0], CBBE_NOTE[1], flag='note_cbbe'), '''
      <visible>
        <dependencies operator="Or">
          <fileDependency file="CBBE.esp" state="Missing"/>
          <fileDependency file="CBBE.esp" state="Inactive"/>
        </dependencies>
      </visible>'''))
    pages.append(page('Note: Random Overlay Framework', 'Read this', option(ROF_NOTE[0], ROF_NOTE[1], flag='note_rof'), '''
      <visible>
        <fileDependency file="INVB_OverlayFramework.esp" state="Active"/>
      </visible>'''))
    pages.append(page('Note: AAF', 'Read this', option(AAF_NOTE[0], AAF_NOTE[1], flag='note_aaf'), '''
      <visible>
        <dependencies operator="Or">
          <fileDependency file="AAF.esm" state="Missing"/>
          <fileDependency file="AAF.esm" state="Inactive"/>
        </dependencies>
      </visible>'''))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- GENERATED by tools/fomod_pack.py (nexus-tools/docs/FOMOD-STANDARD.md). Edit the tool, not this file. -->
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="{SCHEMA}">
  <moduleName>Complexion</moduleName>
  <moduleImage path="fomod\\images\\groups.jpg"/>
  <moduleDependencies operator="And">
    <gameDependency version="1.10.163.0"/>
    <fileDependency file="LooksMenu.esp" state="Active"/>
  </moduleDependencies>
  <requiredInstallFiles>
{chr(10).join(installs)}
  </requiredInstallFiles>
  <installSteps order="Explicit">
{chr(10).join(pages)}
  </installSteps>
</config>
'''


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    out, version = pathlib.Path(sys.argv[1]), sys.argv[2]
    entries = sorted((e for e in out.iterdir() if e.name.lower() != 'fomod'), key=lambda e: e.name.lower())
    if not entries:
        sys.exit(f'{out} holds nothing to install')
    fomod = out / 'fomod'
    (fomod / 'images').mkdir(parents=True, exist_ok=True)
    for _name, image, _d in FEATURES:
        src = IMG / image
        if not src.exists():
            sys.exit(f'no picture {src}')
        pic = Image.open(src).convert('RGB')
        pic.resize((1000, round(1000 * pic.height / pic.width)), Image.LANCZOS).save(fomod / 'images' / image, quality=86)
    Image.open(IMG / 'groups.jpg').convert('RGB').resize((1000, 563), Image.LANCZOS).save(fomod / 'screenshot.png')
    config = module_config(entries)
    # UTF-8 with a BOM: both managers read it (Vortex detects it, MO2 retries encodings).
    (fomod / 'ModuleConfig.xml').write_text(config, encoding='utf-8-sig')
    (fomod / 'info.xml').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<fomod>
  <Name>Complexion</Name>
  <Author>Dudu'sButt</Author>
  <Version>{esc(version)}</Version>
  <Website>https://www.nexusmods.com/fallout4</Website>
  <Description>Skin overlays for every NPC, chosen for who they are.</Description>
</fomod>
''', encoding='utf-8-sig')

    from lxml import etree
    schema = etree.XMLSchema(etree.parse(str(XSD)))
    doc = etree.parse(str(fomod / 'ModuleConfig.xml'))
    if not schema.validate(doc):
        sys.exit('ModuleConfig.xml fails the 5.0 schema:\n' + '\n'.join(str(e) for e in schema.error_log))
    for el in doc.iter('image', 'moduleImage'):
        if not (out / el.get('path').replace('\\', '/')).exists():
            sys.exit(f'the installer shows {el.get("path")}, which is not in the release')
    for el in doc.iter('file', 'folder'):
        if not (out / el.get('source')).exists():
            sys.exit(f'the installer installs {el.get("source")}, which is not in the release')
    print(f'fomod: {len(entries)} entries installed as they are, the setup page, {len(FEATURES)} feature pages, AAF note; '
          f'valid against {XSD.name}')


if __name__ == '__main__':
    main()
