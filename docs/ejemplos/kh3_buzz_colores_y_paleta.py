"""Kingdom Hearts 3 Buzz (MMD/Blender rig) -> Toy Story 3 Buzz skeleton.

Same tables as mods/ts5_characters/maps/buzz_map.py (its docstring explains TORSO, DRIVE, WEIGHTS...), plus the
texture tables: the model comes in 15 meshes with one material each and the FBX links no textures, so MATERIALS says
which texture set (or solid colour) each FBX material uses.

Bones: 'bip_*_L' is Buzz's left (+x), '_R' his right (the right upper arm is spelled 'bip_upperarm_R'). The model and
the game both stand in a T pose with the wings out.
"""

PREFIX = 'kh3'
KEEP_PIECES = ['JetPack_Flame']        # the game's jetpack flames: this model has none

# the helmet's glass (6 meshes): the game has no see-through material for it, and keeps its own dome piece
SKIP_MATERIALS = ['New .001', 'New .002', 'New .003', '4', 'New .004', 'New .005']
# the shoulder's rubber: a thin sleeve between the arm's root (radius 9) and the armour's hole (10.6), from inside the
# chest out to the shoulder pivot. The game lowers the T-posed arms, and every way of weighting it showed it in game:
# with the arm a big dark disc swung out over the armour, half way a dark tube bulged from the joint, with the torso
# its outer rim stood up above the lowered arm. Without it the arm's root fills the hole in both poses.
SKIP_BONES = ['LArmRubber', 'RArmRubber']
# the game hides the wings by scaling WingLeft1/2 to 0.001 at the centre of the back (curves 'WingsOpenClose' in the
# .oct). Each wing's root sits in a slot in the jetpack's side, which then showed the background: the root (x < 22,
# inside the jetpack, which reaches 24.2) stays on the chest, so the shrunk wing's first triangles wall the slot off
WEIGHT_RAMP = {'L wing1': ('Spine3', 'WingLeft1', 0, 22, 27), 'R wing1': ('Spine3', 'WingRight1', 0, -22, -27)}
TEXTURES = {
    # most of the model is solid colours: whole parts have their uvs on one texel (KH3's shader tints them by the
    # mask m00), so 'solid' moves them to the palette. The mask's channels: R white/purple plastic, G skin, hood and
    # rubber, B green plastic, A grey parts and eye whites. The rubber's texel is pure black: dark grey like the
    # game's own Buzz instead.
    # No normal map: 0n00/0n01 (and 0o00/0o01) are laid out for KH3's own uvs, not this repainted atlas (only m00
    # matches it). With 0n00 the game showed screws and rings in the face and torso.
    'body': dict(d='n_ts202_0d00.tga', size=2048, nsize=16, solid=True,
                 mask='n_ts202_0m00.tga', mask_spec=(0.45, 0.12, 0.45, 0.3), recolor={(0, 0, 0): (65, 65, 72)}),
    'logo': dict(d='Anti logo.png', size=256, spec=0.4),
}
MATERIALS = {
    'buzz': 'body', 'torso': 'body', 'Wings': 'body',
    'New .007': 'logo',                 # the belt buckle
    'green': (40, 200, 60), 'red': (220, 30, 30),     # wing tip lights
    'New ': (25, 25, 25),
    'lambert1.001': (0, 128, 255), 'New .006': (255, 0, 0),
}

TORSO = ['bip_pelvis', 'pelvis_alt', 'bip_spine_0', 'bip_spine_1', 'bip_spine_2']
LANDMARKS = [('bip_pelvis', 'Hips'), ('bip_upperArm_L', 'BicepLeft'), ('bip_upperarm_R', 'BicepRight'),
             ('bip_neck', 'Neck'), ('bip_hip_L', 'ThighLeft'), ('bip_hip_R', 'ThighRight')]
SCALE_JOINTS = [('bip_pelvis', 'Hips'), ('bip_neck', 'Neck'), ('bip_head', 'Head'),
                ('bip_upperArm_L', 'BicepLeft'), ('bip_upperarm_R', 'BicepRight'),
                ('bip_lowerArm_L', 'ForearmLeft'), ('bip_lowerArm_R', 'ForearmRight'),
                ('bip_hand_L', 'HandLeft'), ('bip_hand_R', 'HandRight'), ('bip_hip_L', 'ThighLeft'),
                ('bip_hip_R', 'ThighRight'), ('bip_knee_L', 'CalfLeft'), ('bip_knee_R', 'CalfRight')]
FACE_ALIGN = [('L eye', 'EyeLeft'), ('R eye', 'EyeRight'), ('L brow b', 'BrowLeft'), ('R brow b', 'BrowRight'),
              ('CU lip', 'UpperLip'), ('CD lip', 'LowerLip'), ('LU cor', 'LipCornerLeft'),
              ('RU cor', 'LipCornerRight')]

