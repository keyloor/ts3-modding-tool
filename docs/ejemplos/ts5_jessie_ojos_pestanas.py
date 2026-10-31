"""Toy Story 5 Jessie (Fortnite rig) -> Toy Story 3 Jessie skeleton. See buzz_map.py for what each table means.

The model's 'L_Thigh' is the hip joint and 'L_Thigh_2' / 'L_Shin' twist bones; 'L_Shoulder' is the shoulder joint and
'L_Bicep' / 'L_forearm' twist bones. It has no jaw: its 'Mouth' bones move both lips together, so the mouth stays
with the head. The game's eyelid bones turn around a point well behind this model's eyes, so the lids stay with the
head too (no blinking); the eyes follow the game's eye bones.
"""

KEEP_PIECES = []
MATERIAL_EFFECT = 'a_1_dmnsmqdrqcf2_skin'          # Jessie's archive has no a_1_dmnsmqdrqcf_skin; her cloth's shader

TORSO = ['Pelvis', 'Spine1', 'Spine2', 'Spine3', 'Spine4']
LANDMARKS = [('Pelvis', 'Hips'), ('L_Shoulder', 'BicepLeft'), ('R_Shoulder', 'BicepRight'), ('Neck', 'Neck'),
             ('L_Thigh', 'ThighLeft'), ('R_Thigh', 'ThighRight')]
SCALE_JOINTS = [('Pelvis', 'Hips'), ('Neck', 'Neck'), ('Head', 'Head'), ('L_Shoulder', 'BicepLeft'),
                ('R_Shoulder', 'BicepRight'), ('L_Elbow', 'ForearmLeft'), ('R_Elbow', 'ForearmRight'),
                ('L_Hand', 'HandLeft'), ('R_Hand', 'HandRight'), ('L_Thigh', 'ThighLeft'), ('R_Thigh', 'ThighRight'),
                ('L_Knee', 'CalfLeft'), ('R_Knee', 'CalfRight')]
FACE_ALIGN = [('L_Eye', 'eyeLeft'), ('R_Eye', 'eyeRight'), ('L_BrowMid', 'BrowLeft'), ('R_BrowMid', 'BrowRight'),
              ('MouthL', 'LipCornerLeft'), ('MouthR', 'LipCornerRight')]

DRIVE = {
    'Neck': ('Head', 'Neck', 'Head', {'aim_face': True}),
    'Head': (None, 'Head', None, {'face': True}),
}
WEIGHTS = {'Root': 'Hips', 'Pelvis': 'Hips', 'Spine1': 'Spine1', 'Spine2': 'Spine2', 'Spine3': 'Spine3',
           'Spine4': 'Spine3', 'Neck': 'Neck', 'Head': 'Head', 'Hat': 'Hat',
           'Hair1': 'Hair1', 'Hair2': 'Hair2', 'Hair3': 'Hair3', 'Hair4': 'Hair4', 'Hair5': 'Hair4',
           'Mouth': 'Head', 'MouthL': 'Head', 'MouthR': 'Head'}
for s, t in (('L', 'Left'), ('R', 'Right')):
    DRIVE.update({
        s + '_Thigh': (s + '_Knee', 'Thigh' + t, 'Calf' + t, {}),
        s + '_Knee': (s + '_Ankle', 'Calf' + t, 'Foot' + t, {'aim_floor': True}),
        s + '_Ankle': (None, 'Foot' + t, None, {'floor': True}),
        s + '_Shoulder': (s + '_Elbow', 'Bicep' + t, 'Forearm' + t, {}),
        s + '_Elbow': (s + '_Hand', 'Forearm' + t, 'Hand' + t, {}),
        s + '_Hand': (s + '_Middle1', 'Hand' + t, 'Middle1' + t, {}),
    })
    WEIGHTS.update({s + '_Thigh': 'Thigh' + t, s + '_Thigh_2': 'Thigh' + t, s + '_Knee': 'Calf' + t,
                    s + '_Shin': 'Calf' + t, s + '_LegTassles': 'Calf' + t, s + '_Ankle': 'Foot' + t,
                    s + '_Toe': 'Toes' + t, s + '_Clav': 'Clavicle' + t, s + '_Shoulder': 'Bicep' + t,
                    s + '_Bicep': 'Bicep' + t, s + '_Elbow': 'Forearm' + t, s + '_forearm': 'Forearm' + t,
                    s + '_ArmTassles': 'Forearm' + t, s + '_Hand': 'Hand' + t, s + '_Eye': 'eye' + t,
                    s + '_BrowMid': 'Brow' + t, s + '_BrowIn': 'Brow' + t, s + '_BrowOut': 'Brow' + t})
    for f5, f3 in (('Pointer', 'Index'), ('Middle', 'Middle'), ('Ring', 'Ring'), ('Pinky', 'Pinky'), ('Thumb', 'Thumb')):
        for k in '123':
            WEIGHTS['%s_%s%s' % (s, f5, k)] = f3 + k + t
    for k in ('01', '02', '03'):
        WEIGHTS['EyeLid_Top_%s_%s' % (k, s)] = 'Head'
        WEIGHTS['EyeLid_Bot_%s_%s' % (k, s)] = 'Head'
    for k in ('01', '02', '03', '04', '05'):
        WEIGHTS['EyeLash_%s_%s' % (k, s)] = 'Head'
    WEIGHTS['EyeLid_Corner_Centre_' + s] = 'Head'
    WEIGHTS['EyeLid_Corner_Far_' + s] = 'Head'

EYES = [('L_Eye', ['EyeLid_Top_01_L', 'EyeLid_Top_02_L', 'EyeLid_Top_03_L'], ['EyeLid_Bot_01_L', 'EyeLid_Bot_02_L', 'EyeLid_Bot_03_L']),
        ('R_Eye', ['EyeLid_Top_01_R', 'EyeLid_Top_02_R', 'EyeLid_Top_03_R'], ['EyeLid_Bot_01_R', 'EyeLid_Bot_02_R', 'EyeLid_Bot_03_R'])]
# the lids shut about 20 deg below the eye centre: the edges slide open and the lid skin is squeezed
EYE_MODE = 'slide'
EYE_TOP_EDGE, EYE_TOP_LIMIT = 22, 48
EYE_BOTTOM_EDGE, EYE_BOTTOM_LIMIT = -32, -68
# the lashes sit apart from the shut lids (17..37 deg): each one is moved onto the opened lid's edge
LASHES = [(eye, ['EyeLash_0%d_%s' % (k, s) for k in range(1, 6)]) for eye, s in (('L_Eye', 'L'), ('R_Eye', 'R'))]

# the game's brow animation moves these brows into the hair: half as far
WEIGHT_SCALE = {'BrowLeft': 0.5, 'BrowRight': 0.5}

FACE_BONES = set()
FACE = True
