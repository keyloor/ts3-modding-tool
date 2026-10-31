"""Carl Johnson (GTA: San Andreas) -> Toy Story 3 Woody skeleton.

The source's left side is +X, as is Woody's.  It is an old ASCII FBX with a
human-sized, complete rig; the shared reader supports that source format.
"""

PREFIX = 'cj'
KEEP_PIECES = []

TEXTURES = {
    'body': dict(d='upper body.png', size=1024, spec=0.08),
    'head': dict(d='head.png', size=512, spec=0.10),
    'shoes': dict(d='shoes.png', size=512, spec=0.20),
    'legs': dict(d='legs.png', size=512, spec=0.08),
}
MATERIALS = {
    'body upper': 'body', 'head': 'head', 'shoes': 'shoes', 'legs': 'legs',
}
# CJ's jeans are intentionally baggy in the source.  A small transverse
# reduction brings their silhouette in line with his fitted torso.
MATERIAL_SCALE = {'legs': (0.84, 1.0, 0.88)}

TORSO = ['root hips', 'pelvis', 'spine lower', 'spine middle', 'spine upper']
LANDMARKS = [
    ('pelvis', 'Hips'),
    ('arm left shoulder 2', 'BicepLeft'), ('arm right shoulder 2', 'BicepRight'),
    ('head neck lower', 'Neck'),
    ('leg left thigh', 'ThighLeft'), ('leg right thigh', 'ThighRight'),
]
SCALE_JOINTS = [
    ('pelvis', 'Hips'), ('head neck lower', 'Neck'), ('head neck upper', 'Head'),
    ('arm left shoulder 2', 'BicepLeft'), ('arm right shoulder 2', 'BicepRight'),
    ('arm left elbow', 'ForearmLeft'), ('arm right elbow', 'ForearmRight'),
    ('arm left wrist', 'HandLeft'), ('arm right wrist', 'HandRight'),
    ('leg left thigh', 'ThighLeft'), ('leg right thigh', 'ThighRight'),
    ('leg left knee', 'CalfLeft'), ('leg right knee', 'CalfRight'),
    ('leg left ankle', 'FootLeft'), ('leg right ankle', 'FootRight'),
]
# CJ's human facial pivots are much lower than the caricatured Woody face.
# Keep his head naturally seated on the neck instead of stretching it upward to
# Woody's brow pivots.  Facial weights are kept on Head below for the same
# reason; the source has no compatible eyelid/eye rig in Woody.
FACE_ALIGN = []

DRIVE = {
    # Woody's head pivot sits above CJ's natural head position.  Move CJ's
    # whole head down 3.5 cm and let the neck join it there, retaining the
    # source's natural neck length and avoiding the stretched, angled seam.
    'head neck lower': ('head neck upper', 'Neck', 'Head', {'tip_offset': (0, -0.035, 0)}),
    'head neck upper': (None, 'Head', None, {'offset': (0, -0.035, 0)}),
}
for side, target in (('left', 'Left'), ('right', 'Right')):
    DRIVE.update({
        'leg %s thigh' % side: ('leg %s knee' % side, 'Thigh' + target, 'Calf' + target, {}),
        'leg %s knee' % side: ('leg %s ankle' % side, 'Calf' + target, 'Foot' + target, {'aim_floor': True}),
        'leg %s ankle' % side: ('leg %s toes' % side, 'Foot' + target, 'Toes' + target, {'floor': True}),
        'arm %s shoulder 2' % side: ('arm %s elbow' % side, 'Bicep' + target, 'Forearm' + target, {}),
        'arm %s elbow' % side: ('arm %s wrist' % side, 'Forearm' + target, 'Hand' + target, {}),
        'arm %s wrist' % side: ('arm %s finger 2a' % side, 'Hand' + target, 'Middle1' + target, {}),
    })

WEIGHTS = {
    'root ground': 'Hips', 'root hips': 'Hips', 'pelvis': 'Hips',
    'spine lower': 'Spine1', 'spine middle': 'Spine2', 'spine upper': 'Spine3',
    'head neck lower': 'Neck', 'head neck upper': 'Head',
    'head jaw': 'Jaw', 'head lip upper middle': 'UpperLip', 'head lip lower middle': 'LowerLip',
    'head lip upper left': 'UpperLip', 'head lip upper right': 'UpperLip',
    'head lip lower left': 'LowerLip', 'head lip lower right': 'LowerLip',
    'head mouth corner left': 'LipCornerLeft', 'head mouth corner right': 'LipCornerRight',
    'head eyebrow middle': 'MiddleBrow',
    # Woody has no eye bones, so the source eyes and lids stay attached to its head.
    'head eyeball left': 'Head', 'head eyeball right': 'Head',
    'head eyelid left upper': 'Head', 'head eyelid left lower': 'Head',
    'head eyelid right upper': 'Head', 'head eyelid right lower': 'Head',
}
for side, target in (('left', 'Left'), ('right', 'Right')):
    WEIGHTS.update({
        'leg %s thigh' % side: 'Thigh' + target,
        'leg %s knee' % side: 'Calf' + target,
        'leg %s ankle' % side: 'Foot' + target,
        'leg %s toes' % side: 'Toes' + target,
        'arm %s shoulder 1' % side: 'Clavicle' + target,
        'arm %s shoulder 2' % side: 'Bicep' + target,
        'arm %s elbow' % side: 'Forearm' + target,
        'arm %s wrist' % side: 'Hand' + target,
        'arm %s finger 1a' % side: 'Index1' + target,
        'arm %s finger 1b' % side: 'Index2' + target,
        'arm %s finger 1c' % side: 'Index3' + target,
        'arm %s finger 2a' % side: 'Middle1' + target,
        'arm %s finger 2b' % side: 'Middle2' + target,
        'arm %s finger 2c' % side: 'Middle3' + target,
    })
    for k in range(1, 4):
        WEIGHTS['head eyebrow %s %d' % (side, k)] = 'Brow' + target

FACE_BONES = {'Jaw', 'UpperLip', 'LowerLip', 'LipCornerLeft', 'LipCornerRight',
              'MiddleBrow', 'BrowLeft', 'BrowRight'}
FACE = False