DRIVE = {
    'bip_neck': ('bip_head', 'Neck', 'Head', {'aim_face': True}),
    'bip_head': (None, 'Head', None, {'face': True}),
}
UPPER_ARM = {'L': 'bip_upperArm_L', 'R': 'bip_upperarm_R'}
for s, t in (('L', 'Left'), ('R', 'Right')):
    DRIVE.update({
        'bip_hip_' + s: ('bip_knee_' + s, 'Thigh' + t, 'Calf' + t, {}),
        'bip_knee_' + s: ('bip_foot_' + s, 'Calf' + t, 'Foot' + t, {'aim_floor': True}),
        'bip_foot_' + s: (None, 'Foot' + t, None, {'floor': True}),
        UPPER_ARM[s]: ('bip_lowerArm_' + s, 'Bicep' + t, 'Forearm' + t, {}),
        'bip_lowerArm_' + s: ('bip_hand_' + s, 'Forearm' + t, 'Hand' + t, {}),
        'bip_hand_' + s: ('bip_middle_0_' + s, 'Hand' + t, 'Middle' + t + '1', {}),
    })

# the eyelids are shut in the rest pose (half-spheres around the eye bone): turned open around it
EYES = [('%s eye' % s, ['%sU eyelid %s' % (s, k) for k in 'abcdefg'], ['%sD eyelid %s' % (s, k) for k in 'abcdefg'])
        for s in 'LR']
EYE_MODE = 'rotate'
EYE_OPEN_TOP = 30
EYE_OPEN_BOTTOM = 40

WEIGHTS = {'blender_implicit': 'Hips', 'bip_pelvis': 'Hips', 'pelvis_alt': 'Hips', 'bip_spine_0': 'Spine1',
           'bip_spine_1': 'Spine2', 'bip_spine_2': 'Spine3', 'rubber1': 'Spine1', 'rubber2': 'Spine1',
           'rubber3': 'Spine2', 'backpack': 'Spine3', 'greenbutton': 'Spine3', 'redbutton': 'Spine3',
           'bigredbutton': 'Spine3', 'bluebutton': 'Spine3', 'torsobuttonL': 'Spine3', 'torsobuttonR': 'Spine3',
           'bip_neck': 'Neck', 'bip_head': 'Head', 'C brow': 'MidddleBrow',
           'CU lip': 'UpperLip', 'LU lip': 'UpperLip', 'RU lip': 'UpperLip',
           'CD lip': 'LowerLip', 'LD lip': 'LowerLip', 'RD lip': 'LowerLip',
           'C jaw': 'Jaw', 'C chin': 'Jaw', 'CD teeth': 'Jaw', 'C tongroot': 'Jaw', 'C tongtip': 'Jaw',
           'RArmButton': 'BicepRight'}
for s, t in (('L', 'Left'), ('R', 'Right')):
    WEIGHTS.update({'bip_hip_' + s: 'Thigh' + t, 'bip_knee_' + s: 'Calf' + t, 'bip_foot_' + s: 'Foot' + t,
                    'bip_toe_' + s: 'Toes' + t, 'bip_collar_' + s: 'Sternum' + t, UPPER_ARM[s]: 'Bicep' + t,
                    s + 'ArmRubber': 'Sternum' + t,          # left out (SKIP_BONES)
                    'bip_lowerArm_' + s: 'Forearm' + t, 'bip_hand_' + s: 'Hand' + t,
                    s + ' wing1': 'Wing' + t + '1', s + ' wing2': 'Wing' + t + '2',
                    s + ' eye': 'Eye' + t, s + ' weye': 'Eye' + t,
                    s + 'U cor': 'LipCorner' + t, s + 'D cor': 'LipCorner' + t})
    for f5, f3 in (('index', 'Index'), ('middle', 'Middle'), ('ring', 'Ring'), ('pinky', 'Pinky'), ('thumb', 'Thumb')):
        WEIGHTS['bip_%s_0_%s' % (f5, s)] = f3 + t + '1'   # the game spells them IndexLeft1, Index2Left, Index3Left
        WEIGHTS['bip_%s_1_%s' % (f5, s)] = f3 + '2' + t
        WEIGHTS['bip_%s_2_%s' % (f5, s)] = f3 + '3' + t
    for k in 'abcdefg':
        WEIGHTS['%sU eyelid %s' % (s, k)] = 'EyeLidTop' + t
        WEIGHTS['%sD eyelid %s' % (s, k)] = 'EyeLidBtm' + t
    for k in 'abcdefgh':
        WEIGHTS['%s brow %s' % (s, k)] = 'Brow' + t
WEIGHTS.update({'knee': 'CalfLeft', 'Rknee': 'CalfRight', 'armcover': 'ForearmLeft'})

FACE_BONES = {'EyeLidTopLeft', 'EyeLidBtmLeft', 'EyeLidTopRight', 'EyeLidBtmRight', 'EyeLeft', 'EyeRight'}
FACE = True
