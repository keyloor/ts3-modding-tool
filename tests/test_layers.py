"""Priority composition and transactions on synthetic game files, through either application CLI."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'kit'), str(ROOT/'tests')]
import test_replacement as F
import modstore as M
import modlayers as L
from modfile import ModError, json_bytes

ENTRY = [sys.executable, '-I', str(ROOT/'kit/cli.py')]
if '--loader' in sys.argv:
    sys.argv.remove('--loader'); ENTRY[-1] = str(ROOT/'kit/loadercli.py')
if '--exe' in sys.argv:
    at = sys.argv.index('--exe'); ENTRY = [str(Path(sys.argv[at+1]).resolve())]; del sys.argv[at:at+2]


class Messages(unittest.TestCase):
    def test_the_window_translates_the_layered_registrys_refusals(self):
        import app as A

        class Window:                                      # just what App.mod_error_text uses
            t = staticmethod(lambda k: A.TEXT['es'][k])
        text = lambda msg: A.App.mod_error_text(Window, msg)
        for msg in ('File changed outside the manager; kept untouched: a.bin', 'File conflict: a.bin; review installation with --layer.',
                    'Remove dependent mod first: test.a', 'Replacement would break dependent mod: test.a',
                    'Package, game or priority order changed since preview; review again.',
                    'Interrupted operation: run mods recover first.'):
            self.assertNotEqual(text(msg), msg)
        self.assertIn('a.bin', text('File changed outside the manager; kept untouched: a.bin'))
        self.assertNotIn('--layer', text('File conflict: a.bin; review installation with --layer.'))
        self.assertEqual(text('Something else entirely.'), 'Something else entirely.')


class Layers(unittest.TestCase):
    setUp, tearDown, package = F.Replacement.setUp, F.Replacement.tearDown, F.Replacement.package

    def stack(self, new=False):
        target = 'assets/added.bin' if new else 'data_dx/main.bank'
        a = self.package({target: b'low'}, mid='test.low')
        b = self.package({target: b'high'}, mid='test.high')
        self.store.install(a)
        plan = self.store.preview(b, layer=True)
        self.store.install(b, layer=True, expected=plan['ticket'])
        return a, b, target

    def patchpack(self, mid, edits):
        self.serial += 1; folder = self.root/('patch%d' % self.serial); folder.mkdir()
        current = self.game/'assets/shared.zip'
        if not current.exists():
            self.original_zip = M.archive.write_zip([M.archive.entry(k, v) for k, v in
                ((b'a.oct', b'A original'), (b'b.oct', b'B original'), (b'untouched', b'external content'))])
            current.write_bytes(self.original_zip)
        original = {e['name'].decode(): e for e in M.archive.read_zip(self.original_zip)}
        blob, lines, replacements = b'', [], []
        for name, raw in edits.items():
            before = original.get(name); entry = M.archive.entry(name.encode(), raw, before)
            crc = '%08x' % before['crc'] if before else 'new'
            lines.append('put|%s|%d|%d|%d|%d|%d|%08x|%d|%s|%s' % (name, len(blob), len(entry['data']),
                         entry['method'], entry['time'], entry['date'], entry['crc'], entry['usize'], entry['md5'].hex(), crc))
            blob += entry['data']; replacements.append((entry, crc))
        (folder/'change.bin').write_bytes(blob); (folder/'change.txt').write_text('\n'.join(lines)+'\n')
        result = M.merge(self.original_zip, replacements)
        (folder/'manifest.txt').write_text('assets/shared.zip|change|%s|%s\n' % (
            hashlib.md5(self.original_zip).hexdigest(), hashlib.md5(result).hexdigest()))
        (folder/'mod.json').write_bytes(json_bytes(dict(schema_version=1, id=mid, name=mid, version='1.0',
                                                      author='Test', description='', game='ts3-pc', patches=[dict(manifest='manifest.txt')])))
        return folder

    def contents(self):
        return {e['name'].decode(): M.archive.unpack(e) for e in M.archive.read_zip((self.game/'assets/shared.zip').read_bytes())}

    def cli(self, *args):
        result = subprocess.run(ENTRY+['mods', *args, '--game', str(self.game), '--json'], capture_output=True,
                                text=True, encoding='utf-8', env=dict(os.environ, TS3TOOL_SETTINGS=str(self.root/'settings.json')))
        self.assertNotEqual(result.returncode, 5, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_explicit_install_migrates_only_on_commit_and_retains_original(self):
        a = self.package(mid='test.low'); b = self.package(mid='test.high')
        self.store.install(a); before = self.store.path(M.REGISTRY).read_bytes()
        objects = set(self.store.path(M.HOME+'/objects').iterdir())
        with self.assertRaises(ModError) as e: self.store.preview(b)
        self.assertEqual(e.exception.code, 'file_conflict')
        plan = self.store.preview(b, layer=True)
        self.assertEqual(self.store.path(M.REGISTRY).read_bytes(), before)
        self.assertEqual(set(self.store.path(M.HOME+'/objects').iterdir()), objects)
        self.assertEqual(plan['shared'][0]['mods'], ['test.low', 'test.high'])
        self.store.install(b, layer=True, expected=plan['ticket'])
        self.assertEqual(self.store._state()['schema_version'], 2)
        self.assertTrue(self.store.verify('test.low')['valid']); self.assertTrue(self.store.verify('test.high')['valid'])
        self.store.remove('test.high'); self.store.remove('test.low')
        self.assertEqual(self.live.read_bytes(), b'original including external mod')

    def test_remove_lower_or_upper_restores_remaining_layers(self):
        self.stack(); self.store.remove('test.low')
        self.assertEqual(self.live.read_bytes(), b'high')
        self.store.remove('test.high'); self.assertEqual(self.live.read_bytes(), b'original including external mod')
        self.stack(); self.store.remove('test.high')
        self.assertEqual(self.live.read_bytes(), b'low'); self.store.remove('test.low')
        self.assertEqual(self.live.read_bytes(), b'original including external mod')

    def test_new_file_is_deleted_only_when_last_layer_is_removed(self):
        _, _, target = self.stack(new=True)
        self.store.remove('test.low'); self.assertEqual((self.game/target).read_bytes(), b'high')
        self.store.remove('test.high'); self.assertFalse((self.game/target).exists())

    def test_order_preview_no_writes_and_reorder_survives_package_deletion(self):
        a, b, _ = self.stack(); shutil.rmtree(a); shutil.rmtree(b)
        original = self.store.path(M.REGISTRY).read_bytes()
        ids = ['test.high', 'test.low']; plan = self.store.preview_order(ids)
        self.assertEqual(self.store.path(M.REGISTRY).read_bytes(), original); self.assertEqual(self.live.read_bytes(), b'high')
        self.store.order(ids, expected=plan['ticket']); self.assertEqual(self.live.read_bytes(), b'low')
        self.assertEqual(self.store.order_info()['order'], ids)
        self.store.remove('test.low'); self.assertEqual(self.live.read_bytes(), b'high')

    def test_archive_members_compose_and_same_member_last_wins(self):
        a = self.patchpack('test.a', {'a.oct': b'A changed', 'added': b'A new'})
        b = self.patchpack('test.b', {'b.oct': b'B changed'})
        c = self.patchpack('test.c', {'a.oct': b'A winner', 'added': b'C new'})
        self.store.install(a)  # Exercise v1 patch -> member-aware migration.
        self.store.install(b, layer=True); self.store.install(c, layer=True)
        self.assertEqual(self.contents(), {'a.oct': b'A winner', 'b.oct': b'B changed', 'added': b'C new', 'untouched': b'external content'})
        self.store.order(['test.c', 'test.b', 'test.a'])
        self.assertEqual(self.contents()['a.oct'], b'A changed'); self.assertEqual(self.contents()['b.oct'], b'B changed')
        self.store.remove('test.b'); self.assertEqual(self.contents()['b.oct'], b'B original')
        self.store.remove('test.a'); self.assertEqual(self.contents()['added'], b'C new')
        self.store.remove('test.c'); self.assertEqual((self.game/'assets/shared.zip').read_bytes(), self.original_zip)

    def test_mixed_whole_archive_and_member_layers_have_explicit_order(self):
        a = self.patchpack('test.patch', {'a.oct': b'patch'})
        full = M.archive.write_zip([M.archive.entry(b'a.oct', b'whole A'), M.archive.entry(b'b.oct', b'whole B')])
        b = self.package({'assets/shared.zip': full}, mid='test.whole')
        self.store.install(b); self.store.install(a, layer=True)
        self.assertEqual(self.contents(), {'a.oct': b'patch', 'b.oct': b'whole B'})
        self.store.order(['test.patch', 'test.whole']); self.assertEqual((self.game/'assets/shared.zip').read_bytes(), full)
        self.store.remove('test.whole'); self.assertEqual(self.contents()['b.oct'], b'B original')
        self.store.remove('test.patch'); self.assertEqual((self.game/'assets/shared.zip').read_bytes(), self.original_zip)

    def test_replacement_keeps_priority_and_retired_targets_reveal_other_layers(self):
        self.stack()
        replacement = self.package({'assets/other': b'new target'}, mid='test.high', version='2')
        plan = self.store.preview(replacement, replace=True)
        self.store.install(replacement, replace=True, expected=plan['ticket'])
        self.assertEqual(self.live.read_bytes(), b'low')
        replacement = self.package({'data_dx/main.bank': b'rebuilt low'}, mid='test.low')
        self.store.install(replacement, replace=True)
        self.assertEqual(self.store.order_info()['order'], ['test.low', 'test.high'])
        self.assertEqual(self.live.read_bytes(), b'rebuilt low')

    def test_hidden_replacement_invalidates_ticket_even_if_winner_unchanged(self):
        self.stack(); ids = ['test.low', 'test.high']; plan = self.store.preview_order(ids)
        replacement = self.package({'data_dx/main.bank': b'rebuilt low'}, mid='test.low')
        self.store.install(replacement, replace=True)
        with self.assertRaises(ModError) as e: self.store.order(ids, expected=plan['ticket'])
        self.assertEqual(e.exception.code, 'plan_changed'); self.assertEqual(self.live.read_bytes(), b'high')

    def test_external_changes_block_order_remove_and_replacement(self):
        a, _, _ = self.stack(); self.live.write_bytes(b'external')
        for call in (lambda: self.store.preview_order(['test.high', 'test.low']), lambda: self.store.remove('test.low'),
                     lambda: self.store.install(a, replace=True)):
            with self.assertRaises(ModError) as e: call()
            self.assertEqual(e.exception.code, 'external_change')
        self.assertFalse(self.store.verify('test.low')['valid']); self.assertEqual(self.live.read_bytes(), b'external')

    def test_payload_corruption_and_original_backup_damage_are_reported(self):
        self.stack(); row = self.store.list()[0]['files'][0]
        self.store.path(M.HOME+'/objects/'+row['payload']).write_bytes(b'damaged')
        self.assertFalse(self.store.verify('test.high')['valid'])
        with self.assertRaises(ModError) as e: self.store.order(['test.high', 'test.low'])
        self.assertEqual(e.exception.code, 'backup_damaged'); self.assertEqual(self.live.read_bytes(), b'high')

    def test_dependencies_and_declared_conflicts_still_apply(self):
        self.stack(); child = self.package(mid='test.child', requires=[dict(id='test.low', version='>=1')])
        self.store.install(child, layer=True)
        with self.assertRaises(ModError) as e: self.store.remove('test.low')
        self.assertEqual(e.exception.code, 'dependent_installed')
        conflict = self.package(mid='test.conflict', conflicts=[dict(id='test.low', version='*')])
        with self.assertRaises(ModError) as e: self.store.install(conflict, layer=True)
        self.assertEqual(e.exception.code, 'declared_conflict')
        replacement = self.package(mid='test.low', version='0.5')
        with self.assertRaises(ModError) as e: self.store.install(replacement, replace=True)
        self.assertEqual(e.exception.code, 'dependent_version')

    def test_order_rejects_missing_duplicate_and_unknown_ids(self):
        self.stack()
        for ids in ([], ['test.low'], ['test.low', 'test.low'], ['test.low', 'unknown'], [['bad'], 'test.high']):
            with self.subTest(ids=ids), self.assertRaises(ModError) as e: self.store.preview_order(ids)
            self.assertEqual(e.exception.code, 'invalid_arguments')

    def test_order_rollback_and_keyboard_interrupt_recovery(self):
        self.stack(); original = self.store.path(M.REGISTRY).read_bytes(); put = self.store._put
        for error in (OSError('simulated disk failure'), KeyboardInterrupt()):
            triggered = False
            def crash(rel, data):
                nonlocal triggered
                put(rel, data)
                if not triggered: triggered = True; raise error
            with patch.object(self.store, '_put', side_effect=crash), self.assertRaises(type(error)):
                self.store.order(['test.high', 'test.low'])
            if isinstance(error, KeyboardInterrupt):
                with self.assertRaises(ModError): self.store.list()
                self.assertTrue(M.Store(self.game).recover())
            self.assertEqual(self.store.path(M.REGISTRY).read_bytes(), original)
            self.assertEqual(self.live.read_bytes(), b'high')

    def test_order_ticket_bound_to_destination_and_external_race(self):
        self.stack(); plan = self.store.preview_order(['test.high', 'test.low'])
        other = self.root/'other'; shutil.copytree(self.game, other)
        with self.assertRaises(ModError) as e: M.Store(other).order(['test.high', 'test.low'], expected=plan['ticket'])
        self.assertEqual(e.exception.code, 'plan_changed')
        self.live.write_bytes(b'external')
        with self.assertRaises(ModError): self.store.order(['test.high', 'test.low'], expected=plan['ticket'])
        self.assertEqual(self.live.read_bytes(), b'external')

    def test_interrupted_layer_install_restores_v1_registry_and_all_targets(self):
        a = self.package({'data_dx/main.bank': b'low', 'assets/new': b'low new'}, mid='test.low')
        b = self.package({'data_dx/main.bank': b'high', 'assets/new': b'high new'}, mid='test.high')
        self.store.install(a); registry = self.store.path(M.REGISTRY).read_bytes(); put = self.store._put
        def crash(rel, data):
            put(rel, data)
            if rel == M.REGISTRY: raise KeyboardInterrupt()
        with patch.object(self.store, '_put', crash), self.assertRaises(KeyboardInterrupt): self.store.install(b, layer=True)
        self.assertTrue(self.store.path(M.JOURNAL).exists()); M.Store(self.game).recover()
        self.assertEqual(self.store.path(M.REGISTRY).read_bytes(), registry)
        self.assertEqual(self.live.read_bytes(), b'low'); self.assertEqual((self.game/'assets/new').read_bytes(), b'low new')

    def test_layer_removal_rolls_back_all_files_after_failure(self):
        a = self.package({'data_dx/main.bank': b'low', 'assets/new': b'low new'}, mid='test.low')
        b = self.package({'data_dx/main.bank': b'high', 'assets/new': b'high new'}, mid='test.high')
        self.store.install(a, layer=True); self.store.install(b, layer=True)
        registry = self.store.path(M.REGISTRY).read_bytes(); put = self.store._put; triggered = False
        def failure(rel, data):
            nonlocal triggered
            put(rel, data)
            if not triggered: triggered = True; raise OSError('simulated failure')
        with patch.object(self.store, '_put', failure), self.assertRaises(OSError): self.store.remove('test.high')
        self.assertEqual(self.store.path(M.REGISTRY).read_bytes(), registry)
        self.assertEqual(self.live.read_bytes(), b'high'); self.assertEqual((self.game/'assets/new').read_bytes(), b'high new')

    def test_registry_shared_baseline_mismatch_is_rejected(self):
        self.stack(); path = self.store.path(M.REGISTRY); data = json.loads(path.read_bytes())
        data['mods'][0]['files'][0]['before'] = None; path.write_bytes(json_bytes(data))
        with self.assertRaises(ModError) as e: self.store.list()
        self.assertEqual(e.exception.code, 'invalid_registry')

    def test_new_target_race_does_not_lose_external_edit(self):
        source = self.package(); read = M.Package.read
        def race(package, name):
            data = read(package, name)
            if name == 'payload0': self.live.write_bytes(b'external race')
            return data
        with patch.object(M.Package, 'read', race), self.assertRaises(ModError) as e:
            self.store.install(source, layer=True)
        self.assertEqual(e.exception.code, 'external_change')
        self.assertEqual(self.live.read_bytes(), b'external race'); self.assertEqual(self.store.list(), [])

    def test_invalid_whole_archive_cannot_be_composed_with_higher_patch(self):
        patchpack = self.patchpack('test.patch', {'a.oct': b'new'})
        whole = self.package({'assets/shared.zip': b'invalid archive'}, mid='test.whole')
        self.store.install(whole)
        with self.assertRaises(ModError) as e: self.store.install(patchpack, layer=True)
        self.assertEqual(e.exception.code, 'unsupported_layer')
        self.assertEqual((self.game/'assets/shared.zip').read_bytes(), b'invalid archive')

    def test_cli_layer_review_order_and_remove(self):
        a = self.package(mid='test.low'); b = self.package({'data_dx/main.bank': b'high'}, mid='test.high')
        code, result = self.cli('install', str(a)); self.assertEqual(code, 0)
        code, result = self.cli('plan', str(b), '--layer'); self.assertEqual(code, 0)
        ticket = result['data']['ticket']
        code, result = self.cli('install', str(b), '--layer', '--expect', ticket); self.assertEqual(code, 0)
        code, result = self.cli('order'); self.assertEqual(result['data']['order'], ['test.low', 'test.high'])
        code, result = self.cli('order', 'test.high', 'test.low', '--dry-run'); self.assertEqual(code, 0)
        ticket = result['data']['ticket']; self.assertEqual(self.live.read_bytes(), b'high')
        code, result = self.cli('order', 'test.high', 'test.low', '--expect', ticket); self.assertEqual(code, 0)
        self.assertEqual(self.live.read_bytes(), b'v1')
        code, result = self.cli('verify', 'test.high'); self.assertEqual(code, 0)
        code, result = self.cli('remove', 'test.low', '--dry-run'); self.assertEqual(code, 0)
        code, result = self.cli('remove', 'test.low', '--expect', result['data']['ticket']); self.assertEqual(code, 0)
        self.assertEqual(self.live.read_bytes(), b'high')

    def test_cli_two_packs_of_the_same_member_ask_for_layers_not_external_change(self):
        """texture packs usually change the same OCT; without --layer it is a conflict to review, not outside damage"""
        a = self.patchpack('test.a', {'a.oct': b'changed A'})
        b = self.patchpack('test.b', {'a.oct': b'other A'})
        code, result = self.cli('install', str(a)); self.assertEqual(code, 0)
        before = self.contents()
        for action in ('plan', 'install'):
            code, result = self.cli(action, str(b))
            self.assertEqual((code, result['error']['code']), (3, 'file_conflict'))
        self.assertEqual(self.contents(), before)
        code, result = self.cli('install', str(b), '--layer'); self.assertEqual(code, 0)
        self.assertEqual(self.contents()['a.oct'], b'other A')

    def test_cli_archive_layers_combine_and_restore(self):
        a = self.patchpack('test.a', {'a.oct': b'changed A'})
        b = self.patchpack('test.b', {'b.oct': b'changed B'})
        code, result = self.cli('install', str(a)); self.assertEqual(code, 0)
        code, result = self.cli('plan', str(b), '--layer'); self.assertEqual(code, 0)
        code, result = self.cli('install', str(b), '--layer', '--expect', result['data']['ticket']); self.assertEqual(code, 0)
        self.assertEqual(self.contents()['a.oct'], b'changed A'); self.assertEqual(self.contents()['b.oct'], b'changed B')
        code, result = self.cli('order', 'test.b', 'test.a', '--dry-run'); self.assertEqual(code, 0)
        code, result = self.cli('order', 'test.b', 'test.a', '--expect', result['data']['ticket']); self.assertEqual(code, 0)
        code, result = self.cli('remove', 'test.a'); self.assertEqual(code, 0)
        self.assertEqual(self.contents()['a.oct'], b'A original'); self.assertEqual(self.contents()['b.oct'], b'changed B')
        code, result = self.cli('remove', 'test.b'); self.assertEqual(code, 0)
        self.assertEqual((self.game/'assets/shared.zip').read_bytes(), self.original_zip)


if __name__ == '__main__': unittest.main()
