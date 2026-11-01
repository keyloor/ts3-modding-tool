"""Synthetic explorer checks; never reads a real game or the user's settings.

python -I tests/test_explorer.py [--exe PATH_TO_CONSOLE_EXE]
"""
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'kit'))
import explorer as E
from modfile import ModError
import install
from octlib import Oct, Rec, NODE, SCALAR, NAME, BYTE, LIST, FLOAT, INT
from PIL import Image
import numpy as np
import viewer as V

ENTRY = [sys.executable, '-I', str(ROOT / 'kit/cli.py')]
if '--exe' in sys.argv:
    i = sys.argv.index('--exe')
    ENTRY = [str(Path(sys.argv[i + 1]).resolve())]
    del sys.argv[i:i + 2]


def texture_oct(png):
    names = ['', 'TexturePool', 'Texture', 'Name', 'Synthetic', 'Data']
    recs = [Rec(NODE, 0, 0, b''), Rec(NODE, 1, 1, b''), Rec(NODE, 2, 2, b''),
            Rec(SCALAR | NAME << 3, 3, 3, struct.pack('<H', 4))]
    raw = Rec(LIST | BYTE << 3, 3, 5, b'')
    raw.set_items(png); recs.append(raw)
    f = Oct(names, recs, 0); f._tail = b''
    return f.to_bytes()


def build_oct(tree):
    """an .oct from nested (name, value): a list of pairs is a node, a str a name, a list of numbers a list"""
    names, recs = [''], [Rec(NODE, 0, 0, b'')]

    def name(text):
        if text not in names:
            names.append(text)
        return names.index(text)

    def add(pairs, level):
        for key, value in pairs:
            if isinstance(value, str):
                recs.append(Rec(SCALAR | NAME << 3, level, name(key), struct.pack('<H', name(value))))
            elif value and isinstance(value[0], tuple) or value == []:
                recs.append(Rec(NODE, level, name(key), b''))
                add(value, level + 1)
            else:
                kind = FLOAT if any(isinstance(x, float) for x in value) else INT
                rec = Rec(LIST | kind << 3, level, name(key), b'')
                rec.set_items(value)
                recs.append(rec)
    add(tree, 1)
    f = Oct(names, recs, 0); f._tail = b''
    return f.to_bytes()


IDENTITY = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]


def rigid_piece(geometry_at=(0, 0, 0), bare=False, hidden=False, grid=0):
    """what scene() needs for one rigid piece: position + uv and a normal stream, or only positions"""
    n = max(3, grid)
    p = np.zeros(n, [('p', '<f4', 3), ('uv', '<f2', 2)])
    p['p'][:3] = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    p['uv'][1] = [0.5, 0.25]
    if grid:
        p['p'][3:] = np.c_[np.arange(n - 3) % 7, np.arange(n - 3) % 3, np.zeros(n - 3)]
    nrm = np.zeros(n, [('n', '<f2', 4)]); nrm['n'][:, 2] = 1
    tri = np.arange(n - n % 3, dtype='<u2')
    if bare:
        return dict(kind='SubGeometry', streams=[([('Position', 2, 0)], 12, p['p'].tobytes(), n)], tri=tri, at=geometry_at, hidden=hidden)
    return dict(kind='SubGeometryLit', tri=tri, at=geometry_at, hidden=hidden,
                streams=[([('Position', 2, 0), ('Uv1', 44, 12)], 16, p.tobytes(), n), ([('Normal', 45, 0)], 8, nrm.tobytes(), n)])


def skinned_piece():
    v = np.zeros(3, [('p', '<f4', 3), ('bi', 'u1', 4), ('bw', 'u1', 4), ('uv', '<f2', 2)])
    v['p'] = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    v['bw'][:, 0] = 255
    return dict(kind='SubGeometryLit', tri=np.arange(3, dtype='<u2'), at=(0, 0, 0), hidden=False, sc=0,
                streams=[([('Position', 2, 0), ('BoneIndices', 24, 12), ('BlendWeights', 25, 16), ('Uv1', 44, 20)], 24, v.tobytes(), 3)])


