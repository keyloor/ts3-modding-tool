"""Toy Story 5 Woody (Fortnite rig) -> Toy Story 3 Woody skeleton. See buzz_map.py for what each table means.

The model's bones without a suffix are on Woody's left (+x), '_2' on his right. Its 'Leg' bone is the hip joint,
'Thigh' and 'Shin' are twist bones half way down; 'Arm' is the shoulder joint, 'Bicep' and 'Forearm' twist bones.
The game's Woody has no eye or eyelid bones (its eyes are separate pieces), so the eyes stay still with the head.
"""

KEEP_PIECES = []

TORSO = ['Pelvis', 'Spine1', 'Spine2', 'Spine3']
LANDMARKS = [('Pelvis', 'Hips'), ('Arm', 'BicepLeft'), ('Arm_2', 'BicepRight'), ('Neck', 'Neck'),
             ('Leg', 'ThighLeft'), ('Leg_2', 'ThighRight')]
SCALE_JOINTS = [('Pelvis', 'Hips'), ('Neck', 'Neck'), ('Head', 'Head'), ('Arm', 'BicepLeft'), ('Arm_2', 'BicepRight'),
                ('Elbow', 'ForearmLeft'), ('Elbow_2', 'ForearmRight'), ('Hand', 'HandLeft'), ('Hand_2', 'HandRight'),
                ('Leg', 'ThighLeft'), ('Leg_2', 'ThighRight'), ('Knee', 'CalfLeft'), ('Knee_2', 'CalfRight')]
FACE_ALIGN = [('Brow', 'BrowLeft'), ('Brow_2', 'BrowRight'), ('LipTop', 'UpperLip'), ('LipBottom', 'LowerLip'),
              ('LipCorner', 'LipCornerLeft'), ('LipCorner_2', 'LipCornerRight')]

DRIVE = {
    'Neck': ('Head', 'Neck', 'Head', {'aim_face': True}),
    'Head': (None, 'Head', None, {'face': True}),
}
WEIGHTS = {'Pelvis': 'Hips', 'Spine1': 'Spine1', 'Spine2': 'Spine2', 'Spine3': 'Spine3', 'Neck': 'Neck',
           'ScarfKnot': 'Neck', 'PullString': 'Spine3', 'StringHandle': 'Spine3', 'Holster': 'Holster',
           'Head': 'Head', 'Hat': 'Hat', 'Jaw': 'Jaw', 'LipTop': 'UpperLip', 'LipLeft': 'UpperLip', 'LipRight': 'UpperLip',
           'LipBottom': 'LowerLip', 'BLipLeft': 'LowerLip', 'BLipLeft_2': 'LowerLip', 'Eye': 'Head', 'Eye_2': 'Head'}
for s, t in (('', 'Left'), ('_2', 'Right')):
    DRIVE.update({
        'Leg' + s: ('Knee' + s, 'Thigh' + t, 'Calf' + t, {}),
        'Knee' + s: ('Foot' + s, 'Calf' + t, 'Foot' + t, {'aim_floor': True}),
        'Foot' + s: (None, 'Foot' + t, None, {'floor': True}),
        'Arm' + s: ('Elbow' + s, 'Bicep' + t, 'Forearm' + t, {}),
        'Elbow' + s: ('Hand' + s, 'Forearm' + t, 'Hand' + t, {}),
        'Hand' + s: ('Middle1' + s, 'Hand' + t, 'Middle1' + t, {}),
    })
    WEIGHTS.update({'Leg' + s: 'Thigh' + t, 'Thigh' + s: 'Thigh' + t, 'Knee' + s: 'Calf' + t, 'Shin' + s: 'Calf' + t,
                    'Foot' + s: 'Foot' + t, 'Toe' + s: 'Toes' + t, 'Clav' + s: 'Clavicle' + t,
                    'Arm' + s: 'Bicep' + t, 'Bicep' + s: 'Bicep' + t, 'Elbow' + s: 'Forearm' + t,
                    'Forearm' + s: 'Forearm' + t, 'Hand' + s: 'Hand' + t, 'LipCorner' + s: 'LipCorner' + t,
                    'Brow' + s: 'Brow' + t, 'BrowIn' + s: 'Brow' + t, 'BrowOut' + s: 'Brow' + t})
    for f5, f3 in (('Pointer', 'Index'), ('Middle', 'Middle'), ('Ring', 'Ring'), ('Pinky', 'Pinky'), ('Thumb', 'Thumb')):
        for k in '123':
            WEIGHTS[f5 + k + s] = f3 + k + t                # the game spells them Index1Left, Index2Left ...
for side in 'LR':
    for k in ('01', '02', '03'):
        WEIGHTS['EyeLid_Top_%s_%s' % (k, side)] = 'Head'
        WEIGHTS['EyeLid_Bot_%s_%s' % (k, side)] = 'Head'
    WEIGHTS['EyeLid_Corner_Centre_' + side] = 'Head'
    WEIGHTS['EyeLid_Corner_Far_' + side] = 'Head'

EYES = [('Eye', ['EyeLid_Top_01_L', 'EyeLid_Top_02_L', 'EyeLid_Top_03_L'], ['EyeLid_Bot_01_L', 'EyeLid_Bot_02_L', 'EyeLid_Bot_03_L']),
        ('Eye_2', ['EyeLid_Top_01_R', 'EyeLid_Top_02_R', 'EyeLid_Top_03_R'], ['EyeLid_Bot_01_R', 'EyeLid_Bot_02_R', 'EyeLid_Bot_03_R'])]
# the lids shut about 29 deg below the eye centre and the upper lid skin reaches 65 deg up (turning it all pushed
# it into the brow): slide the edges open and squeeze the lid skin instead
EYE_MODE = 'slide'
EYE_TOP_EDGE, EYE_TOP_LIMIT = 36, 76       # 18 still looked half shut in the game
EYE_BOTTOM_EDGE, EYE_BOTTOM_LIMIT = -36, -88

FACE_BONES = set()
FACE = True
