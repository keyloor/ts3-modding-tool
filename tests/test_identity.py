"""Original-skeleton reinsertion: matching, geometry/skin preservation and refusal before output rotation."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'kit'), str(ROOT / 'tests')]
ENTRY = [sys.executable, '-I', str(ROOT / 'kit/cli.py')]
if '--exe' in sys.argv:
    at = sys.argv.index('--exe'); ENTRY = [str(Path(sys.argv[at+1]).resolve())]; del sys.argv[at:at+2]
import kit as K
import identity as ID
import identityfit as IF
import convert as CV
import gltf
from gltflib import Scene
import test_gltf as F
from test_gltflib import container
import numpy as np


class Identity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-identity-'); self.root = Path(self.temp.name)
        self.path = self.root / 'model.glb'
        self.obj = F.model(skinned=True)
        self.obj.BW = np.tile([128/255, 127/255, 0, 0], (3, 1))
        raw, _ = gltf.encode(self.obj); self.raw = raw; self.path.write_bytes(raw)
        self.bones = [dict(id=10, name='Root', node=1, parent=0, pivot=[0, 0, 0]),
                      dict(id=20, name='Child', node=2, parent=1, pivot=[0, 1, 0])]

    def tearDown(self): self.temp.cleanup()

    def rewrite(self, fn):
        doc, binary = F.parse(self.raw); fn(doc)
        self.path.write_bytes(container(doc, binary))

    def merged(self):
        scene = Scene(self.path); names, _ = IF.mapping(scene, self.bones)
        mp = NS(IDENTITY=True, WEIGHTS=names, MATERIALS={}, SCALE=77, GIRTH={'Child': 9}, JOINT_POS={'Child': (9, 9, 9)})
        return scene, CV.merge_meshes(scene, mp, lambda _: None), mp

    def test_ids_allow_renamed_joints_and_names_work_when_extras_are_lost(self):
        def rename(d):
            for j in d['skins'][0]['joints']: d['nodes'][j]['name'] += '_edited'
        self.rewrite(rename)
        names, report = IF.mapping(Scene(self.path), self.bones)
        self.assertEqual(names, {'Root_edited': 'Root', 'Child_edited': 'Child'})
        self.assertEqual(report['matched_by_id'], 2)
        self.rewrite(lambda d: [d['nodes'][j].pop('extras') for j in d['skins'][0]['joints']])
        self.assertEqual(IF.mapping(Scene(self.path), self.bones)[1]['matched_by_name'], 2)

    def test_wrong_id_does_not_fall_back_to_a_matching_name(self):
        self.rewrite(lambda d: d['nodes'][d['skins'][0]['joints'][1]]['extras'].update(ts3BoneId=999))
        with self.assertRaisesRegex(IF.IdentityError, 'no original'): IF.mapping(Scene(self.path), self.bones)

    def test_moved_pivot_and_reparenting_are_rejected(self):
        self.rewrite(lambda d: d['nodes'][d['skins'][0]['joints'][1]].update(translation=[0, 1.01, 0]))
        with self.assertRaisesRegex(IF.IdentityError, 'pivot'): IF.mapping(Scene(self.path), self.bones)
        bones = copy.deepcopy(self.bones); bones[1]['parent'] = 0
        self.path.write_bytes(self.raw)
        with self.assertRaisesRegex(IF.IdentityError, 'hierarchy'): IF.mapping(Scene(self.path), bones)

    def test_duplicate_bone_mapping_and_unknown_name_are_rejected(self):
        self.rewrite(lambda d: d['nodes'][d['skins'][0]['joints'][1]]['extras'].update(ts3BoneId=10))
        with self.assertRaisesRegex(IF.IdentityError, 'More than one'): IF.mapping(Scene(self.path), self.bones)
        def unknown(d):
            for j in d['skins'][0]['joints']:
                d['nodes'][j].pop('extras'); d['nodes'][j]['name'] = 'unknown' + str(j)
        self.rewrite(unknown)
        with self.assertRaisesRegex(IF.IdentityError, 'no original'): IF.mapping(Scene(self.path), self.bones)

    def test_unrepresented_target_ancestors_are_skipped_for_hierarchy(self):
        bones = copy.deepcopy(self.bones)
        bones.append(dict(id=30, name='Unweighted', node=3, parent=1, pivot=[0, .5, 0]))
        bones[1]['parent'] = 3
        self.assertEqual(IF.mapping(Scene(self.path), bones)[1]['joints'], 2)

    def test_identity_keeps_edited_positions_uv_winding_and_byte_weights(self):
        scene, mesh, mp = self.merged()
        mesh['pos'][1] += [.125, .0625, -.25]
        # Deliberately oppose normals to winding: identity must not silently flip the source triangles.
        mesh['normals'] = (-mesh['normals'][0], mesh['normals'][1])
        p, r, r0, w = CV.fit(scene, mesh, self.bones, mp, lambda _: None)
        np.testing.assert_array_equal(p, mesh['pos'])
        v, idx = CV.build_vertices(mesh, p, r, r0, w, {'Root': 10, 'Child': 20}, identity=True)
        np.testing.assert_array_equal(v['p'][idx], mesh['pos'][mesh['cp'][mesh['tri']]])
        np.testing.assert_array_equal(v['uv'][idx], self.obj.UV[mesh['tri']])
        np.testing.assert_array_equal(v['bw'], np.tile([128, 127, 0, 0], (3, 1)))
        self.assertEqual(v['bw'].shape[1], 4)
        self.assertEqual(v['bid'][0].tolist(), [10, 20, 10, 10])

    def test_one_weight_is_padded_without_changing_it(self):
        scene, mesh, mp = self.merged(); mesh['skin'] = [c for c in mesh['skin'] if len(c['idx'])][:1]
        mesh['skin'][0]['w'][:] = 1
        p, r, r0, w = CV.fit(scene, mesh, self.bones, mp, lambda _: None)
        v, _ = CV.build_vertices(mesh, p, r, r0, w, {'Root': 10}, identity=True)
        np.testing.assert_array_equal(v['bw'], np.tile([255, 0, 0, 0], (3, 1)))

    def test_more_than_four_distinct_influences_are_refused(self):
        scene, mesh, mp = self.merged()
        bones = self.bones + [dict(id=i, name='Extra'+str(i), node=i, parent=1, pivot=[0, 0, 0]) for i in (30, 40, 50)]
        root = scene.identity_joints()[0]['node']
        joints = scene.identity_joints() + [dict(id=b['id'], name=b['name'], node=b['node'], parent=root, pivot=b['pivot']) for b in bones[2:]]
        scene.identity_joints = lambda: joints
        mp.WEIGHTS = {j['name']: j['name'] for j in joints}
        mesh['skin'] = [dict(bone=b['name'], idx=np.arange(3), w=np.full(3, .2)) for b in bones]
        with self.assertRaisesRegex(IF.IdentityError, 'four'): CV.fit(scene, mesh, bones, mp, lambda _: None)

    def test_edited_weight_map_and_unmapped_clusters_are_refused(self):
        scene, mesh, mp = self.merged(); mp.WEIGHTS['Child'] = 'Root'
        with self.assertRaisesRegex(IF.IdentityError, 'Regenerate'): CV.fit(scene, mesh, self.bones, mp, lambda _: None)
        mp.WEIGHTS['Child'] = 'Child'; next(c for c in mesh['skin'] if len(c['idx']))['bone'] = 'unknown'
        with self.assertRaisesRegex(IF.IdentityError, 'no original mapping'): CV.fit(scene, mesh, self.bones, mp, lambda _: None)

    def test_map_mode_cannot_be_reused_or_computed_silently(self):
        path = self.root / 'map.py'
        for text, expected in [('WEIGHTS = {}', False), ('IDENTITY = True', True), ('IDENTITY = False', False)]:
            path.write_text(text); ID.check_map(path, expected)
            with self.assertRaisesRegex(IF.IdentityError, 'differs'): ID.check_map(path, not expected)
        for text in ('IDENTITY = bool(1)', 'if True:\n IDENTITY = True', 'IDENTITY=True\nIDENTITY=False'):
            path.write_text(text)
            with self.assertRaisesRegex(IF.IdentityError, 'literal'): ID.check_map(path, True)

    def test_invalid_mode_and_non_gltf_source_are_refused(self):
        with self.assertRaises(IF.IdentityError): ID.mode({'fit_mode': 'other'})
        with self.assertRaisesRegex(IF.IdentityError, 'GLB'): ID.mode({'fit_mode': 'identity', 'fbx': 'a.fbx'})
        self.assertFalse(ID.mode({}))

    def test_mismatched_map_is_rejected_before_previous_output_moves(self):
        work = self.root / 'project'; out = work / 'out/woody'; out.mkdir(parents=True)
        (out / 'keep.bin').write_bytes(b'last successful conversion')
        (work / 'map.py').write_text('IDENTITY = False')
        with patch.object(K, 'prepare', return_value=str(self.root)):
            with self.assertRaisesRegex(K.KitError, 'differs'):
                K.build(str(work), dict(character='woody', fbx=str(self.path), textures=None, game='fake', fit_mode='identity'))
        self.assertEqual((out / 'keep.bin').read_bytes(), b'last successful conversion')
        self.assertFalse((work / 'out_prev').exists())

    def test_generated_map_is_explicit_and_does_not_use_saved_fitting_adjustments(self):
        proj = dict(fbx=str(self.path), character='woody', fit_mode='identity', adjust={'head_cm': 99})
        with patch.object(ID.T, 'load', return_value=(None, self.bones, [], None)), \
                patch.object(ID.AM, 'material_effect', return_value='Synthetic'):
            tables, info = ID.detect(proj, str(self.root), lambda _: None)
        mpath = self.root / 'map.py'; ID.AM.write_map(tables, info, str(mpath), str(self.path), 'woody')
        ID.check_map(mpath, True); mp = CV.load_map(str(mpath))
        self.assertTrue(mp.IDENTITY); self.assertEqual(mp.DRIVE, {}); self.assertFalse(hasattr(mp, 'GIRTH'))
        self.assertEqual(proj['adjust'], {'head_cm': 99})
        with patch.object(K, 'strain', side_effect=AssertionError('stale normal-fit strain read')):
            self.assertEqual(K.diagnose(str(self.root), proj, tables, info), [])

    def test_cli_exposes_identity_option_and_clean_rejection(self):
        help_ = subprocess.run(ENTRY + ['make', '--help'], capture_output=True, text=True)
        self.assertEqual(help_.returncode, 0); self.assertIn('--fit', help_.stdout)
        model = self.root / 'model.obj'; model.write_text('v 0 0 0')
        result = subprocess.run(ENTRY + ['make', str(self.root / 'cli-project'), '--character', 'woody',
                                '--model', str(model), '--fit', 'identity', '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'invalid_model')


if __name__ == '__main__': unittest.main()
