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
        (self.work / 'kit_project.json').write_text(json.dumps({'character': 'woody', 'fbx': 'model.fbx'}))

    def tearDown(self):
        self.temp.cleanup()

    def run_kit(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            K.main(['adjust', str(self.work), '--json'] + list(args))
        return json.loads(out.getvalue())

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
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    K.main(['adjust', str(self.work)] + args)
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