def scene(pieces, bones=(), remaps=()):
    """a synthetic model: ({file name: bytes}, its .oct's tree), the same pools the game's files have"""
    vb, ib, streams, istreams, nodes = b'', b'', [], [], [('Node', [('Type', 'Scene')])]
    for name_, bone_id, parent in bones:
        nodes.append(('Node', [('Type', 'Bone'), ('NodeName', name_), ('BoneID', [bone_id]),
                               ('ParentNodeReferences', [parent if parent is not None else 0]),
                               ('PivotPoint', [0.0, 0.0, 0.0]), ('LocalToParentMatrix', IDENTITY)]))
    for piece in pieces:
        refs = []
        for els, width, raw, count in piece['streams']:
            refs.append(len(streams))
            streams.append(('VertexStream', [
                ('Length', [count]), ('Width', [width]), ('ExtraStride', [0]), ('VertexBufferReference', [0]),
                ('VertexBufferOffset', [len(vb)]),
                ('Elements', [('Element', [('Type', [t]), ('Name', n), ('Offset', [o])]) for n, t, o in els])]))
            vb += raw
        istreams.append(('IndexStream', [('Length', [len(piece['tri'])]), ('IndexBufferReference', [0]),
                                         ('IndexBufferOffset', [len(ib)]), ('IndexStreamPrimitive', 'TRIANGLES')]))
        ib += piece['tri'].tobytes()
        matrix = IDENTITY[:12] + [float(x) for x in piece['at']] + [1.0]
        nodes.append(('Node', [('Type', 'Geometry'), ('NodeName', 'geo'), ('ParentNodeReferences', [0]),
                               ('Visible', [0 if piece['hidden'] else 1]), ('LocalToParentMatrix', matrix)]))
        fields = [('Type', piece['kind']), ('NodeName', 'piece'), ('ParentNodeReferences', [len(nodes) - 1]),
                  ('LocalToParentMatrix', IDENTITY), ('MaterialReference', [0]), ('VertexStreamReferences', refs),
                  ('IndexStreamReference', [len(istreams) - 1])]
        if 'sc' in piece:
            fields.append(('SceneComponentReferences', [piece['sc']]))
        nodes.append(('Node', fields))
    tree = [('SceneTreeNodePool', nodes), ('VertexStreamPool', streams), ('IndexStreamPool', istreams),
            ('VertexBufferPool', [('VertexBuffer', [('Name', 'Static'), ('FileName', 'scene_0.vbuf')]),
                                  ('VertexBuffer', [('Name', 'Dynamic')])]),
            ('IndexBufferPool', [('IndexBuffer', [('Width', [2]), ('Name', 'Static'), ('FileName', 'scene_0.ibuf')])])]
    if remaps:
        tree.append(('SceneComponentPool', [('SceneComponent', [('Type', 'SkinRemap'), ('RemapData', list(r))]) for r in remaps]))
    return {'scene.oct': build_oct(tree), 'scene_0.vbuf': vb, 'scene_0.ibuf': ib}, tree


