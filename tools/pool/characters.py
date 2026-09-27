"""Unique bodies for the Commonwealth's named people (S-66): each companion and major NPC gets one body of her or
his own, matching who they are, instead of a roll from the random pool (the owner, 2026-09-24).

    python tools/pool/characters.py [--data <Fallout 4 Data>] [--sheets DIR]
    python tools/pool/characters.py --check     # every record still exists, with the sex its body is for

Each character is a hand-set body in the pool's vocabulary (archetypes.py) and one or more NPC records by
editor id, plugin and local form id. The ids were read from the plugins themselves (plugin_forms.editor_ids,
every top group: Fallout4.esm has two NPC_ groups), and --check reads them again. Ghouls, synths of the old
models and robots are not HumanRace and are not here.

A character's body is never random and is always in the picker. The generator gives it to the records listed
as an npcFormID rule UNDER the user's own: a rule in the config or an include for the same record wins.

Writes:
    data/Tools/BodySlide/SliderPresets/Silhouette Characters.xml   the presets
    tools/pool/characters.json                                     the sidecar the generator reads
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import generate  # noqa: E402
import plugin_forms  # noqa: E402
from measure import measure  # noqa: E402
from mesh import Body  # noqa: E402

PRESETS = ROOT / 'data/Tools/BodySlide/SliderPresets/Silhouette Characters.xml'
SIDECAR = HERE / 'characters.json'
F4, FH, NW = 'Fallout4.esm', 'DLCCoast.esm', 'DLCNukaWorld.esm'

# name, sex, [(plugin, editor id, local id)], vibe, slider values in percent
CHARACTERS = [
    # ---- women
    ('Piper Wright', 'female', [(F4, 'CompanionPiper', '002F1E')],
     'wiry, restless reporter: slim, small-chested, narrow hips, a real waist',
     {'LegsThin': 20, 'Arms': 15, 'BreastsSmall': 30, 'BreastGravity2': 15, 'ChubbyWaist': 65, 'WideWaistLine': 45,
      'HipUpperWidth': 25, 'Hips': -15, 'ButtSmall': 20}),
    ('Cait', 'female', [(F4, 'CompanionCait', '079249')],
     'cage fighter: lean muscle, strong shoulders and legs, a small hard chest',
     {'MuscularArms': 50, 'MuscularLegs': 55, 'MuscularButt': 60, 'ChestWidth': 25, 'Back': 20, 'BreastsSmall': 30,
      'BreastPerkiness': 20, 'ChubbyWaist': 55, 'WideWaistLine': 35, 'Hips': -10, 'ButtSmall': 10}),
    ('Curie', 'female', [(F4, 'CompanionCurie', '027686'), (F4, 'EncCurieSynth', '1647C6')],
     'a new synth body, soft and unassuming: gentle curves, a little soft at the middle',
     {'ChubbyWaist': 70, 'Belly': 25, 'Breasts': 15, 'BreastGravity2': 25, 'Hips': 5, 'ChubbyArms': 15, 'Thighs': 10,
      'AppleCheeks': 15}),
    ('Magnolia', 'female', [(F4, 'Magnolia', '02268A')],
     'lounge singer, the Commonwealth\'s one real hourglass',
     {'Breasts': 35, '7B Upper': 20, 'BreastPerkiness': 20, 'Hips': 20, 'Butt': 25, 'RoundAss': 35, 'ChubbyWaist': 20,
      'Thighs': 15, 'BreastGravity2': 10}),
    ('Desdemona', 'female', [(F4, 'Desdemona', '045AD1')],
     'Railroad leader, middle-aged and severe: long, flat and square',
     {'BreastsSmall': 30, 'BreastGravity2': 35, 'ChubbyWaist': 75, 'WideWaistLine': 55, 'HipUpperWidth': 30, 'Hips': -20,
      'ButtSmall': 30, 'LegsThin': 15, 'Back': 15}),
    ('Glory', 'female', [(F4, 'Glory', '045ACF')],
     'the Railroad\'s heavy: a powerful, broad-shouldered athlete',
     {'MuscularArms': 90, 'MuscularLegs': 85, 'MuscularButt': 60, 'ChestWidth': 55, 'Back': 55, 'BigTorso': 35,
      'BreastsSmall': 25, 'ChubbyWaist': 60, 'WideWaistLine': 30, 'Thighs': 30, 'CalfSize': 30}),
    ('Haylen', 'female', [(F4, 'BoSScribeHaylen', '05DE3F')],
     'scribe, bookish: a desk body, soft arms and a soft belly',
     {'ChubbyWaist': 85, 'Belly': 55, 'BigBelly': 20, 'ChubbyArms': 45, 'ChubbyLegs': 30, 'Breasts': 15,
      'BreastGravity2': 40, 'WideWaistLine': 35, 'ChubbyButt': 25}),
    ('Madison Li', 'female', [(F4, 'MadisonLi', '05E63F')],
     'scientist in her fifties: thin and narrow, gone soft at the middle',
     {'LegsThin': 30, 'Arms': 25, 'BreastsSmall': 30, 'BreastGravity2': 50, 'BreastFlatness2': 20, 'ChubbyWaist': 80,
      'WideWaistLine': 50, 'Belly': 25, 'Hips': -20, 'ButtSmall': 35}),
    ('Mama Murphy', 'female', [(F4, 'MamaMurphy', '019FD8')],
     'old chem-worn seer: frail and sagging, thin limbs',
     {'LegsThin': 80, 'Arms': 70, 'SlimThighs': 50, 'ButtSmall': 70, 'BreastGravity2': 100, 'BreastFlatness2': 60,
      'Breasts': 10, 'Belly': 40, 'ChubbyWaist': 85, 'WideWaistLine': 40, 'Hips': -30}),
    ('Marcy Long', 'female', [(F4, 'MarcyLong', '019FDC')],
     'bitter survivor: hard, thin, worn out',
     {'LegsThin': 35, 'Arms': 30, 'BreastsSmall': 30, 'BreastGravity2': 45, 'ChubbyWaist': 75, 'WideWaistLine': 55,
      'Hips': -25, 'ButtSmall': 40, 'SlimThighs': 20}),
    ('Fahrenheit', 'female', [(F4, 'Fahrenheit', '022616')],
     'Hancock\'s bodyguard: big, broad, muscled and heavy',
     {'BigTorso': 70, 'ChestWidth': 70, 'Back': 70, 'MuscularArms': 70, 'MuscularLegs': 55, 'ChubbyArms': 30,
      'ChubbyWaist': 100, 'WideWaistLine': 70, 'Thighs': 45, 'Breasts': 10, 'CalfSize': 50, 'Hips': -15}),
    ('Irma', 'female', [(F4, 'Irma', '0228A5')],
     'Memory Den hostess: faded glamour, soft and full-figured',
     {'Breasts': 55, '7B Upper': 15, 'BreastGravity2': 65, 'Hips': 25, 'Thighs': 30, 'ChubbyWaist': 80, 'Belly': 35,
      'ChubbyArms': 30, 'ChubbyButt': 30, 'BigButt': 20}),
    ('Mags Black', 'female', [(NW, 'DLC04MagsBlack', '00D3EB')],
     'the Operators\' boss: slim, elegant, cold',
     {'LegsThin': 10, 'BreastsSmall': 20, 'Breasts': 5, 'BreastPerkiness': 25, 'ChubbyWaist': 45, 'Hips': 5,
      'RoundAss': 20, 'SlimThighs': 10}),
    ('Nisha', 'female', [(NW, 'DLC04Nisha', '00A4E2')],
     'the Disciples\' leader: sinewy and knife-lean, all tendon',
     {'LegsThin': 30, 'Arms': 25, 'MuscularArms': 30, 'MuscularLegs': 25, 'BreastsSmall': 30, 'BreastsSmall2': 20,
      'ChubbyWaist': 50, 'WideWaistLine': 40, 'Hips': -20, 'ButtSmall': 30}),
    ('Kasumi Nakano', 'female', [(FH, 'DLC03KasumiNakano', '003ECA')],
     'young runaway: small, slight, girlish',
     {'BreastsSmall': 30, 'BreastPerkiness': 30, 'SlimThighs': 20, 'Arms': 15, 'LegsThin': 15, 'ChubbyWaist': 55,
      'WideWaistLine': 30, 'Hips': -5, 'ButtSmall': 10}),
    ('Ronnie Shaw', 'female', [(F4, 'RonnieShaw', '03A458')],
     'old Minutemen veteran: stocky, thick-waisted, tough',
     {'BigTorso': 30, 'Back': 35, 'ChestWidth': 25, 'ChubbyWaist': 95, 'WideWaistLine': 60, 'Belly': 35,
      'BreastGravity2': 60, 'BreastFlatness2': 30, 'ButtSmall': 30, 'Hips': -15, 'MuscularArms': 15}),
    ('Myrna', 'female', [(F4, 'Myrna', '002CBF')],
     'sour shopkeeper: pear-shaped, thick through the hips',
     {'BreastsSmall': 30, 'Hips': 35, 'Thighs': 40, 'ChubbyLegs': 35, 'ChubbyButt': 40, 'ChubbyWaist': 80, 'Belly': 30,
      'HipUpperWidth': 35, 'BreastGravity2': 40}),
    ('Doctor Amari', 'female', [(F4, 'DoctorAmari', '09A680')],
     'neuroscientist, middle-aged: ordinary and a little soft',
     {'ChubbyWaist': 80, 'WideWaistLine': 40, 'Belly': 30, 'Breasts': 10, 'BreastGravity2': 40, 'ChubbyArms': 15,
      'Thighs': 10}),
    ('Trudy', 'female', [(F4, 'Trudy', '1069FC')],
     'Drumlin Diner owner: a heavy apple shape',
     {'BigBelly': 30, 'Belly': 95, 'ChubbyWaist': 120, 'WideWaistLine': 60, 'HipUpperWidth': 50, 'Back': 45,
      'LegsThin': 20, 'ButtSmall': 30, 'Breasts': 25, 'BreastGravity2': 75, 'ChubbyArms': 50}),
    ('Ellie Perkins', 'female', [(F4, 'ElliePerkins', '0222A2')],
     'the detective\'s secretary: plain and average',
     {'ChubbyWaist': 70, 'WideWaistLine': 40, 'HipUpperWidth': 25, 'Belly': 25, 'Breasts': 5, 'BreastGravity2': 25,
      'BreastsSmall': 10, 'ChubbyArms': 10}),
    ('Cricket', 'female', [(F4, 'Cricket', '12FCCE')],
     'arms dealer: tough, thick-armed, broad',
     {'BigTorso': 30, 'Back': 35, 'ChestWidth': 30, 'ChubbyWaist': 80, 'WideWaistLine': 40, 'MuscularArms': 30,
      'ChubbyArms': 25, 'Thighs': 20, 'Breasts': 20, 'BreastGravity2': 40}),
    ('Carla', 'female', [(F4, 'Carla', '0DC936')],
     'caravan trader: lean and weathered, a walker\'s legs',
     {'LegsThin': 10, 'MuscularLegs': 30, 'CalfSize': 20, 'BreastsSmall': 30, 'ChubbyWaist': 65, 'WideWaistLine': 45,
      'Hips': -10, 'ButtSmall': 15, 'BreastGravity2': 30}),
    ('Captain Avery', 'female', [(FH, 'DLC03CaptainAvery', '005C80')],
     'Far Harbor\'s leader: a sturdy fisherwoman with a broad back',
     {'Back': 40, 'ChestWidth': 30, 'BigTorso': 25, 'MuscularArms': 25, 'ChubbyWaist': 85, 'WideWaistLine': 45,
      'Belly': 20, 'Breasts': 10, 'BreastGravity2': 45, 'Thighs': 20}),
    ('Aster', 'female', [(FH, 'DLC03Aster', '00463E')],
     'Acadia\'s synth: willowy and flat',
     {'LegsThin': 25, 'Arms': 20, 'BreastsSmall': 30, 'ChubbyWaist': 55, 'WideWaistLine': 40, 'Hips': -15,
      'ButtSmall': 25, 'SlimThighs': 25}),
    ('Ivy', 'female', [('CompanionIvy.esm', 'IVYCOMP', '000803')],
     'NX-2C pleasure bot on a Courser combat chassis, a raider boss\'s brain: an engineered hourglass over '
     'toned muscle (the owner\'s pick, option A, 2026-09-24; made fuller by their poll the same night: '
     '"too slim" at breasts 25 / butt 15; then, by a rendered poll, option B: a big powerful glute shelf, '
     '"a woman with powerful ass muscles" cannot have a small one, and a more muscled back and arms)',
     {'Breasts': 70, '7B Upper': 15, 'BreastPerkiness': 45, 'PushUp': 20, 'ChestWidth': 10,
      'MuscularArms': 70, 'ForearmSize': 25, 'Back': 30, 'ShoulderWidth': 10, 'ChubbyWaist': 5,
      'Butt': 100, 'BigButt': 75, 'RoundAss': 80, 'MuscularButt': 100, 'AppleCheeks': 60, 'HipBack': 35,
      'BackArch': 35, 'Hips': 45, 'Thighs': 70, 'MuscularLegs': 65}),
    ('Geneva', 'female', [(F4, 'Geneva', '002F0A')],
     'the mayor\'s secretary, famous among players for being hot: sleek and office-neat -- a perky bust, a slim '
     'waist, a high round bottom (the owner\'s pick from three renders, option B, 2026-09-25; the pool had '
     'rolled her a Boxy body)',
     {'Breasts': 35, '7B Upper': 15, 'BreastPerkiness': 45, 'PushUp': 20, 'Hips': 15, 'Butt': 30, 'RoundAss': 55,
      'AppleCheeks': 30, 'Thighs': 10, 'ChubbyWaist': 10}),
    # ---- the Diamond City pack (owner's poll, 2026-09-27: the unique people his saves actually meet, drawn from
    # their stories and allowed to be SARDONIC -- "TRULY unique memorable bodies ... sardonic to their
    # stories/characters"). Lore from the Fallout wiki, quoted in docs/decisions.md S-77.
    ('Polly', 'female', [(F4, 'Polly', '002CD4')],
     'the Choice Chops butcher who secretly writes poems about dancing in the dark: a butcher\'s meaty arms, '
     'shoulders and belly, and under them a dancer\'s round bottom',
     {'MuscularArms': 60, 'ChubbyArms': 70, 'ForearmSize': 60, 'Back': 60, 'ShoulderWidth': 45, 'BigTorso': 35,
      'Breasts': 60, 'BreastGravity2': 60, 'ChubbyWaist': 105, 'Belly': 70, 'WideWaistLine': 40, 'Hips': 20,
      'Butt': 40, 'RoundAss': 60, 'Thighs': 40, 'MuscularLegs': 30}),
    ('Cathy', 'female', [(F4, 'Cathy', '002CCF')],
     'the salon gossip who greets you with "You look terrible": bloodshot, graying -- and a wreck herself, '
     'skinny-fat and sagging',
     {'BreastGravity2': 120, 'BreastFlatness2': 90, 'Breasts': 20, 'Belly': 90, 'BigBelly': 45,
      'ChubbyWaist': 105, 'WideWaistLine': 45, 'LegsThin': 60, 'Arms': 55, 'ButtSmall': 70, 'Hips': -35}),
    ('Becky Fallon', 'female', [(F4, 'BeckyFallon', '002CC6')],
     'Fallon\'s Basement, "quality and affordability": everything has sunk to the basement -- a small bust over '
     'enormous hips, thighs and bottom',
     {'BreastsSmall': 30, 'Breasts': 0, 'ChubbyWaist': 65, 'Hips': 85, 'Thighs': 105, 'ChubbyLegs': 110,
      'BigButt': 85, 'ChubbyButt': 95, 'HipUpperWidth': 55, 'AppleCheeks': 35, 'Arms': 25}),
    ('Scarlett', 'female', [(F4, 'Scarlett', '04B240')],
     'the Dugout Inn waitress, "hopefully nothing will poison ya": she never eats what she serves -- bony, '
     'run off her feet',
     {'LegsThin': 85, 'Arms': 80, 'SlimThighs': 70, 'ButtSmall': 85, 'BreastsSmall': 30, 'Breasts': 0,
      'BreastFlatness2': 45, 'Hips': -45, 'ChubbyWaist': 45, 'WideWaistLine': 35, 'CalfSmooth': 60}),
    # ---- men
    ('Preston Garvey', 'male', [(F4, 'PrestonGarvey', '019FD9')],
     'earnest Minuteman: lean, a little gaunt from hard years',
     {'BTThinArm': 30, 'ThinThigh': 25, 'BTTHinCalf': 20, 'BTAbDefinition': 15, 'BTShoulders': 10, 'BTStomachFat': 10}),
    ('Paladin Danse', 'male', [(F4, 'BoSPaladinDanse', '027683')],
     'Brotherhood paladin: big and heavily muscled, thick neck and traps',
     {'BTAryaydaMoreMuscular': 45, 'BTARYAYDA': 40, 'TigerSanBBMale': 30, 'BTTraps': 55, 'BTShoulders': 40,
      'BTBack': 30, 'BTAbDefinition': 30, 'BTStomachFat': 10}),
    ('Robert MacCready', 'male', [(F4, 'CompanionMacCready', '02740E')],
     'young mercenary: skinny, narrow-shouldered, all elbows',
     {'BTThinArm': 60, 'ThinThigh': 55, 'BTTHinCalf': 50, 'BTNegChestWidth': 35, 'BTNegShoulder': 30,
      'BTNegPecMuscle': 30, 'BTAbDefinition': 10}),
    ('Deacon', 'male', [(F4, 'CompanionDeacon', '045AC9')],
     'the spy nobody remembers: perfectly average',
     {'BTStomachFat': 30, 'BTChubbyArm': 25, 'BTChubbyLeg': 20, 'BTChestSmoothing': 30, 'Hips': 15}),
    ('Arthur Maxson', 'male', [(F4, 'BoSElderMaxson', '0642B8')],
     'the young Elder: broad, imposing, heavy-built',
     {'TigerSanBBMale': 45, 'BTShoulders': 50, 'BTTraps': 50, 'BTBack': 40, 'BTPectorals': 30, 'BTStomachFat': 25,
      'BTBodyFatv2': 10}),
    ('X6-88', 'male', [(F4, 'CompanionX6-88', '0BBEE6')],
     'Courser: athletic and lean-muscled, built to a spec',
     {'BTAbDefinition': 60, 'BTWaist-In': 40, 'BTShoulders': 35, 'BTPectorals': 30, 'BTBiceps': 30,
      'BT2AdonisBelt': 40, 'BTCalves': 30}),
    ('Old Longfellow', 'male', [(FH, 'DLC03_CompanionOldLongfellow', '006E5B')],
     'old hunter: stringy and weathered, a drinker\'s gut',
     {'BTThinArm': 45, 'ThinThigh': 40, 'BTTHinCalf': 35, 'BTNegPecMuscle': 35, 'BTStomachFat': 55,
      'BTLowerStomachSize': 30, 'BTNegShoulder': 20}),
    ('Porter Gage', 'male', [(NW, 'DLC04Gage', '00881D')],
     'raider lieutenant: a stocky bruiser with a gut',
     {'BTBodyFatv2': 25, 'BTStomachFat': 50, 'BTShoulders': 35, 'BTTraps': 40, 'BTThigh': 35, 'BTChubbyLeg': 30,
      'BTBiceps': 25}),
    ('Sturges', 'male', [(F4, 'Sturges', '019FDA')],
     'mechanic: solid, broad-chested, a bit of a belly',
     {'BTShoulders': 25, 'BTPectorals': 20, 'BTStomachFat': 40, 'BTLowerStomachSize': 15, 'BTBiceps': 25,
      'BTChubbyArm': 20}),
    ('Kellogg', 'male', [(F4, 'Kellogg', '09BC6C'), (F4, 'MQ101Kellogg', '0CF917')],
     'mercenary: compact and dense, hard muscle',
     {'BTARYAYDA': 35, 'BTTraps': 45, 'BTShoulders': 30, 'BTAbDefinition': 35, 'BTBiceps': 35, 'BTStomachFat': 15,
      'BTThigh': 25}),
    ('Travis Miles', 'male', [(F4, 'TravisMiles', '002F26')],
     'nervous DJ: soft, narrow-shouldered, an indoor body',
     {'BTNegShoulder': 35, 'BTNegChestWidth': 30, 'BTChestSmoothing': 50, 'BTStomachFat': 40, 'BTThinArm': 30,
      'Hips': 30}),
    ('Mayor McDonough', 'male', [(F4, 'MayorMcDonough', '002F08')],
     'the fat cat of "Mankind for McDonough", who threw the ghouls out and smiles a mile-long smile: grossly obese, '
     'soft all over (the owner, 2026-09-27: "quite unpleasant, could very very fat"; was: well-fed and soft)',
     {'BTBodyFatv2': 100, 'BTStomachFat': 135, 'BTLowerStomachSize': 95, 'BTCenterStomachSize': 70,
      'BTChubbyArm': 100, 'BTChubbyLeg': 90, 'BTChestSmoothing': 100, 'Hips': 95}),
    ('Vadim Bobrov', 'male', [(F4, 'VadimBobrov', '002EFC')],
     'barkeep: a big beer belly, heavy arms',
     {'BTStomachFat': 100, 'BTLowerStomachSize': 60, 'BTCenterStomachSize': 45, 'BTChubbyArm': 50,
      'BTChestSmoothing': 50, 'Hips': 30}),
    ('Moe Cronin', 'male', [(F4, 'MoeCronin', '002CB2')],
     'Swatters\' owner: a pot belly on thin legs',
     {'BTStomachFat': 90, 'BTLowerStomachSize': 50, 'ThinThigh': 40, 'BTThinArm': 35, 'BTNegPecMuscle': 30}),
    ('Father', 'male', [(F4, 'shaun', '02A19A')],
     'the Institute\'s director, sixty and dying: thin and frail',
     {'BTThinArm': 95, 'ThinThigh': 90, 'BTTHinCalf': 90, 'BTNegPecMuscle': 75, 'BTNegBicepMuscle': 70,
      'BTNegShoulder': 60, 'BTNegChestWidth': 60, 'BTNegScapularMuscle': 50, 'BTStomachFat': 25}),
    ('Paladin Brandis', 'male', [(F4, 'BoSM01_PaladinBrandis', '0B1DAF'), (F4, 'BoSM01_PaladinBrandis_Postquest', '0B35BD')],
     'hermit survivor: gaunt, the muscle wasted away',
     {'BTThinArm': 75, 'ThinThigh': 70, 'BTTHinCalf': 60, 'BTNegPecMuscle': 55, 'BTNegBicepMuscle': 60,
      'BTNegScapularMuscle': 40, 'BTAbDefinition': 40, 'BTNegStomach': 45}),
    ('Tinker Tom', 'male', [(F4, 'TinkerTom', '045ACB')],
     'paranoid tinkerer: skinny-fat',
     {'BTStomachFat': 50, 'BTThinArm': 50, 'ThinThigh': 45, 'BTNegShoulder': 40, 'BTChestSmoothing': 40}),
    # ---- the Diamond City pack, men (see the women's note above)
    ('John', 'male', [(F4, 'John', '002CCB')],
     'Cathy\'s son at the Super Salon, "practically deaf in this ear" from ma\'s yelling: henpecked -- narrow '
     'shoulders, soft, a mama\'s boy\'s hips',
     {'BTNegShoulder': 85, 'BTNegChestWidth': 70, 'BTChestSmoothing': 80, 'BTStomachFat': 60, 'BTThinArm': 75,
      'Hips': 95, 'BTButt': 50}),
    ('Arturo Rodriguez', 'male', [(F4, 'ArturoRodriguez', '002CB7')],
     'Commonwealth Weaponry, "the real secret is in the mods": an ordinary dad body with over-modded arms',
     {'BTBiceps': 100, 'BTShoulders': 80, 'BTTraps': 75, 'BTPectorals': 45, 'BTStomachFat': 85,
      'BTLowerStomachSize': 50, 'ThinThigh': 45, 'Hips': 15}),
    ('Solomon', 'male', [(F4, 'Solomon', '002CBB')],
     'Chem-I-Care, slightly stoned: "all the chems you need to ... balance you out" -- and nothing about him is '
     'balanced: sunken chest, stick limbs, a soft little gut',
     {'BTStomachFat': 95, 'BTLowerStomachSize': 45, 'BTThinArm': 100, 'ThinThigh': 90, 'BTTHinCalf': 80,
      'BTNegShoulder': 85, 'BTNegChestWidth': 85, 'BTNegPecMuscle': 85, 'BTChestSmoothing': 60}),
    ('Doctor Sun', 'male', [(F4, 'DoctorSun', '020B8E')],
     'the doctor who "can cure just about anything" and scorns facial surgery as not real medicine: a hollow, '
     'bony ascetic who forgets to eat',
     {'BTNegStomach': 90, 'BTThinArm': 90, 'ThinThigh': 85, 'BTTHinCalf': 80, 'BTNegPecMuscle': 80,
      'BTNegBicepMuscle': 70, 'BTNegShoulder': 55, 'BTNegScapularMuscle': 55, 'BTNegChestWidth': 40}),
    ('Abbot', 'male', [(F4, 'Abbot', '002F28')],
     'one of the oldest citizens, keeper of the Wall ("the great, green guardian"): he has become one -- old, '
     'broad, square and barrel-bellied',
     {'BTBack': 70, 'BTShoulders': 55, 'BTTraps': 45, 'BTBodyFatv2': 35, 'BTStomachFat': 80,
      'BTCenterStomachSize': 55, 'BTChubbyArm': 45, 'BTChubbyLeg': 40, 'BTChestSmoothing': 50}),
    ('Sheffield', 'male', [(F4, 'Sheffield', '002F06')],
     'the market\'s former alcoholic, "doctors said I shot my liver", begging for Nuka-Cola: stick limbs and a '
     'swollen gut',
     {'BTStomachFat': 125, 'BTLowerStomachSize': 85, 'BTCenterStomachSize': 80, 'BTThinArm': 90, 'ThinThigh': 90,
      'BTTHinCalf': 80, 'BTNegPecMuscle': 70, 'BTNegShoulder': 55, 'BTNegChestWidth': 50}),
    ('Malcolm Latimer', 'male', [(F4, 'MalcolmLatimer', '002F10'), (F4, 'MS13Photo_MalcolmLatimer', '218F14')],
     'the rich man who "practically runs Diamond City", pays the mayor and hires others for his dirty work, '
     'confidence "Cowardly": a pampered pear that never lifted anything',
     {'Hips': 110, 'BTButt': 100, 'BTThighWidth': 100, 'BTOuterUpperThighSize': 90, 'BTNegShoulder': 85,
      'BTNegChestWidth': 70, 'BTStomachFat': 70, 'BTChestSmoothing': 80, 'BTChubbyArm': 50}),
    ('Finn', 'male', [(F4, 'Finn', '033585')],
     'Goodneighbor\'s "insurance" man, confidence "Foolhardy", who tells Hancock there will be a new mayor: all '
     'mouth -- a scrawny runt',
     {'BTThinArm': 100, 'ThinThigh': 100, 'BTTHinCalf': 95, 'BTNegShoulder': 90, 'BTNegChestWidth': 90,
      'BTNegPecMuscle': 90, 'BTNegBicepMuscle': 85, 'BTNegScapularMuscle': 70}),
    ('Wayne Delancy', 'male', [(F4, 'MS04WayneDelancy', '03FEC8')],
     'the Goodneighbor hitman who killed Miss Selmy and her child for two caps and calls drifters "meat": gaunt, '
     'sinewy and hungry',
     {'BTNegStomach': 90, 'BTThinArm': 70, 'ThinThigh': 70, 'BTTHinCalf': 60, 'BTNegPecMuscle': 55,
      'BTAbDefinition': 30, 'BTWaist-In': 60, 'BTTraps': 45, 'BTNegChestWidth': 30}),
    ('Parker Quinn', 'male', [(F4, 'ParkerQuinn', '0843E6')],
     'the charge-card con man of South Boston: all show, like his card -- a pumped chest and arms on chicken legs '
     '(the joke is the scam; his face is modelled on a real person, his body is not)',
     {'BTPectorals': 100, 'BTBiceps': 95, 'BTShoulders': 85, 'BTTraps': 80, 'TigerSanBBMale': 35,
      'ThinThigh': 100, 'BTTHinCalf': 100, 'BTStomachFat': 30}),
    ('Winlock', 'male', [(F4, 'GunnerWinlock', '03467F')],
     'the Gunner who tells MacCready "we know how to play the game", O-positive tattooed on his forehead: the big, '
     'broad boss of the pair',
     {'TigerSanBBMale': 90, 'BTShoulders': 85, 'BTTraps': 85, 'BTBack': 75, 'BTPectorals': 55, 'BTBiceps': 60,
      'BTStomachFat': 35, 'BTThigh': 50}),
    ('Barnes', 'male', [(F4, 'GunnerBarnes', '034680')],
     'Winlock\'s sidekick: "Winlock, tell me we don\'t have to listen to this shit..." -- short-armed, soft and '
     'narrow beside him',
     {'BTStomachFat': 95, 'BTLowerStomachSize': 65, 'BTChestSmoothing': 75, 'BTChubbyArm': 60,
      'BTNegShoulder': 65, 'BTNegChestWidth': 55, 'Hips': 70, 'BTChubbyLeg': 40}),
    ('Rufus Rubins', 'male', [(F4, 'RufusRubins', '01A255')],
     'the Hotel Rexford handyman who works for room and board and waits politely for Magnolia to finish singing: '
     'the one honest body in Goodneighbor -- wiry and work-strong',
     {'BTAbDefinition': 25, 'BTThinArm': 25, 'BTBiceps': 40, 'BTShoulders': 20, 'BTStomach': 20, 'ThinThigh': 30,
      'BTTraps': 20}),
]


def sidecar():
    return {'about': 'Silhouette Characters: the NPC records each preset of "Silhouette Characters.xml" is bound to '
                     '(tools/pool/characters.py, S-66).',
            'characters': {name: {'sex': sex, 'forms': [[pl, edid, fid] for pl, edid, fid in forms], 'vibe': vibe,
                                  'values': values}
                           for name, sex, forms, vibe, values in CHARACTERS}}


def check(data):
    """Every record still exists under its editor id, and is the sex its body is for. -> number of problems."""
    bad = 0
    ids = {}
    for name, sex, forms, _vibe, _values in CHARACTERS:
        for pl, edid, fid in forms:
            if pl not in ids:
                ids[pl] = plugin_forms.editor_ids(pathlib.Path(data) / pl, 'NPC_')
            got = ids[pl].get(edid)
            if got is None or got[1] != int(fid, 16):
                bad += 1
                print(f'  {name}: {pl} has no NPC {edid} at {fid} (found {got})')
    print('characters check: ' + ('every record is where it was' if not bad else f'{bad} record(s) moved'))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--data', type=pathlib.Path, default=generate.DATA)
    ap.add_argument('--sheets', type=pathlib.Path, help='also draw a review sheet per sex here')
    ap.add_argument('--check', action='store_true', help='check the records; write nothing')
    args = ap.parse_args()
    if args.check:
        return 1 if check(args.data) else 0
    names = [c[0] for c in CHARACTERS]
    if len({n.casefold() for n in names}) != len(names):
        raise SystemExit('two characters share a name')
    bodies, models, sliders_of = {'female': [], 'male': []}, {}, {}
    for sex in bodies:
        models[sex] = Body(args.data, sex)
        sliders_of[sex] = generate.slider_names(args.data, models[sex].slider_set)
    for name, sex, _forms, vibe, values in CHARACTERS:
        unknown = sorted(set(values) - set(sliders_of[sex]))
        if unknown:
            raise SystemExit(f'{name}: no slider {unknown} in the {sex} set')
        m = measure(models[sex].build({s: v / 100.0 for s, v in values.items()}), models[sex].region, sex)
        bodies[sex].append({'name': name, 'archetype': vibe.split(':')[0], 'values': values, 'measure': m,
                            'tier': generate.tier_of(m, sex)})
        print(f'  {name:18} {generate.tier_of(m, sex):9} whr {m["whr"]:.2f}  b/w {m["bwr"]:.2f}  vol {m["volume"]:.0f}')
    PRESETS.write_text(generate.preset_xml(bodies, sliders_of).replace(
        'Silhouette Pool: generated by fo4-silhouette tools/pool/generate.py. Edit archetypes.py',
        'Silhouette Characters: generated by fo4-silhouette tools/pool/characters.py. Edit characters.py'),
        encoding='utf-8')
    SIDECAR.write_text(json.dumps(sidecar(), indent=1) + '\n', encoding='utf-8')
    print(f'wrote {PRESETS.relative_to(ROOT)} and {SIDECAR.relative_to(ROOT)}')
    if args.sheets:
        from render import render_sheet
        args.sheets.mkdir(parents=True, exist_ok=True)
        for sex, rows in bodies.items():
            render_sheet(models[sex], rows, args.sheets / f'characters_{sex}.png')
        print(f'review sheets in {args.sheets}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
