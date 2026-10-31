"""Kingdom Hearts 3 Woody (MMD/Blender rig) -> Toy Story 3 Woody skeleton. See buzz_map.py here for the texture
tables and mods/ts5_characters/maps/buzz_map.py for the rest.

Bones: 'bip_*_L' is Woody's left (+x). The right thumb is numbered 1..3, the left 0..2. The 'adj' bones are helpers
around joints; 'leg * ankle adj 1' (a child of the knee) carries the whole boot shaft, so it goes with the calf (on
the foot, the shaft came away from the jeans in game). The game's Woody has no eye bones, so eyes and lids stay with
the head. The model has the hat twice ('22_hat_0+' is a copy for MMD physics): one is left out.
"""

PREFIX = 'kh3'
KEEP_PIECES = []

SKIP_MATERIALS = ['22_hat_0+', 'mmd_tools_rigid_0', 'mmd_tools_rigid_1']
TEXTURES = {
    'head': dict(d='Woody_Head_D.tga.png', n='Woody_Head_N.tga.png', size=1024, nsize=512, spec=0.15),
    'clothes': dict(d='Woody_Clothes_D.tga.png', n='Woody_Clothes_N.tga.png', size=1024, nsize=512, spec=0.08),
    'shirt': dict(d='Woody_Shirt_D.tga.png', n='Woody_Shirt_N.tga.png', size=1024, nsize=512, spec=0.08),
    'hat': dict(d='Woody_Hat_D.tga.png', n='Woody_Hat_N.tga.png', size=1024, nsize=512, spec=0.1),
    'boots': dict(d='Woody_Boots_D.tga.png', n='Woody_Boots_N.tga.png', size=512, nsize=256, spec=0.3),
    'hair': dict(d='Woody_Hair_D.tga.png', n='Woody_Hair_N.tga.png', size=512, nsize=256, spec=0.1),
}
MATERIALS = {'24_skin_0': 'head', 'New ': 'head', '22_clothes_0': 'clothes', '-Pull String.a': 'clothes',
             '22_shirt_0': 'shirt', '22_hat_0': 'hat', '22_boots_0': 'boots', '24_hair_0': 'hair'}

TORSO = ['bip_pelvis', 'bip_spine_0', 'bip_spine_1', 'bip_spine_2', 'hips', 'pelvis adj']
LANDMARKS = [('bip_pelvis', 'Hips'), ('bip_upperArm_L', 'BicepLeft'), ('bip_upperArm_R', 'BicepRight'),
             ('bip_neck', 'Neck'), ('bip_hip_L', 'ThighLeft'), ('bip_hip_R', 'ThighRight')]
SCALE_JOINTS = [('bip_pelvis', 'Hips'), ('bip_neck', 'Neck'), ('bip_head', 'Head'),
                ('bip_upperArm_L', 'BicepLeft'), ('bip_upperArm_R', 'BicepRight'),
                ('bip_lowerArm_L', 'ForearmLeft'), ('bip_lowerArm_R', 'ForearmRight'),
                ('bip_hand_L', 'HandLeft'), ('bip_hand_R', 'HandRight'), ('bip_hip_L', 'ThighLeft'),
                ('bip_hip_R', 'ThighRight'), ('bip_knee_L', 'CalfLeft'), ('bip_knee_R', 'CalfRight')]
FACE_ALIGN = [('head eyebrow left 2', 'BrowLeft'), ('head eyebrow right 2', 'BrowRight'),
              ('head lip upper middle', 'UpperLip'), ('head lip lower middle', 'LowerLip'),
              ('head lip corner left', 'LipCornerLeft'), ('head lip corner right', 'LipCornerRight')]

DRIVE = {
    'bip_neck': ('bip_head', 'Neck', 'Head', {'aim_face': True}),
    'bip_head': (None, 'Head', None, {'face': True}),
}
for s, t in (('L', 'Left'), ('R', 'Right')):
    DRIVE.update({
        'bip_hip_' + s: ('bip_knee_' + s, 'Thigh' + t, 'Calf' + t, {}),
        'bip_knee_' + s: ('bip_foot_' + s, 'Calf' + t, 'Foot' + t, {'aim_floor': True}),
        'bip_foot_' + s: (None, 'Foot' + t, None, {'floor': True}),
        'bip_upperArm_' + s: ('bip_lowerArm_' + s, 'Bicep' + t, 'Forearm' + t, {}),
        'bip_lowerArm_' + s: ('bip_hand_' + s, 'Forearm' + t, 'Hand' + t, {}),
        'bip_hand_' + s: ('bip_middle_0_' + s, 'Hand' + t, 'Middle1' + t, {}),
    })

