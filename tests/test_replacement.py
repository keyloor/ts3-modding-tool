"""Transactional replacement: originals, archive patches, dependencies, races and crash recovery."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'kit'))
import modfile as MF
import modstore as MS
import install as INS


class Replacement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ts3-replace-')
        self.root = Path(self.tmp.name)
        self.game = self.root / 'game'
        (self.game / 'assets/characters').mkdir(parents=True)
        (self.game / 'data_dx').mkdir()
        self.live = self.game / 'data_dx/main.bank'
        self.live.write_bytes(b'original including external mod')
        self.store = MS.Store(self.game)
        self.closed = patch.object(INS, 'game_running', return_value=False)
        self.closed.start()
        self.serial = 0

    def tearDown(self):
        self.closed.stop()
        self.tmp.cleanup()

    def package(self, files=None, mid='test.mod', version='1.0', **extra):
        self.serial += 1
        folder = self.root / ('package%d' % self.serial); folder.mkdir()
        rows = []
        for i, (target, data) in enumerate((files or {'data_dx/main.bank': b'v1'}).items()):
            source = 'payload%d' % i
            (folder / source).write_bytes(data)
            rows.append(dict(source=source, target=target))
        meta = dict(schema_version=1, id=mid, name='Test mod', version=version, author='Test',
                    description='Synthetic package', game='ts3-pc', files=rows, **extra)
        (folder / 'mod.json').write_bytes(MF.json_bytes(meta))
        return folder

    def install_old(self):
        (self.game / 'assets/restore.bin').write_bytes(b'original restore')
        self.store.install(self.package({'data_dx/main.bank': b'v1', 'assets/added.bin': b'added',
                                         'assets/restore.bin': b'changed'}))
        return self.store.list()

    def changed_package(self):
        return self.package({'data_dx/main.bank': b'v2', 'assets/new.bin': b'new'}, version='2.0')

    def assert_old(self, state):
        self.assertEqual(self.store.list(), state)
        self.assertEqual(self.live.read_bytes(), b'v1')
        self.assertEqual((self.game / 'assets/added.bin').read_bytes(), b'added')
        self.assertEqual((self.game / 'assets/restore.bin').read_bytes(), b'changed')
        self.assertFalse((self.game / 'assets/new.bin').exists())
        self.assertFalse(self.store.path(MS.JOURNAL).exists())

    def test_replacement_restores_retired_targets_and_keeps_first_backups(self):
        old = self.install_old(); source = self.changed_package()
        objects = set(self.store.path(MS.HOME + '/objects').iterdir())
        preview = self.store.preview(source, replace=True)
        self.assert_old(old)
        self.assertEqual(set(self.store.path(MS.HOME + '/objects').iterdir()), objects)
        self.assertEqual(preview['replaces']['version'], '1.0.0')
        self.assertEqual(set(preview['restores']), {'assets/added.bin', 'assets/restore.bin'})
        self.assertEqual(len(preview['files']), 4)
        self.store.install(source, replace=True, expected=preview['ticket'])
        self.assertEqual(self.live.read_bytes(), b'v2')
        self.assertEqual((self.game / 'assets/restore.bin').read_bytes(), b'original restore')
        self.assertFalse((self.game / 'assets/added.bin').exists())
        self.assertTrue(self.store.verify('test.mod')['valid'])
        current = self.store.list()[0]
        self.assertEqual(current['files'][0]['before'], old[0]['files'][0]['before'])
        self.store.install(self.package({'data_dx/main.bank': b'rebuilt v2'}, version='2.0'), replace=True)
        self.store.remove('test.mod')
        self.assertEqual(self.live.read_bytes(), b'original including external mod')
        self.assertFalse((self.game / 'assets/new.bin').exists())

    def test_replacement_is_explicit_and_never_takes_another_mods_target(self):
        old = self.install_old(); source = self.changed_package()
        for action in (self.store.preview, self.store.install):
            with self.assertRaises(MF.ModError) as caught:
                action(source)
            self.assertEqual(caught.exception.code, 'already_installed')
        self.store.install(self.package({'assets/owned.bin': b'other'}, mid='test.other'))
        source = self.package({'assets/owned.bin': b'attempt'})
        with self.assertRaises(MF.ModError) as caught:
            self.store.install(source, replace=True)
        self.assertEqual(caught.exception.code, 'file_conflict')
        self.assertEqual(self.live.read_bytes(), b'v1')
        self.assertEqual((self.game / 'assets/owned.bin').read_bytes(), b'other')

    def test_compatible_dependents_stay_installed_and_incompatible_versions_are_blocked(self):
        self.store.install(self.package(version='2'))
        self.store.install(self.package({'assets/dependent.bin': b'dependent'}, mid='test.dependent',
                                        requires=[dict(id='test.mod', version='>=2.0')]))
        source = self.package(version='3')
        self.store.install(source, replace=True)
        self.assertEqual(len(self.store.list()), 2)
        for extra, code in ((dict(version='1'), 'dependent_version'),
                            (dict(version='3', requires=[dict(id='missing.mod')]), 'missing_dependency'),
                            (dict(version='3', conflicts=[dict(id='test.dependent')]), 'declared_conflict')):
            with self.subTest(code=code), self.assertRaises(MF.ModError) as caught:
                self.store.install(self.package(**extra), replace=True)
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(self.store.list()[0]['metadata']['version'], '3.0.0')

    def test_external_edits_and_corrupt_originals_block_replacement_even_for_retired_files(self):
        old = self.install_old(); source = self.changed_package()
        retired = self.game / 'assets/added.bin'
        retired.write_bytes(b'external')
        with self.assertRaises(MF.ModError) as caught:
            self.store.install(source, replace=True)
        self.assertEqual(caught.exception.code, 'external_change')
        self.assertEqual(retired.read_bytes(), b'external')
        retired.write_bytes(b'added')
        key = old[0]['files'][2]['before']
        backup = self.store.path(MS.HOME + '/objects/' + key); backup.write_bytes(b'broken')
        with self.assertRaises(MF.ModError) as caught:
            self.store.preview(source, replace=True)
        self.assertEqual(caught.exception.code, 'backup_damaged')
        self.assertEqual(self.live.read_bytes(), b'v1')

    def test_replacement_cannot_introduce_a_dependency_cycle(self):
        self.store.install(self.package())
        self.store.install(self.package({'assets/dependent.bin': b'dependent'}, mid='test.dependent',
                                        requires=[dict(id='test.mod')]))
        source = self.package(requires=[dict(id='test.dependent')])
        with self.assertRaises(MF.ModError) as caught:
            self.store.install(source, replace=True)
        self.assertEqual(caught.exception.code, 'dependency_cycle')
        self.assertEqual(self.store.list()[0]['metadata']['requires'], [])
        self.store.remove('test.dependent'); self.store.remove('test.mod')

    def test_stale_tickets_cover_package_old_metadata_and_new_targets(self):
        self.install_old(); source = self.changed_package()
        for change in ('package', 'old_metadata', 'new_target'):
            preview = self.store.preview(source, replace=True)
            if change == 'package':
                (source / 'payload0').write_bytes(b'rebuilt')
            elif change == 'old_metadata':
                registry = json.loads(self.store.path(MS.REGISTRY).read_bytes())
                registry['mods'][0]['metadata']['description'] = 'edited record'
                self.store.path(MS.REGISTRY).write_bytes(MF.json_bytes(registry))
            else:
                (self.game / 'assets/new.bin').write_bytes(b'new external')
            with self.subTest(change=change), self.assertRaises(MF.ModError) as caught:
                self.store.install(source, replace=True, expected=preview['ticket'])
            self.assertEqual(caught.exception.code, 'plan_changed')
            self.assertEqual(self.live.read_bytes(), b'v1')

    def test_disk_failure_rolls_back_to_installed_version(self):
        old = self.install_old(); original = self.store._put; calls = []
        def fail(rel, data):
            calls.append(rel)
            if len(calls) == 3:
                raise OSError('simulated disk failure')
            original(rel, data)
        with patch.object(self.store, '_put', side_effect=fail), self.assertRaises(OSError):
            self.store.install(self.changed_package(), replace=True)
        self.assert_old(old)

    def test_crash_recovery_restores_installed_version_including_registry(self):
        old = self.install_old(); original = self.store._put
        def crash(rel, data):
            original(rel, data)
            if rel == MS.REGISTRY:
                raise KeyboardInterrupt('simulated power loss')
        with patch.object(self.store, '_put', side_effect=crash), self.assertRaises(KeyboardInterrupt):
            self.store.install(self.changed_package(), replace=True)
        self.assertTrue(MS.Store(self.game).recover())
        self.assert_old(old)

    def test_edit_between_preparation_and_commit_is_preserved(self):
        self.install_old(); original = self.store._commit
        def race(changes, state, expected):
            self.live.write_bytes(b'external during commit')
            return original(changes, state, expected)
        with patch.object(self.store, '_commit', side_effect=race), self.assertRaises(MF.ModError) as caught:
            self.store.install(self.changed_package(), replace=True)
        self.assertEqual(caught.exception.code, 'external_change')
        self.assertEqual(self.live.read_bytes(), b'external during commit')
        self.assertEqual(self.store.list()[0]['metadata']['version'], '1.0.0')

    def test_case_variant_uses_original_target_and_new_package_duplicates_are_rejected(self):
        self.store.install(self.package())
        self.store.install(self.package({'DATA_DX/MAIN.BANK': b'v2'}), replace=True)
        self.assertEqual(self.live.read_bytes(), b'v2')
        self.assertEqual(self.store.list()[0]['files'][0]['path'], 'data_dx/main.bank')
        with self.assertRaises(MF.ModError):
            self.store.install(self.package({'data_dx/main.bank': b'v3', 'DATA_DX/MAIN.BANK': b'v4'}), replace=True)
        self.assertEqual(self.live.read_bytes(), b'v2')

    def test_game_running_blocks_replacement(self):
        self.install_old()
        with patch.object(INS, 'game_running', return_value=True), self.assertRaises(MF.ModError) as caught:
            self.store.install(self.changed_package(), replace=True)
        self.assertEqual(caught.exception.code, 'game_running')

    def archive_package(self, original, replacement):
        source = self.package(files={'assets/unused': b''})
        meta = json.loads((source / 'mod.json').read_bytes())
        meta.update(files=[], patches=[dict(manifest='patches/manifest.txt')])
        (source / 'mod.json').write_bytes(MF.json_bytes(meta))
        (source / 'patches').mkdir()
        old = INS.read_zip(original)[0]
        new = INS.entry(b'fake.oct', replacement)
        added = INS.entry(b'added.bin', replacement)
        entries, blob, lines = [(new, '%08x' % old['crc']), (added, 'new')], b'', []
        for entry, before in entries:
            lines.append('put|%s|%d|%d|%d|%d|%d|%08x|%d|%s|%s' % (
                entry['name'].decode(), len(blob), len(entry['data']), entry['method'], entry['time'], entry['date'],
                entry['crc'], entry['usize'], entry['md5'].hex(), before))
            blob += entry['data']
        after = MS.merge(original, entries)
        (source / 'patches/fake.bin').write_bytes(blob)
        (source / 'patches/fake.txt').write_text('\n'.join(lines), encoding='utf-8')
        (source / 'patches/manifest.txt').write_text('assets/fake.zip|fake|%s|%s\n' % (
            hashlib.md5(original).hexdigest(), hashlib.md5(after).hexdigest()), encoding='utf-8')
        return source, after

    def test_archive_update_uses_original_baseline_and_preserves_unrelated_members(self):
        original = INS.write_zip([INS.entry(b'fake.oct', b'original mesh'), INS.entry(b'external.bin', b'other mod')])
        target = self.game / 'assets/fake.zip'; target.write_bytes(original)
        source, first = self.archive_package(original, b'v1 mesh'); self.store.install(source)
        source, second = self.archive_package(original, b'v2 mesh')
        plan = self.store.preview(source, replace=True)
        self.assertEqual(target.read_bytes(), first)
        self.store.install(source, replace=True, expected=plan['ticket'])
        self.assertEqual(target.read_bytes(), second)
        self.assertTrue(self.store.verify('test.mod')['valid'])
        self.store.remove('test.mod')
        self.assertEqual(target.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
