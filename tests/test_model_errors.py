"""A model the tool can't use gets a clear message that says how to fix it, not a traceback. Synthetic skeletons, no
model files and no game files.

Run: python -I tests/test_model_errors.py
"""
import contextlib
import io
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'kit'))
import automap as AM
import kit as K

# a small humanoid in the game's frame (Y up, facing +Z, its left at +x): bone -> (parent, position)
BODY = {'Hips': (None, (0, 1.0, 0)), 'Spine': ('Hips', (0, 1.2, 0)), 'Chest': ('Spine', (0, 1.4, 0)),
        'Neck': ('Chest', (0, 1.55, 0)), 'Head': ('Neck', (0, 1.65, 0)), 'HeadTop': ('Head', (0, 1.8, 0))}
for s, x in (('L', 1), ('R', -1)):
    BODY.update({
        'Clav' + s: ('Chest', (0.05 * x, 1.45, 0)), 'Shoulder' + s: ('Clav' + s, (0.15 * x, 1.45, 0)),
        'Elbow' + s: ('Shoulder' + s, (0.4 * x, 1.45, 0)), 'Hand' + s: ('Elbow' + s, (0.65 * x, 1.45, 0)),
        'Index' + s: ('Hand' + s, (0.72 * x, 1.45, 0.02)), 'Middle' + s: ('Hand' + s, (0.73 * x, 1.45, 0)),
        'Ring' + s: ('Hand' + s, (0.72 * x, 1.45, -0.02)),
        'Thigh' + s: ('Hips', (0.1 * x, 0.95, 0)), 'Knee' + s: ('Thigh' + s, (0.1 * x, 0.5, 0)),
        'Foot' + s: ('Knee' + s, (0.1 * x, 0.08, 0)), 'Toe' + s: ('Foot' + s, (0.1 * x, 0.02, 0.1))})


def skeleton(body):
    sk = AM.Skeleton.__new__(AM.Skeleton)
    sk.parent = {n: p for n, (p, _) in body.items()}
    sk.kids = {n: [] for n in body}
    for n, p in sk.parent.items():
        if p is not None:
            sk.kids[p].append(n)
    sk.pos = {n: np.array(v, float) for n, (_, v) in body.items()}
    sk.nv = {n: 10 for n in body}
    sk.skinned = set(body)
    sk.height = 1.8
    sk._count = {}
    return sk


class ModelErrors(unittest.TestCase):
    def find(self, body, ov=None):
        return AM.find_body(skeleton(body), lambda *a: None, ov)

    def test_good_skeleton_is_found(self):
        b = self.find(BODY)
        self.assertEqual((b['pelvis'], b['chest'], b['head']), ('Hips', 'Chest', 'Head'))
        self.assertEqual((b['kneeLeft'], b['elbowRight']), ('KneeL', 'ElbowR'))

    def test_legs_in_a_separate_skeleton(self):
        body = dict(BODY, LegsRoot=(None, (0, 0.98, 0)))
        for s in 'LR':
            body['Thigh' + s] = ('LegsRoot', body['Thigh' + s][1])
        with self.assertRaises(AM.ModelError) as cm:
            self.find(body)
        e = cm.exception
        self.assertEqual(e.problem, 'split_skeleton')
        self.assertEqual(sorted(e.info['roots']), ['Hips', 'LegsRoot'])
        err = K.model_error(e)
        self.assertEqual(err.code, 'invalid_model')
        self.assertIn('one Armature', str(err))
        self.assertIn('LegsRoot', str(err))

    def test_missing_joint_and_bad_choice(self):
        body = {n: v for n, v in BODY.items() if n not in ('ShoulderL', 'ElbowL')}   # chest > clavicle > hand
        body['HandL'] = ('ClavL', BODY['HandL'][1])
        with self.assertRaises(AM.ModelError) as cm:
            self.find(body)
        self.assertEqual(cm.exception.problem, 'arm')
        with self.assertRaises(AM.ModelError) as cm:
            self.find(BODY, {'kneeLeft': 'NoSuchBone'})
        self.assertEqual((cm.exception.problem, cm.exception.info['bone']), ('bad_choice', 'NoSuchBone'))

    def test_every_problem_has_words(self):
        """the CLI's help and both languages of the window cover every problem the body search can raise"""
        import app as A
        problems = {'split_skeleton', 'no_skin', 'pose', 'not_humanoid', 'leg', 'arm', 'no_head', 'bad_choice',
                    'bad_file'}
        self.assertEqual(set(K.MODEL_HELP), problems)
        for lang in ('es', 'en'):
            self.assertEqual(set(A.TEXT[lang]['model_errors']), problems)

        class Window:                                      # just what App.model_text uses
            t = staticmethod(lambda k: A.TEXT['es'][k])
            role_label = staticmethod(lambda r: r)
        body = dict(BODY, LegsRoot=(None, (0, 0.98, 0)))
        for s in 'LR':
            body['Thigh' + s] = ('LegsRoot', body['Thigh' + s][1])
        try:
            self.find(body)
        except AM.ModelError as e:
            text = A.App.model_text(Window, K.model_error(e))
        self.assertTrue(text.startswith('Los huesos de tu modelo no forman un solo esqueleto'))
        self.assertIn('Cómo arreglarlo', text)
        self.assertIn('Detalle técnico', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
