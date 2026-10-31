"""Black-box CLI checks using synthetic packages and isolated game folders.

python -I tests/test_cli.py
python -I tests/test_cli.py --exe "C:/path/TS3 Modding CLI.exe"
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENTRY = [sys.executable, '-I', str(ROOT / 'kit/cli.py')]
if '--exe' in sys.argv:
    pos = sys.argv.index('--exe')
    ENTRY = [str(Path(sys.argv[pos + 1]).resolve())]
    del sys.argv[pos:pos + 2]


class Console(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-cli-')
        self.root = Path(self.temp.name)
        self.game = self.root / 'game with spaces'
        (self.game / 'assets/characters').mkdir(parents=True)
        (self.game / 'data_dx').mkdir()
        self.live = self.game / 'data_dx/music.bank'
        self.live.write_bytes(b'original music\x00')
        self.pkg = self.root / 'Paquete de prueba'
        self.pkg.mkdir()
        (self.pkg / 'payload').write_bytes(b'modified music\x00')
        self.meta = {'schema_version': 1, 'id': 'test.music', 'name': 'Música de prueba',
                     'version': '1.0.0', 'author': 'Prueba', 'description': 'Contenido sintético',
                     'game': 'ts3-pc', 'files': [{'source': 'payload', 'target': 'data_dx/music.bank'}]}
        self.write_meta()
        self.env = dict(os.environ, TS3TOOL_SETTINGS=str(self.root / 'settings.json'),
                        TEMP=str(self.root), TMP=str(self.root))

    def tearDown(self):
        self.temp.cleanup()

    def write_meta(self):
        (self.pkg / 'mod.json').write_text(json.dumps(self.meta, ensure_ascii=False), encoding='utf-8')

    def call(self, *args, code=0):
        result = subprocess.run(ENTRY + ['mods', *map(str, args), '--json'],
                                env=self.env, capture_output=True, encoding='utf-8', timeout=60,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(len(result.stdout.strip().splitlines()), 1)
        data = json.loads(result.stdout)
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(data['ok'], code == 0)
        if code == 0:
            self.assertIsNone(data['error'])
        return data

    def plan(self):
        return self.call('plan', self.pkg, '--game', self.game)['data']

    def install(self):
        plan = self.plan()
        return self.call('install', self.pkg, '--game', self.game, '--expect', plan['ticket'])['data']

    def test_entire_review_install_verify_remove_workflow(self):
        discovered = self.call('capabilities')['data']
        self.assertTrue(discovered['non_interactive'])
        self.assertIn('verify', discovered['commands'])
        meta = self.call('inspect', self.pkg)['data']['metadata']
        self.assertEqual(meta['name'], 'Música de prueba')
        plan = self.plan()
        self.assertEqual(plan['files'][0]['operation'], 'replace')
        self.assertEqual(self.live.read_bytes(), b'original music\x00')
        self.assertFalse((self.game / 'TS3 Modding Tool/installed.json').exists())
        self.assertFalse((self.game / 'TS3 Modding Tool/objects').exists())
        dry = self.call('install', self.pkg, '--game', self.game, '--dry-run')['data']
        self.assertEqual(dry['ticket'], plan['ticket'])
        self.call('install', self.pkg, '--game', self.game, '--expect', plan['ticket'])
        self.assertEqual(self.live.read_bytes(), b'modified music\x00')
        self.assertEqual(len(self.call('list', '--game', self.game)['data']['mods']), 1)
        shown = self.call('show', 'test.music', '--game', self.game)['data']
        self.assertEqual(shown['files'][0]['path'], 'data_dx/music.bank')
        report = self.call('verify', 'test.music', '--game', self.game)['data']
        self.assertTrue(report['valid'])
        self.assertEqual(report['files'][0]['backup_status'], 'ok')
        removal = self.call('remove', 'test.music', '--game', self.game, '--dry-run')['data']
        self.assertEqual(self.live.read_bytes(), b'modified music\x00')
        self.assertNotEqual(removal['ticket'], plan['ticket'])
        self.call('remove', 'test.music', '--game', self.game, '--expect', removal['ticket'])
        self.assertEqual(self.live.read_bytes(), b'original music\x00')
        self.assertEqual(self.call('list', '--game', self.game)['data']['mods'], [])
        self.assertFalse(self.call('recover', '--game', self.game)['data']['recovered'])
        self.assertFalse((self.root / 'settings.json').exists())

    def test_modified_file_is_reported_and_never_overwritten(self):
        self.install()
        self.live.write_bytes(b'external change')
        result = self.call('verify', 'test.music', '--game', self.game, code=4)
        self.assertEqual(result['error']['code'], 'verification_failed')
        self.assertEqual(result['data']['files'][0]['status'], 'modified')
        rejected = self.call('remove', 'test.music', '--game', self.game, code=3)
        self.assertEqual(rejected['error']['code'], 'external_change')
        self.assertEqual(self.live.read_bytes(), b'external change')

    def test_missing_backup_is_reported(self):
        self.install()
        record = self.call('show', 'test.music', '--game', self.game)['data']['files'][0]
        (self.game / 'TS3 Modding Tool/objects' / record['before']).unlink()
        result = self.call('verify', 'test.music', '--game', self.game, code=4)
        self.assertEqual(result['data']['files'][0]['backup_status'], 'missing')
        self.assertEqual(self.call('remove', 'test.music', '--game', self.game, code=3)['error']['code'],
                         'backup_damaged')

    def test_stale_ticket_rejected(self):
        plan = self.plan()
        (self.pkg / 'payload').write_bytes(b'changed package')
        result = self.call('install', self.pkg, '--game', self.game, '--expect', plan['ticket'], code=3)
        self.assertEqual(result['error']['code'], 'plan_changed')
        self.assertEqual(self.live.read_bytes(), b'original music\x00')

    def test_ticket_is_bound_to_destination(self):
        plan = self.plan()
        other = self.root / 'other game'
        (other / 'data_dx').mkdir(parents=True)
        (other / 'data_dx/music.bank').write_bytes(self.live.read_bytes())
        result = self.call('install', self.pkg, '--game', other, '--expect', plan['ticket'], code=3)
        self.assertEqual(result['error']['code'], 'plan_changed')
        self.assertEqual((other / 'data_dx/music.bank').read_bytes(), b'original music\x00')

    def test_argument_and_package_errors_are_machine_readable(self):
        for args in (('unknown',), ('install',), ('install', self.pkg, '--expect', 'bad'),
                     ('install', self.pkg, '--expect', '0' * 64, '--dry-run')):
            with self.subTest(args=args):
                self.assertEqual(self.call(*args, code=2)['error']['code'], 'invalid_arguments')
        (self.pkg / 'mod.json').write_text('{bad json', encoding='utf-8')
        self.assertEqual(self.call('inspect', self.pkg, code=3)['error']['code'], 'invalid_data')

    def test_conflicts_and_missing_mod_codes(self):
        self.install()
        self.assertEqual(self.call('install', self.pkg, '--game', self.game, code=3)['error']['code'],
                         'already_installed')
        self.meta['id'] = 'test.other'
        self.write_meta()
        self.assertEqual(self.call('plan', self.pkg, '--game', self.game, code=3)['error']['code'], 'file_conflict')
        self.assertEqual(self.call('show', 'test.absent', '--game', self.game, code=3)['error']['code'], 'not_installed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
