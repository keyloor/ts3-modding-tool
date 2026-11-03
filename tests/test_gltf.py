"""GLB structure, bind pose, static/skinned separation and read-only explorer export.

python -I tests/test_gltf.py [--exe CONSOLE_EXE] [--artifacts NEW_VALIDATION_DIRECTORY]
"""
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'kit'), str(ROOT / 'tests')]
import gltf
import explorer
import install
from modfile import ModError
import numpy as np
from PIL import Image

ENTRY = [sys.executable, '-I', str(ROOT / 'kit/cli.py')]
ARTIFACTS = None
for option in ('--exe', '--artifacts'):
    if option in sys.argv:
        at = sys.argv.index(option); value = str(Path(sys.argv[at + 1]).resolve()); del sys.argv[at:at + 2]
        if option == '--exe':
            ENTRY = [value]
        else:
            ARTIFACTS = Path(value); ARTIFACTS.mkdir(parents=True, exist_ok=True)

# This fixture module also supports --exe; parse our own arguments before importing it.
import test_explorer as F


def parse(raw):
    magic, version, size = struct.unpack_from('<4sII', raw)
    assert (magic, version, size) == (b'glTF', 2, len(raw))
    length, kind = struct.unpack_from('<II', raw, 12)
    assert kind == 0x4E4F534A and length % 4 == 0
    document = json.loads(raw[20:20 + length])
    at = 20 + length; length, kind = struct.unpack_from('<II', raw, at)
    assert kind == 0x004E4942 and length % 4 == 0 and at + 8 + length == len(raw)
    binary = raw[at + 8:]
    assert 0 <= len(binary) - document['buffers'][0]['byteLength'] <= 3
    for view in document['bufferViews']:
        assert view.get('byteOffset', 0) % 4 == 0
        assert view.get('byteOffset', 0) + view['byteLength'] <= len(binary)
    return document, binary


def accessor(document, binary, index):
    acc = document['accessors'][index]; view = document['bufferViews'][acc['bufferView']]
    width = dict(SCALAR=1, VEC2=2, VEC3=3, VEC4=4, MAT4=16)[acc['type']]
    dtype = {5126: '<f4', 5125: '<u4', 5123: '<u2'}[acc['componentType']]
    at = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
    return np.frombuffer(binary, dtype, acc['count'] * width, at).reshape(acc['count'], width)


