"""The Adjustments from the command line (kit.py adjust) and the stretch read from a report. No game files, no model,
no user settings: a project folder with only its kit_project.json.

Run: python -I tests/test_adjust.py
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'kit'))
import kit as K


class Adjust(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-adjust-test-')
        self.work = Path(self.temp.name)
        (self.work / 'kit_project.json').write_text(json.dumps({'character': 'woody', 'fbx': 'model.fbx',
                                                               'game': str(self.work / 'no game')}))

    def tearDown(self):
        self.temp.cleanup()

    def kit_json(self, *args):
        """kit.main with --json: (exit status, the one JSON object it printed)"""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            status = K.main(list(args) + ['--json'])
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        return status, json.loads(lines[0])

    def run_kit(self, *args):
        status, d = self.kit_json('adjust', str(self.work), *args)
        self.assertEqual((status, d['ok'], d['command'], d['error']), (0, True, 'kit.adjust', None))
        return d['data']

    def refused(self, *args):
        status, d = self.kit_json(*args)
        self.assertFalse(d['ok'])
        return status, d['error']['code']

    def project(self):
        return json.loads((self.work / 'kit_project.json').read_text())

    def test_set_put_unset(self):
        d = self.run_kit('--set', 'head_cm=-2.5', '--set', 'torso=[110,100,100]', '--set', 'face=true',
                         '--put', 'props', 'Staff=hand_right', '--put', 'props', 'Bag=out',
                         '--put', 'weights', 'Helper={"Spine3": 0.5, "Neck": 0.5}',
                         '--set', 'eyes_open={"top": 20, "bottom": 5}')
        adj = self.project()['adjust']
        self.assertEqual(adj['head_cm'], -2.5)
        self.assertEqual(adj['torso'], [110, 100, 100])
        self.assertIs(adj['face'], True)
        self.assertEqual(adj['props'], {'Staff': 'hand_right', 'Bag': 'out'})
        self.assertEqual(adj['weights']['Helper'], {'Spine3': 0.5, 'Neck': 0.5})
        self.assertEqual(d['adjust'], adj)
        self.assertIn('make --remap', d['next'])
        self.run_kit('--drop', 'props', 'Bag', '--unset', 'face')
        adj = self.project()['adjust']
        self.assertEqual(adj['props'], {'Staff': 'hand_right'})
        self.assertNotIn('face', adj)

    def test_rejects_unknown(self):
        for args in (['--set', 'bogus=1'], ['--put', 'props', 'Hat=pocket'], ['--set', 'torso=[1,2]']):
            self.assertEqual(self.refused('adjust', str(self.work), *args), (3, 'invalid_value'))
        self.assertNotIn('adjust', self.project())

    def test_versions_and_joints(self):
        self.run_kit('--set', 'arms_pct=120', '--joint', 'LeftForeArm=10,100,-2', '--save-version', 'wide')
        self.run_kit('--unset', 'arms_pct', '--reset-joints')
        self.assertNotIn('adjust', self.project())
        self.assertNotIn('joints', self.project())
        d = self.run_kit('--load-version', 'wide')
        self.assertEqual(self.project()['adjust'], {'arms_pct': 120})
        self.assertEqual(self.project()['joints'], {'LeftForeArm': [10.0, 100.0, -2.0]})
        self.assertEqual(d['versions'], ['wide'])
        self.run_kit('--delete-version', 'wide')
        self.assertNotIn('adjust_versions', self.project())

    def test_body_keys(self):
        self.run_kit('--set', 'scale_pct=105', '--set', 'shoulders_cm=2', '--put', 'stretch_limit', 'neck=1.6')
        self.assertEqual(self.project()['adjust'], {'scale_pct': 105, 'shoulders_cm': 2,
                                                    'stretch_limit': {'neck': 1.6}})
        self.assertEqual(self.refused('adjust', str(self.work), '--put', 'stretch_limit', 'tail=2'), (3, 'invalid_value'))

    def test_json_envelope_and_errors(self):
        self.assertEqual(self.refused('characters', '--bogus'), (2, 'invalid_arguments'))
        self.assertEqual(self.refused('install', str(self.work / 'nothing here')), (3, 'no_project'))
        self.assertEqual(self.refused('install', str(self.work)), (3, 'game_not_found'))
        self.assertEqual(self.refused('characters', '--game', str(self.work)), (3, 'game_not_found'))
        status, d = self.kit_json('diagnose', str(self.work), '--fix', 'nothing')
        self.assertEqual((status, d['command']), (3, 'kit.diagnose'))
        # without --json the answer is text, the error on stderr, and the same exit status
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(K.main(['install', str(self.work / 'nothing here')]), 3)
        self.assertIn('error:', err.getvalue())

    def test_merge_and_limit_steps(self):
        self.assertEqual(K.merge_adjust({'stretch_limit': {'neck': 1.5}, 'face': True},
                                        {'stretch_limit': {'hands': 1.5}, 'head_cm': 2}),
                         {'stretch_limit': {'neck': 1.5, 'hands': 1.5}, 'face': True, 'head_cm': 2})
        self.assertEqual(K.limit_step(1.5625), 1.65)
        self.assertEqual(K.limit_step(9), 2.5)

    def test_diagnose_findings_and_fix(self):
        """diagnose() on measurements given by hand (no model): what it says and the fixes it offers"""
        class Sk:
            pos = {'hand_l': [0.6, 1.4, 0]}
        (self.work / 'report.txt').write_text(
            '  bip_hand_L   -> HandLeft       turn   3.3 deg  stretch 1.25  move 0.087\n', encoding='utf-8')
        tables = {'WEIGHTS': {'Staff': 'Hips'}, '_tex_notes': {'Coat': 'check', 'Skin': ''}}
        info = {'neck': {'model_cm': 6.9, 'game_cm': 10.6, 'stretch': 1.52, 'natural_cm': -3.6},
                'torso': {'width_pct': 125, 'height_pct': 100}, 'skeleton': Sk(), 'body': {'handLeft': 'hand_l'},
                'eyes': {'Left': ('EyeL', ['LidTopL'], [])}, 'face': {'jaw': 'Jaw', 'upperlip': 'Lip'},
                'extras': ['Staff']}
        found = {d['id']: d for d in K.diagnose(str(self.work), self.project(), tables, info)}
        self.assertEqual(set(found), {'neck', 'torso_width', 'limit_hands', 'materials', 'eyes', 'face', 'prop_Staff'})
        self.assertEqual(found['neck']['fixes'][0]['set'], {'head_cm': -3.6})
        self.assertEqual(found['neck']['fixes'][1]['set'], {'stretch_limit': {'neck': 1.6}})
        self.assertEqual(found['torso_width']['fixes'][0]['set'], {'torso': [80, 100, 100]})
        self.assertEqual(found['limit_hands']['fixes'][0]['set'], {'stretch_limit': {'hands': 1.5}})
        self.assertEqual(found['materials']['args']['list'], 'Coat')
        # with those fixed in the project, they are no longer pointed out
        proj = dict(self.project(), adjust={'eyes_open': {'top': 15, 'bottom': 5}, 'face': True,
                                            'stretch_limit': {'neck': 1.6, 'hands': 1.5}, 'props': {'Staff': 'out'}})
        again = {d['id'] for d in K.diagnose(str(self.work), proj, tables, info)}
        self.assertEqual(again, {'torso_width', 'materials'})

    def test_strain_from_report(self):
        (self.work / 'report.txt').write_text(
            '  torso block: scale [0.969 0.982 1.   ], offset [0 0 0], landmark error 0.041\n'
            '  bip_neck     -> Neck           turn   3.0 deg  stretch 1.25  move 0.020\n'
            '  Bip01 L Forearm -> ForearmLeft    turn  12.1 deg  stretch 0.87  move 0.047\n', encoding='utf-8')
        s = K.strain(str(self.work))
        self.assertEqual(s['Neck'], 1.25)
        self.assertEqual(s['ForearmLeft'], 0.87)
        self.assertEqual(s['Spine2'], 0.969)


if __name__ == '__main__':
    unittest.main(verbosity=2)
