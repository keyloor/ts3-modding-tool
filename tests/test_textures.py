"""Synthetic texture workspace -> pack -> manager install/remove, with isolated settings.

python -I tests/test_textures.py [--exe PATH_TO_CONSOLE_EXE]
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
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'kit'))
import texpack
import ddsedit
import install
from modfile import ModError, Package
from modstore import Store
from octlib import Oct, Rec, NODE, SCALAR, LIST, NAME, BYTE, INT
from PIL import Image

ENTRY = [sys.executable, '-I', str(ROOT / 'kit/cli.py')]
if '--exe' in sys.argv:
    i = sys.argv.index('--exe'); ENTRY = [str(Path(sys.argv[i + 1]).resolve())]; del sys.argv[i:i + 2]


def dds(fmt='DXT5', size=(8, 4), mips=4, colour=(255, 0, 0, 255)):
    im = Image.new('RGBA', size, colour)
    header, body = None, bytearray()
    for _ in range(mips):
        stream = io.BytesIO()
        im.save(stream, 'DDS', **({'pixel_format': fmt} if fmt.startswith('DXT') else {}))
        raw = stream.getvalue()
        header = bytearray(raw[:128]) if header is None else header
        body.extend(raw[128:])
        im = im.resize((max(1, im.width // 2), max(1, im.height // 2)))
    struct.pack_into('<I', header, 28, mips)
    if fmt == 'RGBX32':
        struct.pack_into('<I', header, 80, 64)
        struct.pack_into('<I', header, 104, 0)
    return bytes(header + body)


def oct_textures(raws):
    names = ['', 'TexturePool', 'Texture', 'Name', 'Data', 'DataCRC'] + ['texture%d' % i for i in range(len(raws))]
    recs = [Rec(NODE, 0, 0, b''), Rec(NODE, 1, 1, b'')]
    for i, raw in enumerate(raws):
        data = Rec(LIST | BYTE << 3, 3, 4, b''); data.set_items(raw)
        crc = Rec(SCALAR | INT << 3, 3, 5, b''); crc.set_items([zlib.crc32(raw)])
        recs.extend([Rec(NODE, 2, 2, b''), Rec(SCALAR | NAME << 3, 3, 3, struct.pack('<H', 6 + i)), data, crc])
    f = Oct(names, recs, 0); f._tail = b''
    return f.to_bytes()


class DDS(unittest.TestCase):
    def test_rectangular_formats_mips_headers_and_colour(self):
        for fmt in ('DXT1', 'DXT3', 'DXT5', 'RGBA32', 'RGBX32'):
            with self.subTest(format=fmt):
                raw = dds(fmt)
                encoded = ddsedit.replace(raw, Image.new('RGBA', (8, 4), (0, 255, 0, 255)))
                self.assertEqual(encoded[:128], raw[:128])
                self.assertEqual(len(encoded), len(raw))
                info = ddsedit.layout(encoded)
                self.assertEqual((info['format'], info['mipmaps']), (fmt, 4))
                with Image.open(io.BytesIO(encoded)) as image:
                    self.assertEqual(image.convert('RGBA').getpixel((0, 0)), (0, 255, 0, 255))

    def test_dxt5_alpha_survives(self):
        encoded = ddsedit.replace(dds(), Image.new('RGBA', (8, 4), (255, 0, 0, 0)))
        with Image.open(io.BytesIO(encoded)) as image:
            self.assertEqual(image.convert('RGBA').getpixel((0, 0))[3], 0)

    def test_reject_size_cube_and_damaged_payload(self):
        with self.assertRaisesRegex(ModError, 'original texture dimensions'):
            ddsedit.replace(dds(), Image.new('RGB', (16, 8)))
        raw = bytearray(dds()); struct.pack_into('<I', raw, 112, 0x200)
        with self.assertRaises(ModError):
            ddsedit.layout(raw)
        with self.assertRaises(ModError):
            ddsedit.layout(dds()[:-1])


class TexturePacks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-textures-test-')
        self.root = Path(self.temp.name); self.game = self.root / 'game'
        (self.game / 'assets').mkdir(parents=True); (self.game / 'data_dx').mkdir()
        self.source = self.game / 'assets/test.zip'
        self.raws = [dds(), dds('DXT1')]
        self.oct = oct_textures(self.raws)
        self.before = install.write_zip([install.entry(b'test.oct', self.oct), install.entry(b'untouched.txt', b'keep')])
        self.source.write_bytes(self.before)
        self.work = self.root / 'workspace'; self.pack = self.root / 'pack'

    def tearDown(self):
        self.temp.cleanup()

    def dump(self):
        result = texpack.dump(self.game, 'assets/test.zip', self.work)
        self.assertFalse(result['errors'])
        return json.loads((self.work / 'index.json').read_text())

    def edit(self, row, size=(8, 4)):
        Image.new('RGBA', size, (0, 255, 0, 255)).save(self.work / row['png'])

    def build(self):
        return texpack.build(self.game, self.work, self.pack, mod_id='test.textures', name='Test textures', author='Test')

    def test_edit_pack_install_remove_byte_exact(self):
        data = self.dump(); self.edit(data['textures'][0])
        result = self.build()
        self.assertEqual((result['textures'], result['oct_files']), (1, 1))
        self.assertEqual(self.source.read_bytes(), self.before)
        with Package(self.pack) as package:
            self.assertEqual(package.metadata['id'], 'test.textures')
        store = Store(self.game); store._closed = lambda: None
        ticket = store.preview(self.pack)['ticket']; store.install(self.pack, expected=ticket)
        ents = install.read_zip(self.source.read_bytes())
        self.assertEqual(install.unpack(ents[1]), b'keep')
        f = Oct.parse(install.unpack(ents[0]))
        self.assertEqual(f.to_bytes(), install.unpack(ents[0]))
        pool = f.children(f.find('TexturePool')[0])
        changed = bytes(f.recs[f.child(pool[0], 'Data')].items()[1])
        self.assertEqual(f.value(f.child(pool[0], 'DataCRC'))[0] & 0xffffffff, zlib.crc32(changed))
        self.assertEqual(changed[:128], self.raws[0][:128])
        self.assertEqual(bytes(f.recs[f.child(pool[1], 'Data')].items()[1]), self.raws[1])
        with Image.open(io.BytesIO(changed)) as image:
            self.assertEqual(image.convert('RGBA').getpixel((0, 0)), (0, 255, 0, 255))
        store.remove('test.textures')
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_unchanged_deleted_and_resized_pngs(self):
        data = self.dump()
        with self.assertRaisesRegex(ModError, 'No changed PNGs'):
            self.build()
        (self.work / data['textures'][1]['png']).unlink()
        self.edit(data['textures'][0], (16, 8))
        with self.assertRaises(ModError) as caught:
            self.build()
        self.assertEqual(caught.exception.code, 'size_mismatch')
        self.assertFalse(self.pack.exists())
        self.edit(data['textures'][0]); self.build()

    def test_source_changed_existing_destination_and_game_destination(self):
        data = self.dump(); self.edit(data['textures'][0])
        self.source.write_bytes(self.before + b'changed')
        with self.assertRaises(ModError) as caught:
            self.build()
        self.assertEqual(caught.exception.code, 'source_changed')
        self.source.write_bytes(self.before)
        self.pack.mkdir()
        with self.assertRaises(ModError):
            self.build()
        with self.assertRaises(ModError):
            texpack.dump(self.game, 'assets/test.zip', self.game / 'dump')

    def test_manifest_paths_and_duplicate_targets(self):
        data = self.dump()
        data['textures'][0]['png'] = '../outside.png'
        (self.work / 'index.json').write_text(json.dumps(data))
        with self.assertRaises(ModError):
            self.build()
        self.assertFalse(self.pack.exists())

    def call(self, *args, code=0):
        env = dict(os.environ, TS3TOOL_SETTINGS=str(self.root / 'settings.json'))
        result = subprocess.run(ENTRY + ['textures', *map(str, args), '--game', str(self.game), '--json'],
                                capture_output=True, encoding='utf-8', env=env, timeout=60,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')
        parsed = json.loads(result.stdout); self.assertEqual(parsed['ok'], code == 0)
        return parsed

    def test_cli_entire_texture_workflow(self):
        result = self.call('dump', 'assets/test.zip', '--out', self.work)['data']
        self.assertEqual(result['textures'], 2)
        args = ['build', self.work, '--out', self.pack, '--id', 'test.textures', '--name', 'Test', '--author', 'Test']
        self.assertEqual(self.call(*args, code=3)['error']['code'], 'nothing_changed')
        data = json.loads((self.work / 'index.json').read_text()); self.edit(data['textures'][0])
        self.assertEqual(self.call(*args)['data']['textures'], 1)
        self.assertEqual(self.source.read_bytes(), self.before)
        self.assertFalse((self.root / 'settings.json').exists())

    def second_archive(self):
        source = self.game / 'assets/variant.zip'
        source.write_bytes(self.before)
        return source

    def multi_dump(self, shared=False):
        self.second_archive()
        result = texpack.dump(self.game, ['assets/test.zip', 'assets/variant.zip'], self.work, shared=shared)
        data = json.loads((self.work / 'index.json').read_bytes())
        self.assertEqual(data['schema_version'], 2)
        self.assertEqual((result['archives'], result['textures']), (2, 4))
        return result, data

    def test_multi_archive_separate_edits_only_selected_occurrence(self):
        result, data = self.multi_dump()
        self.assertEqual(result['png_files'], 4)
        self.assertNotEqual(data['textures'][0]['png'], data['textures'][2]['png'])
        self.edit(data['textures'][0])
        result = self.build()
        self.assertEqual((result['archives'], result['textures']), (1, 1))
        store = Store(self.game); store._closed = lambda: None
        store.install(self.pack)
        self.assertNotEqual(self.source.read_bytes(), self.before)
        self.assertEqual((self.game / 'assets/variant.zip').read_bytes(), self.before)
        store.remove('test.textures')
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_shared_png_updates_both_archives_and_restores_exactly(self):
        result, data = self.multi_dump(shared=True)
        self.assertEqual(result['png_files'], 2)
        self.assertEqual(data['textures'][0]['png'], data['textures'][2]['png'])
        self.assertNotEqual(data['textures'][0]['png'], data['textures'][1]['png'])  # Same colour, different DDS format.
        self.edit(data['textures'][0]); result = self.build()
        self.assertEqual((result['png_files'], result['textures'], result['archives'], result['oct_files']), (1, 2, 2, 2))
        store = Store(self.game); store._closed = lambda: None
        plan = store.preview(self.pack)
        self.assertEqual(len(plan['files']), 2)
        store.install(self.pack, expected=plan['ticket'])
        self.assertTrue(store.verify('test.textures')['valid'])
        for archive in (self.source, self.game / 'assets/variant.zip'):
            entries = install.read_zip(archive.read_bytes())
            self.assertEqual(install.unpack(entries[1]), b'keep')
            f = Oct.parse(install.unpack(entries[0])); pool = f.children(f.find('TexturePool')[0])
            raw = bytes(f.recs[f.child(pool[0], 'Data')].items()[1])
            with Image.open(io.BytesIO(raw)) as image:
                self.assertEqual(image.convert('RGBA').getpixel((0, 0)), (0, 255, 0, 255))
            self.assertEqual(bytes(f.recs[f.child(pool[1], 'Data')].items()[1]), self.raws[1])
        store.remove('test.textures')
        self.assertEqual(self.source.read_bytes(), self.before)
        self.assertEqual((self.game / 'assets/variant.zip').read_bytes(), self.before)

    def test_shared_scope_is_only_selected_archives_and_deleted_png_skips_whole_group(self):
        outside = self.game / 'assets/unselected.zip'; outside.write_bytes(self.before)
        _, data = self.multi_dump(shared=True)
        (self.work / data['textures'][0]['png']).unlink()
        self.edit(data['textures'][1]); result = self.build()
        self.assertEqual((result['png_files'], result['textures']), (1, 2))
        store = Store(self.game); store._closed = lambda: None; store.install(self.pack)
        self.assertEqual(outside.read_bytes(), self.before)
        entries = install.read_zip(self.source.read_bytes())
        f = Oct.parse(install.unpack(entries[0])); pool = f.children(f.find('TexturePool')[0])
        self.assertEqual(bytes(f.recs[f.child(pool[0], 'Data')].items()[1]), self.raws[0])

    def test_crc_collision_does_not_share_different_dds(self):
        self.second_archive()
        with patch.object(texpack.zlib, 'crc32', return_value=0):
            result = texpack.dump(self.game, ['assets/test.zip', 'assets/variant.zip'], self.work, shared=True)
        self.assertEqual(result['png_files'], 2)
        data = json.loads((self.work / 'index.json').read_bytes())
        self.assertNotEqual(data['textures'][0]['png'], data['textures'][1]['png'])
        self.assertTrue(all(Path(r['png']).name.startswith('00000000_') for r in data['textures']))
        self.edit(data['textures'][0]); self.assertEqual(self.build()['textures'], 2)

    def test_any_changed_source_blocks_multi_archive_pack_without_output(self):
        _, data = self.multi_dump()
        self.edit(data['textures'][0])
        other = self.game / 'assets/variant.zip'; other.write_bytes(self.before + b'changed')
        with self.assertRaises(ModError) as caught:
            self.build()
        self.assertEqual(caught.exception.code, 'source_changed')
        self.assertFalse(self.pack.exists())
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_shared_index_cannot_alias_different_textures_or_unknown_archives(self):
        _, original = self.multi_dump(shared=True)
        for kind in ('different_dds', 'unknown_archive', 'duplicate_texture', 'duplicate_archive', 'invalid_hash'):
            data = json.loads(json.dumps(original))
            if kind == 'different_dds':
                data['textures'][1]['png'] = data['textures'][0]['png']
            elif kind == 'unknown_archive':
                data['textures'][0]['archive'] = 'assets/unknown.zip'
            elif kind == 'duplicate_texture':
                data['textures'].append(data['textures'][0])
            elif kind == 'duplicate_archive':
                data['archives'].append(data['archives'][0])
            else:
                data['archives'][0]['sha256'] = 'not a hash'
            (self.work / 'index.json').write_text(json.dumps(data), encoding='utf-8')
            with self.subTest(kind=kind), self.assertRaises(ModError):
                self.build()
            self.assertFalse(self.pack.exists())

    def test_failure_in_later_archive_never_publishes_partial_pack(self):
        _, data = self.multi_dump(shared=True); self.edit(data['textures'][0])
        original = texpack.patch_archive; calls = []
        def fail(source, replacements):
            calls.append(True)
            if len(calls) == 2:
                raise OSError('simulated second archive failure')
            return original(source, replacements)
        with patch.object(texpack, 'patch_archive', side_effect=fail), self.assertRaises(OSError):
            self.build()
        self.assertFalse(self.pack.exists())
        self.assertFalse(list(self.root.glob('.ts3-texpack-*')))
        self.assertEqual(self.source.read_bytes(), self.before)
        self.assertEqual((self.game / 'assets/variant.zip').read_bytes(), self.before)

    def test_multi_archive_replacement_restores_originals_after_second_pack(self):
        _, data = self.multi_dump(shared=True); self.edit(data['textures'][0]); self.build()
        Image.new('RGBA', (8, 4), (0, 0, 255, 255)).save(self.work / data['textures'][0]['png'])
        second = self.root / 'second-pack'
        texpack.build(self.game, self.work, second, mod_id='test.textures', name='Test v2', author='Test', version='2.0')
        store = Store(self.game); store._closed = lambda: None; store.install(self.pack)
        plan = store.preview(second, replace=True); store.install(second, replace=True, expected=plan['ticket'])
        self.assertTrue(store.verify('test.textures')['valid'])
        store.remove('test.textures')
        self.assertEqual(self.source.read_bytes(), self.before)
        self.assertEqual((self.game / 'assets/variant.zip').read_bytes(), self.before)

    def test_cli_multi_archive_shared_workflow_and_member_restriction(self):
        self.second_archive()
        rejected = self.call('dump', 'assets/test.zip', 'assets/variant.zip', '--member', 'test.oct', '--out', self.work, code=2)
        self.assertEqual(rejected['error']['code'], 'invalid_arguments')
        self.assertFalse(self.work.exists())
        result = self.call('dump', 'assets/test.zip', 'assets/variant.zip', '--shared', '--out', self.work)['data']
        self.assertEqual((result['archives'], result['png_files'], result['textures']), (2, 2, 4))
        data = json.loads((self.work / 'index.json').read_bytes()); self.edit(data['textures'][0])
        result = self.call('build', self.work, '--out', self.pack, '--id', 'test.textures', '--name', 'Shared', '--author', 'Test')['data']
        self.assertEqual((result['archives'], result['textures']), (2, 2))

    def test_v1_remains_readable_and_workspace_is_not_rewritten(self):
        data = self.dump(); self.assertEqual(data['schema_version'], 1)
        before = (self.work / 'index.json').read_bytes()
        _, normalized = texpack.workspace(self.work)
        self.assertEqual(normalized['archives'][0]['path'], 'assets/test.zip')
        self.edit(data['textures'][0]); self.build()
        self.assertEqual((self.work / 'index.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