class Explorer(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-explorer-test-')
        self.root = Path(self.temp.name)
        self.game = self.root / 'game'
        (self.game / 'assets').mkdir(parents=True)
        (self.game / 'data_dx').mkdir()
        self.path = 'assets/test.zip'
        self.zip = self.game / self.path
        out = io.BytesIO(); Image.new('RGBA', (16, 8), (255, 30, 40, 128)).save(out, format='PNG')
        self.png = out.getvalue()
        self.items = {'folder/notes.txt': b'hello', 'texture.png': self.png, 'model.oct': texture_oct(self.png)}
        self.write_zip()
        (self.game / 'data_dx/info.txt').write_text('loose text', encoding='utf-8')
        self.browser = E.Browser(self.game, self.root / 'cache')

    def tearDown(self):
        self.temp.cleanup()

    def write_zip(self, items=None):
        self.zip.write_bytes(install.write_zip([install.entry(n.encode(), b) for n, b in (items or self.items).items()]))

    def test_index_reads_directory_only_and_invalidates_cache(self):
        with patch.object(zipfile.ZipFile, 'read', side_effect=AssertionError('decompressed while indexing')):
            index = self.browser.index()
        self.assertEqual(len(E.Browser.search(index)), 5)
        self.assertFalse(index['errors'])
        with patch.object(E, 'directory', side_effect=AssertionError('cache not reused')):
            self.assertEqual(self.browser.index()['reused'], 2)
        self.write_zip({'new.txt': b'new content'})
        index = self.browser.index()
        self.assertEqual(index['reused'], 1)
        self.assertEqual(E.Browser.search(index, 'NEW.TXT')[0]['member'], 'new.txt')
        self.zip.unlink()
        self.assertEqual(len(self.browser.index()['files']), 1)

    def test_invalid_cache_and_broken_archive_do_not_hide_other_files(self):
        self.browser.cache.mkdir()
        self.browser.cache_file.write_text('{broken')
        (self.game / 'assets/broken.zip').write_bytes(b'bad')
        index = self.browser.index()
        self.assertEqual(len(index['errors']), 1)
        self.assertEqual(len(E.Browser.search(index, category='text')), 2)

    def test_front_directory_archive_and_crc(self):
        raw = self.zip.read_bytes()
        _, _, _, _, count, length, offset, _ = struct.unpack('<IHHHHIIH', raw[:22])
        front = bytearray(raw[:offset])
        struct.pack_into('<I', front, 16, 22)
        self.zip.write_bytes(front)
        self.assertEqual(len(E.directory(self.zip)), count)
        self.assertEqual(self.browser.read(self.path, 'folder/notes.txt'), b'hello')
        # Bad compressed content is refused, not silently exported.
        info = E.FrontZip(self.zip)
        first = info.entries[0]; info.file.close()
        start = first.header_offset + 30 + len(first.filename)
        front[start] ^= 0xFF
        self.zip.write_bytes(front)
        with self.assertRaises((ValueError, zipfile.BadZipFile, E.zlib.error)):
            self.browser.export(self.path, 'folder/notes.txt', self.root / 'bad-export')
        self.assertFalse((self.root / 'bad-export').exists())

    def test_standard_zip(self):
        with zipfile.ZipFile(self.zip, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('música.txt', 'hola')
        self.assertEqual(self.browser.read(self.path, 'música.txt'), b'hola')

    def test_inspection_and_texture_previews(self):
        info = self.browser.inspect(self.path, 'model.oct')
        self.assertEqual(info['pools'], {'TexturePool': 1})
        self.assertEqual((info['textures'][0]['width'], info['textures'][0]['height']), (16, 8))
        images, model = self.browser.preview(self.path, 'model.oct')
        self.assertIsNone(model)
        self.assertEqual(images['textures-01'].size, (800, 194))
        out = self.browser.export(self.path, 'texture.png', self.root / 'preview', preview=True)
        with Image.open(Path(out['output']) / out['files'][0]) as image:
            self.assertEqual(image.getpixel((0, 0)), (255, 30, 40, 128))

    def test_extraction_roundtrip_and_existing_destination(self):
        before = self.zip.read_bytes()
        dest = self.root / 'output'
        self.browser.export(self.path, None, dest)
        for name, data in self.items.items():
            self.assertEqual((dest / name).read_bytes(), data)
        with self.assertRaisesRegex(ModError, 'new output folder'):
            self.browser.export(self.path, None, dest)
        self.assertEqual(self.zip.read_bytes(), before)
        with self.assertRaisesRegex(ModError, 'outside the game'):
            self.browser.export(self.path, None, self.game / 'output')

    def test_missing_member_and_unsafe_source(self):
        for path in ('../outside.txt', 'assets/../outside.txt', 'data_dx/NUL.txt', 'C:/outside.txt'):
            with self.subTest(path=path), self.assertRaises(ModError):
                self.browser.read(path)
        with self.assertRaisesRegex(ModError, 'not found'):
            self.browser.read(self.path, 'absent')

    def test_unsafe_and_duplicate_members_rejected_before_export(self):
        for names in (['../escape'], ['/absolute'], ['NUL'], ['a:stream'], ['A.txt', 'a.txt'], ['a', 'a/b']):
            with self.subTest(names=names):
                self.write_zip({name: b'x' for name in names})
                with self.assertRaises(ModError):
                    self.browser.export(self.path, None, self.root / 'export')
                self.assertFalse((self.root / 'export').exists())

    def test_limits_and_source_change_leave_no_partial_export(self):
        with patch.object(E, 'MAX_FILE', 2), self.assertRaises(ModError):
            self.browser.export(self.path, None, self.root / 'large')
        self.assertFalse((self.root / 'large').exists())
        read = self.browser.read
        def changed(*args):
            data = read(*args)
            self.write_zip({'changed': b'new'})
            return data
        with patch.object(self.browser, 'read', side_effect=changed), self.assertRaises(ModError):
            self.browser.export(self.path, 'folder/notes.txt', self.root / 'changed')
        self.assertFalse((self.root / 'changed').exists())

    def test_cache_is_never_trusted_for_extraction(self):
        self.browser.index()
        self.write_zip({'different.txt': b'current'})
        with self.assertRaises(ModError):
            self.browser.read(self.path, 'folder/notes.txt')

    def test_rigid_piece_is_placed_by_its_nodes(self):
        files, _ = scene([rigid_piece(geometry_at=(5, 0, 0))])
        model = V.GameModel(files['scene.oct'], files.get)
        np.testing.assert_allclose(model.P0, [[5, 0, 0], [6, 0, 0], [5, 1, 0]])
        np.testing.assert_allclose(model.N0[0], [0, 0, 1])
        np.testing.assert_allclose(model.UV[1], [0.5, 0.25])
        self.assertEqual((model.pieces, model.skipped, model.triangles, model.names), (1, 0, 1, ['Root']))
        model.pose()                                   # the view's interface
        np.testing.assert_allclose(model.P, model.P0)

    def test_volumes_and_hidden_pieces_are_left_out_unless_there_is_nothing_else(self):
        files, _ = scene([rigid_piece(), rigid_piece(bare=True), rigid_piece(hidden=True)])
        model = V.GameModel(files['scene.oct'], files.get)
        self.assertEqual((model.pieces, model.skipped), (1, 2))
        files, _ = scene([rigid_piece(bare=True)])     # foliage with only positions still shows
        model = V.GameModel(files['scene.oct'], files.get)
        self.assertEqual(model.pieces, 1)
        np.testing.assert_allclose(np.linalg.norm(model.N0, axis=1), 1)    # normals from its triangles

    def test_skinned_piece_keeps_its_bones(self):
        files, _ = scene([skinned_piece()], bones=[('Hips', 10, None), ('Arm', 20, 1)], remaps=[[20, 10]])
        model = V.GameModel(files['scene.oct'], files.get)
        self.assertEqual(model.names, ['Hips', 'Arm'])
        np.testing.assert_array_equal(model.BI[0], [1, 1, 1, 1])         # remap slot 0 -> BoneID 20 -> Arm
        self.assertEqual(model.parent.tolist(), [-1, 0])

    def test_no_geometry_and_a_buffer_that_is_absent(self):
        with self.assertRaises(ValueError):
            V.GameModel(texture_oct(self.png), lambda name: None)
        files, _ = scene([rigid_piece()])
        with self.assertRaises(ValueError):
            V.GameModel(files['scene.oct'], lambda name: None)

    def test_framing_leaves_out_the_sky_but_keeps_its_size(self):
        files, _ = scene([rigid_piece(grid=300), rigid_piece(geometry_at=(5000, 0, 0))])
        model = V.GameModel(files['scene.oct'], files.get)
        self.assertLess(float(max(model.bounds()[1] - model.bounds()[0])), 50)
        self.assertGreater(model.full_extent, 4000)

    def test_snapshot_fills_triangles_without_holes(self):
        files, _ = scene([rigid_piece()])
        image = np.asarray(V.snapshot(V.GameModel(files['scene.oct'], files.get), size=200))
        background = (image == 235).all(2)
        self.assertLess(background[150, 20:90].sum(), 1)   # inside the triangle: not one pixel missed
        self.assertTrue(background[30, 170])               # outside it

    def test_preview_and_inspect_of_a_model_in_an_archive(self):
        files, _ = scene([rigid_piece()])
        items = {'test.oct': files['scene.oct'], 'scene_0.vbuf': files['scene_0.vbuf'], 'scene_0.ibuf': files['scene_0.ibuf']}
        self.write_zip(items)
        info = self.browser.inspect(self.path, 'test.oct')
        self.assertEqual({k: info['model'][k] for k in ('vertices', 'triangles', 'pieces', 'pieces_left_out', 'bones')},
                         dict(vertices=3, triangles=1, pieces=1, pieces_left_out=0, bones=0))
        images, model = self.browser.preview(self.path, 'test.oct')
        self.assertEqual((model.triangles, images['model'].size), (1, (720, 720)))
        images, model = self.browser.preview(self.path)    # the archive's row: its main model
        self.assertIn('model', images)
        out = self.browser.export(self.path, 'test.oct', self.root / 'png', preview=True)
        self.assertIn('model.png', out['files'])

    def test_extracting_an_archive_reads_its_directory_once(self):
        self.write_zip({'m%03d.txt' % n: b'x' for n in range(40)})
        real, calls = E.directory, []
        with patch.object(E, 'directory', side_effect=lambda p: calls.append(p) or real(p)):
            out = self.browser.export(self.path, None, self.root / 'all')
        self.assertEqual((len(out['files']), len(calls)), (40, 1))

    def call(self, *args, code=0):
        env = dict(os.environ, TS3TOOL_SETTINGS=str(self.root / 'isolated-settings.json'))
        proc = subprocess.run(ENTRY + ['explore', *map(str, args), '--game', str(self.game), '--json'],
                              capture_output=True, encoding='utf-8', env=env, timeout=60,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        self.assertEqual(proc.stderr, '')
        self.assertEqual(len(proc.stdout.strip().splitlines()), 1)
        result = json.loads(proc.stdout)
        self.assertEqual(result['ok'], code == 0)
        return result

    def test_cli_model_inspect_and_preview(self):
        """also through the console .exe (--exe): it has no tkinter, so the model code must not need it"""
        files, _ = scene([rigid_piece()])
        self.write_zip({'test.oct': files['scene.oct'], 'scene_0.vbuf': files['scene_0.vbuf'], 'scene_0.ibuf': files['scene_0.ibuf']})
        model = self.call('inspect', self.path, '--member', 'test.oct')['data']['model']
        self.assertEqual((model['vertices'], model['triangles'], model['pieces']), (3, 1, 1))
        out = self.call('preview', self.path, '--out', self.root / 'cli-model')['data']       # a ZIP: its main model
        self.assertIn('model.png', out['files'])
        with Image.open(self.root / 'cli-model' / 'model.png') as image:
            self.assertEqual(image.size, (720, 720))

    def test_cli_search_inspect_extract_preview_and_errors(self):
        result = self.call('list', '--query', 'texture', '--limit', 1)['data']
        self.assertEqual(result['total'], 1)
        self.assertIsNone(result['next_offset'])
        self.assertEqual(self.call('inspect', self.path, '--member', 'folder/notes.txt')['data']['text'], 'hello')
        self.call('extract', self.path, '--member', 'folder/notes.txt', '--out', self.root / 'cli-extract')
        self.call('preview', self.path, '--member', 'texture.png', '--out', self.root / 'cli-preview')
        self.assertEqual(self.call('inspect', self.path, '--member', 'missing', code=3)['error']['code'], 'not_found')
        self.assertEqual(self.call('list', '--limit', 0, code=2)['error']['code'], 'invalid_arguments')
        self.assertFalse((self.root / 'isolated-settings.json').exists())


if __name__ == '__main__':
    unittest.main()
