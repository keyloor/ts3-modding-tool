"""Synthetic package / fake game integration tests. No game data and no user settings.

Run: python -I tests/test_mods.py
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'kit'))
import modfile as MF
import modstore as MS
import install as INS


class Mods(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-mods-test-')
        self.root = Path(self.temp.name)
        self.game = self.root / 'game'
        (self.game / 'assets/characters').mkdir(parents=True)
        (self.game / 'data_dx').mkdir()
        self.live = self.game / 'data_dx/music.bank'
        self.live.write_bytes(b'original music')
        self.store = MS.Store(self.game)
        self.closed = patch.object(INS, 'game_running', return_value=False)
        self.closed.start()

    def tearDown(self):
        self.closed.stop()
        self.temp.cleanup()

    def package(self, mid='test.music', target='data_dx/music.bank', content=b'new music', **extra):
        root = self.root / mid
        root.mkdir(exist_ok=True)
        (root / 'payload.bin').write_bytes(content)
        meta = {'schema_version': 1, 'id': mid, 'name': 'Música de prueba', 'version': '1.0',
                'author': 'Test', 'description': 'Synthetic test', 'game': 'ts3-pc',
                'files': [{'source': 'payload.bin', 'target': target}], **extra}
        (root / 'mod.json').write_bytes(MF.json_bytes(meta))
        return root

    def test_file_roundtrip_and_new_file(self):
        src = self.package()
        self.store.install(src)
        self.assertEqual(self.live.read_bytes(), b'new music')
        self.assertEqual(self.store.list()[0]['metadata']['version'], '1.0.0')
        self.store.install(self.package('test.new', 'assets/new.bin', b'added'))
        self.store.remove('test.music')
        self.assertEqual(self.live.read_bytes(), b'original music')
        self.store.remove('test.new')
        self.assertFalse((self.game / 'assets/new.bin').exists())
        self.assertEqual(self.store.list(), [])

    def test_preview_does_not_change_game_and_ticket_detects_changed_package(self):
        src = self.package()
        result = self.store.preview(src)
        self.assertEqual(self.live.read_bytes(), b'original music')
        self.assertFalse(self.store.path(MS.REGISTRY).exists())
        self.assertFalse(self.store.path(MS.HOME + '/objects').exists())
        (src / 'payload.bin').write_bytes(b'changed after preview')
        with self.assertRaisesRegex(MF.ModError, 'changed since preview'):
            self.store.install(src, expected=result['ticket'])
        self.assertEqual(self.live.read_bytes(), b'original music')

    def test_preview_ticket_detects_external_change_and_allows_unchanged_install(self):
        src = self.package()
        result = self.store.preview(src)
        self.live.write_bytes(b'external before confirm')
        with self.assertRaisesRegex(MF.ModError, 'changed since preview'):
            self.store.install(src, expected=result['ticket'])
        result = self.store.preview(src)
        self.store.install(src, expected=result['ticket'])
        self.store.remove('test.music')
        self.assertEqual(self.live.read_bytes(), b'external before confirm')

    def test_wrapped_zip_and_legacy_layout(self):
        src = self.package()
        dest = self.root / 'wrapped.zip'
        with zipfile.ZipFile(dest, 'w') as z:
            for f in src.iterdir():
                z.write(f, 'Pretty folder/' + f.name)
        self.store.install(dest)
        self.store.remove('test.music')
        legacy = self.root / 'old.zip'
        with zipfile.ZipFile(legacy, 'w') as z:
            z.writestr('Old mod/data_dx/music.bank', b'old mod')
            z.writestr('Old mod/install.bat', b'exit 99')
        meta = self.store.install(legacy)
        self.assertTrue(meta['id'].startswith('legacy.'))
        self.assertFalse((self.game / 'install.bat').exists())
        self.store.remove(meta['id'])
        self.assertEqual(self.live.read_bytes(), b'original music')

    def test_target_conflict_and_external_edit(self):
        self.store.install(self.package())
        with self.assertRaisesRegex(MF.ModError, 'conflict'):
            self.store.install(self.package('test.other'))
        self.live.write_bytes(b'external edit')
        with self.assertRaisesRegex(MF.ModError, 'outside'):
            self.store.remove('test.music')
        self.assertEqual(self.live.read_bytes(), b'external edit')
        self.assertEqual(len(self.store.list()), 1)

    def test_dependencies_and_bidirectional_conflicts(self):
        dep = self.package('test.child', 'assets/child.bin', requires=[{'id': 'test.music', 'version': '>=1.0'}])
        with self.assertRaisesRegex(MF.ModError, 'dependency'):
            self.store.install(dep)
        self.store.install(self.package(conflicts=[{'id': 'test.blocked', 'version': '*'}]))
        self.store.install(dep)
        with self.assertRaisesRegex(MF.ModError, 'dependent'):
            self.store.remove('test.music')
        with self.assertRaisesRegex(MF.ModError, 'declared conflict'):
            self.store.install(self.package('test.blocked', 'assets/block.bin'))
        self.store.remove('test.child')
        self.store.remove('test.music')

    def two_files(self):
        return self.package(files=[{'source': 'payload.bin', 'target': 'data_dx/music.bank'},
                                   {'source': 'payload.bin', 'target': 'assets/new.bin'}])

    def test_failure_rolls_back_every_file(self):
        original = self.store._put
        calls = []
        def fail(rel, data):
            calls.append(rel)
            if len(calls) == 2:
                raise OSError('simulated disk error')
            return original(rel, data)
        with patch.object(self.store, '_put', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'disk error'):
                self.store.install(self.two_files())
        self.assertEqual(self.live.read_bytes(), b'original music')
        self.assertFalse((self.game / 'assets/new.bin').exists())
        self.assertEqual(self.store.list(), [])
        self.assertFalse(self.store.path(MS.JOURNAL).exists())

    def test_interrupted_install_recovers_in_new_process_instance(self):
        original = self.store._put
        def crash(rel, data):
            original(rel, data)
            if rel == MS.REGISTRY:
                raise KeyboardInterrupt('simulated termination after registry write')
        with patch.object(self.store, '_put', side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):
                self.store.install(self.two_files())
        fresh = MS.Store(self.game)
        self.assertTrue(fresh.recover())
        self.assertEqual(self.live.read_bytes(), b'original music')
        self.assertFalse((self.game / 'assets/new.bin').exists())
        self.assertEqual(fresh.list(), [])

    def test_interrupted_removal_recovers(self):
        self.store.install(self.two_files())
        original = self.store._put
        def crash(rel, data):
            original(rel, data)
            raise KeyboardInterrupt()
        with patch.object(self.store, '_put', side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):
                self.store.remove('test.music')
        self.assertTrue(MS.Store(self.game).recover())
        self.assertEqual(self.live.read_bytes(), b'new music')
        self.assertEqual((self.game / 'assets/new.bin').read_bytes(), b'new music')
        self.assertEqual(len(self.store.list()), 1)

    def test_backup_corruption_blocks_removal(self):
        self.store.install(self.package())
        key = self.store.list()[0]['files'][0]['before']
        self.store.path(MS.HOME + '/objects/' + key).write_bytes(b'corrupt')
        with self.assertRaisesRegex(MF.ModError, 'damaged'):
            self.store.remove('test.music')
        self.assertEqual(self.live.read_bytes(), b'new music')

    def test_paths_and_duplicate_zip_names(self):
        for value in ('../outside', '/absolute', 'C:/windows', 'assets/a:ads', 'assets/CON.txt',
                      'assets/trailing.', 'assets//a', 'assets/../a', 'data_dx/a '):
            with self.subTest(value=value), self.assertRaises(MF.ModError):
                MF.relative(value)
        for names in (['../bad'], ['mod.json', 'MOD.JSON'], ['a/mod.json', 'b/mod.json']):
            dest = self.root / 'bad.zip'
            with zipfile.ZipFile(dest, 'w') as z:
                for name in names:
                    z.writestr(name, '{}')
            with self.assertRaises(MF.ModError):
                MF.Package(dest)
        with self.assertRaises(MF.ModError):
            self.store.install(self.package(target='Toy Story 3 Modding Tool/installed.json'))

    def test_junction_escape(self):
        outside = self.root / 'outside'
        outside.mkdir()
        link = self.game / 'assets/linked'
        if os.name == 'nt':
            r = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        else:
            link.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(MF.ModError, 'links|junctions'):
            self.store.install(self.package(target='assets/linked/out.bin'))
        self.assertEqual(list(outside.iterdir()), [])

    def patch_package(self, corrupt=False):
        root = self.root / 'patchpack'
        (root / 'patches').mkdir(parents=True, exist_ok=True)
        rel = 'assets/characters/fake.zip'
        old = INS.entry(b'fake.oct', b'old mesh')
        untouched = INS.entry(b'unrelated', b'keep me')
        original = INS.write_zip([old, untouched])
        (self.game / rel).write_bytes(original)
        new = INS.entry(b'fake.oct', b'new mesh', old)
        added = INS.entry(b'new.bin', b'new buffer')
        expected = INS.write_zip([new, untouched, added])
        lines, blob = [], b''
        for e, prior in ((new, '%08x' % old['crc']), (added, 'new')):
            lines.append('put|%s|%d|%d|%d|%d|%d|%08x|%d|%s|%s' % (
                e['name'].decode(), len(blob), len(e['data']), e['method'], e['time'], e['date'],
                e['crc'], e['usize'], e['md5'].hex(), prior))
            blob += e['data']
        (root / 'patches/fake.bin').write_bytes(blob)
        (root / 'patches/fake.txt').write_text('\n'.join(lines), encoding='utf-8')
        after = '0' * 32 if corrupt else hashlib.md5(expected).hexdigest()
        (root / 'patches/manifest.txt').write_text('%s|fake|%s|%s\n' % (
            rel, hashlib.md5(original).hexdigest(), after), encoding='utf-8')
        return root, rel, original, expected

    def test_legacy_patches_byte_exact_roundtrip(self):
        root, rel, original, expected = self.patch_package()
        meta = self.store.install(root)
        self.assertEqual((self.game / rel).read_bytes(), expected)
        self.store.remove(meta['id'])
        self.assertEqual((self.game / rel).read_bytes(), original)

    def test_bad_patch_hash_changes_nothing(self):
        root, rel, original, _ = self.patch_package(corrupt=True)
        with self.assertRaisesRegex(MF.ModError, 'manifest'):
            self.store.install(root)
        self.assertEqual((self.game / rel).read_bytes(), original)
        self.assertEqual(self.store.list(), [])

    def test_patch_preserves_existing_unrelated_mod(self):
        root, rel, _, _ = self.patch_package()
        entries = INS.read_zip((self.game / rel).read_bytes())
        entries[1] = INS.entry(b'unrelated', b'another mod', entries[1])
        before = INS.write_zip(entries)
        (self.game / rel).write_bytes(before)
        meta = self.store.install(root)
        live = INS.read_zip((self.game / rel).read_bytes())
        self.assertEqual(INS.unpack(live[1]), b'another mod')
        self.store.remove(meta['id'])
        self.assertEqual((self.game / rel).read_bytes(), before)

    def test_schema_versions_and_constraints(self):
        with MF.Package(self.package()) as p:
            meta = p.metadata
        for changes in ({'schema_version': 2}, {'version': '1.0-beta'}, {'id': '../bad'},
                        {'requires': [{'id': 'x', 'version': '^1.0'}]}, {'game': 'another-game'}):
            with self.subTest(changes=changes), self.assertRaises(MF.ModError):
                MF.validate(dict(meta, **changes))
        self.assertTrue(MF.matches('1.10.0', '>=1.2.0'))
        self.assertFalse(MF.matches('1.2.0', '>=1.10.0'))

    def test_lock_excludes_concurrent_manager(self):
        with self.store.locked():
            with self.assertRaisesRegex(MF.ModError, 'another mod operation'):
                MS.Store(self.game).install(self.package())

    def test_project_installer_cannot_bypass_ownership(self):
        with MS.unmanaged(self.game, 'data_dx/music.bank'):
            with self.assertRaisesRegex(MF.ModError, 'another mod operation'):
                self.store.install(self.package())
        self.store.install(self.package())
        with self.assertRaisesRegex(MF.ModError, 'managed mod'):
            with MS.unmanaged(self.game, 'data_dx/music.bank'):
                pass

    def test_full_export_install_remove_and_stable_identity(self):
        import kit as K
        work = self.root / 'project'
        out = work / 'out/woody'
        out.mkdir(parents=True)
        (out / 'woody.oct').write_bytes(b'synthetic new mesh')
        rel = K.archive('woody')
        original = INS.write_zip([INS.entry(b'woody.oct', b'synthetic old mesh')])
        target = self.game / rel
        target.parent.mkdir(parents=True)
        target.write_bytes(original)
        K.save_project(str(work), {'character': 'woody', 'game': str(self.game)})
        # Trust only this synthetic original for the duration of the export test.
        with patch.dict(K.ORIGINAL, {'woody': hashlib.md5(original).hexdigest()}):
            folder, zip_path = K.export_pack(str(work), 'Test mod', '1.0', 'Test author', 'Synthetic', 'Test model')
            meta = self.store.install(zip_path)
            self.assertEqual(meta['version'], '1.0.0')
            self.assertEqual(INS.unpack(INS.read_zip(target.read_bytes())[0]), b'synthetic new mesh')
            self.store.remove(meta['id'])
            self.assertEqual(target.read_bytes(), original)
            _, zip2 = K.export_pack(str(work), 'Renamed mod', '1.1', 'Test author')
        with MF.Package(zip2) as second:
            self.assertEqual(second.metadata['id'], meta['id'])
            self.assertEqual(second.metadata['version'], '1.1.0')

    def test_recovery_preserves_external_changes(self):
        original = self.store._put
        def crash(rel, data):
            original(rel, data)
            raise KeyboardInterrupt()
        with patch.object(self.store, '_put', side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):
                self.store.install(self.two_files())
        self.live.write_bytes(b'external after crash')
        with self.assertRaisesRegex(MF.ModError, 'external edit'):
            self.store.recover()
        self.assertEqual(self.live.read_bytes(), b'external after crash')
        self.assertTrue(self.store.path(MS.JOURNAL).exists())


class Updates(unittest.TestCase):
    """modupdate with a fake GitHub: no network"""
    def setUp(self):
        import modupdate
        self.U = modupdate
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-updates-test-')
        self.cache = os.path.join(self.temp.name, 'TS3 Modding Tool', 'updates.json')
        self.asked = []
        self.mods = [{'metadata': {'id': 'a.mod', 'name': 'A', 'version': '1.0.0', 'update': {'github': 'o/a'}}},
                     {'metadata': {'id': 'b.mod', 'name': 'B', 'version': '2.0.0', 'update': {'github': 'o/b'}}},
                     {'metadata': {'id': 'c.mod', 'name': 'C', 'version': '1.0.0'}}]

    def tearDown(self):
        self.temp.cleanup()

    def fetch(self, repo):
        self.asked.append(repo)
        if repo == 'o/b':
            raise OSError('offline')
        return {'tag': 'v1.2', 'url': 'https://github.com/o/a/releases/tag/v1.2'}

    def test_versions(self):
        self.assertEqual(self.U.tag_version('v1.2'), '1.2.0')
        self.assertIsNone(self.U.tag_version('nightly'))
        self.assertTrue(self.U.newer('1.10.0', '1.9.0'))
        self.assertFalse(self.U.newer('1.0.0', '1.0.0'))

    def test_check_cache_and_retry(self):
        out = {u['id']: u for u in self.U.check(self.mods, self.cache, fetch=self.fetch, now=1000)}
        self.assertEqual(set(out), {'a.mod', 'b.mod'})               # c has no update.github
        self.assertTrue(out['a.mod']['update'])
        self.assertEqual(out['a.mod']['latest'], '1.2.0')
        self.assertEqual(out['b.mod']['error'], 'offline')
        self.assertFalse(out['b.mod']['update'])
        self.asked.clear()
        self.U.check(self.mods, self.cache, fetch=self.fetch, now=1000 + self.U.RETRY)
        self.assertEqual(self.asked, ['o/b'])                         # only the failed one, after an hour
        self.asked.clear()
        self.U.check(self.mods, self.cache, fetch=self.fetch, now=1000 + self.U.DAY)
        self.assertEqual(sorted(self.asked), ['o/a', 'o/b'])
        self.asked.clear()
        cached = self.U.check(self.mods, self.cache, fetch=None, now=10 ** 9)
        self.assertEqual(self.asked, [])                              # fetch=None never asks
        self.assertEqual(len(cached), 2)
        self.U.check(self.mods, self.cache, force=True, fetch=self.fetch, now=1000 + self.U.DAY)
        self.assertEqual(len(self.asked), 2)                          # force asks again


if __name__ == '__main__':
    unittest.main(verbosity=2)