# the eyelids ('New ' mesh, one half-sphere per lid) are shut in the rest pose: turned open around the eyeball
EYES = [('head eyeball %s' % side, ['head eyelid %s upper %d' % (side, k) for k in range(1, 8)],
         ['head eyelid %s lower %d' % (side, k) for k in range(1, 8)]) for side in ('left', 'right')]
EYE_MODE = 'rotate'
EYE_OPEN_TOP = 28                       # 45 hid the lids under the skin
EYE_OPEN_BOTTOM = 35

WEIGHTS = {'bip_pelvis': 'Hips', 'hips': 'Hips', 'pelvis adj': 'Hips', 'bip_spine_0': 'Spine1',
           'bip_spine_1': 'Spine2', 'bip_spine_2': 'Spine3', 'button 2': 'Spine2', 'button 1': 'Spine3',
           'sheriff badge': 'Spine3', 'bip_neck': 'Neck', 'scarf root a': 'Neck', 'scarf root b': 'Neck',
           'scarf 1a': 'Neck', 'scarf 1b': 'Neck', 'scarf 2a': 'Neck', 'scarf 2b': 'Neck',
           'holster a': 'Holster', 'holster b': 'Holster', 'holster c': 'Holster',
           'bip_head': 'Head', 'hat root': 'Hat', 'Phy hat root': 'Hat',
           'head eyebrow center': 'MiddleBrow', 'head jaw': 'Jaw', 'head chin': 'Jaw', 'head teeth lower': 'Jaw',
           'head tongue 1': 'Jaw', 'head tongue 2': 'Jaw', 'head mouth lower left': 'Jaw',
           'head mouth lower right': 'Jaw', 'head lip upper middle': 'UpperLip', 'head lip lower middle': 'LowerLip',
           'lkneeadjuster': 'CalfLeft'}
THUMB = {'L': ('0', '1', '2'), 'R': ('1', '2', '3')}
for s, t, side in (('L', 'Left', 'left'), ('R', 'Right', 'right')):
    WEIGHTS.update({'bip_hip_' + s: 'Thigh' + t, 'bip_knee_' + s: 'Calf' + t, 'bip_foot_' + s: 'Foot' + t,
                    'bip_toe_' + s: 'Toes' + t, 'bip_collar_' + s: 'Clavicle' + t,
                    'bip_upperArm_' + s: 'Bicep' + t, 'bip_lowerArm_' + s: 'Forearm' + t, 'bip_hand_' + s: 'Hand' + t,
                    'arm %s shoulder adj' % side: 'Bicep' + t, 'arm %s elbow adj' % side: 'Forearm' + t,
                    'arm %s wrist adj 1' % side: 'Forearm' + t, 'arm %s wrist adj 2' % side: 'Forearm' + t,
                    'arm %s wrist adj 3' % side: 'Forearm' + t, 'arm %s wrist adj 4' % side: 'Hand' + t,
                    'leg %s thigh adj' % side: 'Thigh' + t, 'leg %s knee adj 1' % side: 'Calf' + t,
                    'leg %s knee adj 2' % side: 'Calf' + t, 'leg %s ankle adj 1' % side: 'Calf' + t,
                    'leg %s ankle adj 2' % side: 'Foot' + t, 'leg %s ankle piece' % side: 'Foot' + t,
                    'head lip upper %s' % side: 'UpperLip', 'head lip lower %s' % side: 'LowerLip',
                    'head lip corner %s' % side: 'LipCorner' + t, 'head lip corner %s adj' % side: 'LipCorner' + t})
    for k in '1234':
        WEIGHTS['head eyebrow %s %s' % (side, k)] = 'Brow' + t
    for k in '12':
        WEIGHTS['head eyebrow %s base %s' % (side, k)] = 'Brow' + t
    for f5, f3 in (('index', 'Index'), ('middle', 'Middle'), ('ring', 'Ring'), ('pinky', 'Pinky')):
        for k in range(3):
            WEIGHTS['bip_%s_%d_%s' % (f5, k, s)] = f3 + str(k + 1) + t      # the game spells them Index1Left ...
    for k, n in enumerate(THUMB[s]):
        WEIGHTS['bip_thumb_%s_%s' % (n, s)] = 'Thumb' + str(k + 1) + t

FACE_BONES = set()
FACE = True