def model(skinned=False, mixed=False):
    p = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    if mixed:
        p = np.r_[p, p + [3, 0, 0]].astype(np.float32)
    n = len(p)
    image = np.zeros((8, 16, 4), np.uint8); image[:, :, :3] = [200, 40, 80]; image[:, :8, 3] = 255
    return SimpleNamespace(P0=p, N0=np.tile([0, 0, 1], (n, 1)), UV=np.tile([[0, 0], [1, 0], [0, 1]], (n // 3, 1)),
        groups={0: np.arange(n, dtype=np.uint32)}, textures={0: image}, skipped=0,
        names=['Root', 'Child'] if skinned else ['Root'], parent=np.array([-1, 0] if skinned else [-1]),
        pivots=np.array([[0, 0, 0], [0, 1, 0]] if skinned else [[0, 0, 0]]),
        BI=np.tile([0, 1 if skinned else 0, 0, 0], (n, 1)), BW=np.tile([0.5, 0.5, 0, 0], (n, 1)),
        skin_mask=np.array(([True] * 3 + [False] * 3) if mixed else [skinned] * n), bone_ids=[10, 20] if skinned else [])


class GLB(unittest.TestCase):
    def encode(self, name, obj):
        raw, report = gltf.encode(obj, name)
        if ARTIFACTS:
            (ARTIFACTS / (name + '.glb')).write_bytes(raw)
        doc, binary = parse(raw)
        return doc, binary, report

    def test_static_geometry_uv_and_embedded_alpha_texture(self):
        obj = model(); doc, binary, report = self.encode('static', obj)
        primitive = doc['meshes'][0]['primitives'][0]
        self.assertNotIn('skins', doc)
        self.assertEqual(report['triangles'], 1)
        np.testing.assert_array_equal(accessor(doc, binary, primitive['attributes']['POSITION']), obj.P0)
        np.testing.assert_array_equal(accessor(doc, binary, primitive['attributes']['TEXCOORD_0']), obj.UV)
        self.assertEqual(doc['materials'][0]['alphaMode'], 'MASK')
        view = doc['bufferViews'][doc['images'][0]['bufferView']]
        with Image.open(io.BytesIO(binary[view['byteOffset']:view['byteOffset'] + view['byteLength']])) as image:
            self.assertEqual(image.size, (16, 8)); self.assertEqual(image.getpixel((0, 0)), (200, 40, 80, 255))

    def test_skin_bind_matrices_are_identity_at_rest_and_weights_normalize(self):
        obj = model(skinned=True)
        obj.pivots = np.array([[2, 1, 3], [2, 4, 3]], dtype=np.float32)
        obj.BW = np.tile([0.3, 0.3, 0, 0], (3, 1))
        doc, binary, report = self.encode('skin', obj)
        self.assertEqual(report['bones'], 2)
        skin = doc['skins'][0]
        matrices = accessor(doc, binary, skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
        world = []
        for i, joint in enumerate(skin['joints']):
            node = doc['nodes'][joint]; matrix = np.eye(4); matrix[:3, 3] = node['translation']
            if obj.parent[i] >= 0:
                matrix = world[obj.parent[i]] @ matrix
            world.append(matrix)
            np.testing.assert_allclose(matrix @ matrices[i], np.eye(4), atol=1e-6)
            self.assertEqual(node['extras']['ts3BoneId'], obj.bone_ids[i])
        primitive = doc['meshes'][0]['primitives'][0]
        w = accessor(doc, binary, primitive['attributes']['WEIGHTS_0'])
        np.testing.assert_allclose(w.sum(1), 1)
        np.testing.assert_allclose(w[:, :2], 0.5)

    def test_mixed_static_pieces_stay_outside_skin(self):
        obj = model(skinned=True, mixed=True); doc, _, report = self.encode('mixed', obj)
        self.assertEqual(report['triangles'], 2)
        nodes = [n for n in doc['nodes'] if 'mesh' in n]
        self.assertEqual(len(nodes), 2)
        static = next(n for n in nodes if 'skin' not in n)
        attrs = doc['meshes'][static['mesh']]['primitives'][0]['attributes']
        self.assertNotIn('JOINTS_0', attrs)
        self.assertIn('JOINTS_0', doc['meshes'][next(n for n in nodes if 'skin' in n)['mesh']]['primitives'][0]['attributes'])

    def test_rejects_nan_bad_triangles_missing_joints_and_cycles(self):
        for kind in ('nan', 'indices', 'joint', 'cycle', 'negative_weight'):
            obj = model(skinned=True)
            if kind == 'nan': obj.P0[0, 0] = np.nan
            elif kind == 'indices': obj.groups[0][0] = 123
            elif kind == 'joint': obj.BI[0, 0] = 123
            elif kind == 'cycle': obj.parent = np.array([1, 0])
            else: obj.BW[0, 0] = -1
            with self.subTest(kind=kind), self.assertRaises(ModError):
                gltf.encode(obj)

    def test_duplicate_images_are_embedded_once_and_untextured_uv_is_kept(self):
        obj = model(mixed=False)
        obj.groups[1] = obj.groups[0].copy(); obj.textures[1] = obj.textures[0].copy()
        doc, _, _ = self.encode('two-materials', obj)
        self.assertEqual(len(doc['images']), 1)
        obj.textures = {}; doc, _, _ = self.encode('untextured', obj)
        self.assertNotIn('images', doc)
        self.assertIn('TEXCOORD_0', doc['meshes'][0]['primitives'][0]['attributes'])

    def test_duplicate_joint_influences_merge_and_empty_weights_get_a_valid_root(self):
        obj = model(skinned=True)
        obj.BI = np.tile([1, 1, 0, 0], (3, 1))
        obj.BW[0] = [0, 0, 0, 0]
        doc, binary, _ = self.encode('repaired-weights', obj)
        attrs = doc['meshes'][0]['primitives'][0]['attributes']
        joints = accessor(doc, binary, attrs['JOINTS_0']); weights = accessor(doc, binary, attrs['WEIGHTS_0'])
        np.testing.assert_array_equal(weights[:, 0], 1)
        np.testing.assert_array_equal(weights[:, 1:], 0)
        np.testing.assert_array_equal(joints[:, 0], [0, 1, 1])
        skinned_node = next(i for i, n in enumerate(doc['nodes']) if 'skin' in n)
        self.assertIn(skinned_node, doc['scenes'][0]['nodes'])


class ExplorerGLB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ts3-glb-'); self.root = Path(self.tmp.name)
        self.game = self.root / 'game'; (self.game / 'assets').mkdir(parents=True); (self.game / 'data_dx').mkdir()
        self.files, self.tree = F.scene([F.rigid_piece((3, 1, 0))])
        self.archive = self.game / 'assets/scene.zip'
        self.archive.write_bytes(install.write_zip([install.entry(n.encode(), raw) for n, raw in self.files.items()]))
        self.before = self.archive.read_bytes(); self.browser = explorer.Browser(self.game, self.root / 'cache')
        self.output = self.root / 'export'

    def tearDown(self):
        self.tmp.cleanup()

    def test_archive_and_loose_exports_preserve_world_positions_without_game_writes(self):
        report = self.browser.export_glb('assets/scene.zip', None, self.output)
        doc, binary = parse((self.output / 'model.glb').read_bytes())
        attrs = doc['meshes'][0]['primitives'][0]['attributes']
        np.testing.assert_array_equal(accessor(doc, binary, attrs['POSITION'])[0], [3, 1, 0])
        self.assertEqual(report['bones'], 0)
        self.assertEqual(self.archive.read_bytes(), self.before)
        for name, raw in self.files.items(): (self.game / 'assets' / name).write_bytes(raw)
        self.browser.export_glb('assets/scene.oct', None, self.root / 'loose')
        self.assertEqual((self.root / 'loose/model.glb').read_bytes(), (self.output / 'model.glb').read_bytes())
        self.assertFalse((self.game / 'TS3 Modding Tool').exists())

    def test_destination_rules_and_source_race_never_publish_output(self):
        for out in (self.game / 'bad', self.root):
            with self.assertRaises(ModError): self.browser.export_glb('assets/scene.zip', None, out)
        encode = gltf.encode
        def race(*args, **kwargs):
            result = encode(*args, **kwargs)
            self.archive.write_bytes(self.before + b'external')
            return result
        with patch.object(gltf, 'encode', side_effect=race), self.assertRaises(ModError) as caught:
            self.browser.export_glb('assets/scene.zip', None, self.output)
        self.assertEqual(caught.exception.code, 'source_changed')
        self.assertFalse(self.output.exists()); self.assertFalse(list(self.root.glob('.ts3-glb-*')))

    def test_mixed_oct_reader_exports_a_real_skin_without_rigging_static_piece(self):
        files, _ = F.scene([F.skinned_piece(), F.rigid_piece((3, 0, 0))],
                           bones=[('Hips', 10, None), ('Arm', 20, 1)], remaps=[[20, 10]])
        self.archive.write_bytes(install.write_zip([install.entry(n.encode(), raw) for n, raw in files.items()]))
        report = self.browser.export_glb('assets/scene.zip', None, self.output)
        doc, binary = parse((self.output / 'model.glb').read_bytes())
        self.assertEqual((report['bones'], report['triangles']), (2, 2))
        self.assertEqual(len([n for n in doc['nodes'] if 'mesh' in n]), 2)
        attrs = doc['meshes'][1]['primitives'][0]['attributes']
        np.testing.assert_array_equal(accessor(doc, binary, attrs['JOINTS_0'])[:, 0], 1)

    def test_original_resolution_diffuse_is_not_a_preview_thumbnail(self):
        out = io.BytesIO(); Image.new('RGB', (2048, 32), (40, 150, 20)).save(out, 'PNG')
        self.tree.extend([('TexturePool', [('Texture', [('Data', list(out.getvalue()))])]),
                          ('MaterialPool', [('Material', [('TextureEntry', [('Reference', [0]), ('Slot', 'diffuseMapA1')])])])])
        self.files['scene.oct'] = F.build_oct(self.tree)
        self.archive.write_bytes(install.write_zip([install.entry(n.encode(), raw) for n, raw in self.files.items()]))
        self.browser.export_glb('assets/scene.zip', None, self.output)
        doc, binary = parse((self.output / 'model.glb').read_bytes())
        view = doc['bufferViews'][doc['images'][0]['bufferView']]
        with Image.open(io.BytesIO(binary[view['byteOffset']:view['byteOffset'] + view['byteLength']])) as image:
            self.assertEqual(image.size, (2048, 32))

    def test_loose_buffer_race_and_size_limit_do_not_publish_output(self):
        for name, raw in self.files.items(): (self.game / 'assets' / name).write_bytes(raw)
        encode = gltf.encode
        def race(*args, **kwargs):
            result = encode(*args, **kwargs)
            (self.game / 'assets/scene_0.vbuf').write_bytes(b'changed')
            return result
        with patch.object(gltf, 'encode', side_effect=race), self.assertRaises(ModError) as caught:
            self.browser.export_glb('assets/scene.oct', None, self.output)
        self.assertEqual(caught.exception.code, 'source_changed'); self.assertFalse(self.output.exists())
        with patch.object(gltf, 'MAX_GLB', 64), self.assertRaises(ModError) as caught:
            self.browser.export_glb('assets/scene.zip', None, self.output)
        self.assertEqual(caught.exception.code, 'size_limit'); self.assertFalse(self.output.exists())

    def test_cli_export_and_machine_readable_rejection(self):
        env = dict(os.environ, TS3TOOL_SETTINGS=str(self.root / 'settings.json'))
        args = ENTRY + ['explore', 'glb', 'assets/scene.zip', '--out', str(self.output), '--game', str(self.game), '--json']
        result = subprocess.run(args, capture_output=True, encoding='utf-8', timeout=60, env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr); self.assertEqual(result.stderr, '')
        data = json.loads(result.stdout); self.assertEqual(data['command'], 'explore.glb')
        self.assertEqual(data['data']['triangles'], 1)
        raw = (self.output / 'model.glb').read_bytes(); parse(raw)
        if ARTIFACTS: (ARTIFACTS / 'explorer-cli.glb').write_bytes(raw)
        result = subprocess.run(args, capture_output=True, encoding='utf-8', timeout=60, env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'destination_exists')
        self.assertFalse((self.root / 'settings.json').exists())

    def test_cli_exports_mixed_skin_and_embedded_diffuse(self):
        files, tree = F.scene([F.skinned_piece(), F.rigid_piece((3, 0, 0))],
                               bones=[('Hips', 10, None), ('Arm', 20, 1)], remaps=[[20, 10]])
        png = io.BytesIO(); Image.new('RGB', (32, 16), (120, 40, 200)).save(png, 'PNG')
        tree.extend([('TexturePool', [('Texture', [('Data', list(png.getvalue()))])]),
                     ('MaterialPool', [('Material', [('TextureEntry', [('Reference', [0]), ('Slot', 'diffuseMapA1')])])])])
        files['scene.oct'] = F.build_oct(tree)
        self.archive.write_bytes(install.write_zip([install.entry(n.encode(), raw) for n, raw in files.items()]))
        args = ENTRY + ['explore', 'glb', 'assets/scene.zip', '--out', str(self.output), '--game', str(self.game), '--json']
        result = subprocess.run(args, capture_output=True, encoding='utf-8', timeout=60,
                                env=dict(os.environ, TS3TOOL_SETTINGS=str(self.root / 'settings.json')),
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr); self.assertEqual(result.stderr, '')
        raw = (self.output / 'model.glb').read_bytes(); doc, _ = parse(raw)
        self.assertEqual(len(doc['meshes']), 2); self.assertEqual(len(doc['skins'][0]['joints']), 2)
        self.assertEqual(len(doc['images']), 1)
        if ARTIFACTS: (ARTIFACTS / 'explorer-cli-skin.glb').write_bytes(raw)


if __name__ == '__main__':
    unittest.main()
