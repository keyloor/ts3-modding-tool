"""Shared state across products, lightweight imports and preference preservation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'kit'))
import gamepaths
import loaderprefs

LOADER = [sys.executable, '-I', str(ROOT / 'kit/loadercli.py')]
TOOL = [sys.executable, '-I', str(ROOT / 'kit/cli.py')]
if '--exe' in sys.argv:
    i = sys.argv.index('--exe'); LOADER = [str(Path(sys.argv[i + 1]).resolve())]; del sys.argv[i:i + 2]


class Loader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ts3-loader-test-')
        self.root = Path(self.tmp.name)
        self.game = self.root / 'game with spaces'
        (self.game / 'assets/characters').mkdir(parents=True)
        (self.game / 'data_dx').mkdir()
        self.file = self.game / 'data_dx/test.bank'; self.file.write_bytes(b'original')
        self.pack = self.root / 'package'; self.pack.mkdir()
        (self.pack / 'payload').write_bytes(b'modified')
        (self.pack / 'mod.json').write_text(json.dumps(dict(schema_version=1, id='test.shared', name='Shared test',
            version='1.0.0', author='Test', description='Temporary test', game='ts3-pc',
            files=[dict(source='payload', target='data_dx/test.bank')])), encoding='utf-8')
        self.settings = self.root / 'settings.json'
        self.env = dict(os.environ, TS3TOOL_SETTINGS=str(self.settings))

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, entry, *args, code=0):
        p = subprocess.run(entry + ['mods', *map(str, args), '--game', str(self.game), '--json'],
                           capture_output=True, encoding='utf-8', env=self.env, timeout=60,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        self.assertEqual(p.stderr, '')
        response = json.loads(p.stdout); self.assertEqual(response['ok'], code == 0)
        return response

    def test_loader_install_tool_remove_share_backups(self):
        ticket = self.call(LOADER, 'plan', self.pack)['data']['ticket']
        self.call(LOADER, 'install', self.pack, '--expect', ticket)
        self.assertEqual(self.file.read_bytes(), b'modified')
        self.assertEqual(self.call(TOOL, 'list')['data']['mods'][0]['metadata']['id'], 'test.shared')
        self.assertTrue(self.call(TOOL, 'verify', 'test.shared')['data']['valid'])
        ticket = self.call(TOOL, 'remove', 'test.shared', '--dry-run')['data']['ticket']
        self.call(TOOL, 'remove', 'test.shared', '--expect', ticket)
        self.assertEqual(self.file.read_bytes(), b'original')
        self.assertEqual(self.call(LOADER, 'list')['data']['mods'], [])

    def test_priority_layers_and_reordering_across_apps(self):
        self.call(TOOL, 'install', self.pack, '--layer')
        second = self.root/'second'; shutil.copytree(self.pack, second)
        meta = json.loads((second/'mod.json').read_text()); meta['id'] = 'test.upper'; meta['name'] = 'Upper'
        (second/'mod.json').write_text(json.dumps(meta)); (second/'payload').write_bytes(b'upper')
        ticket = self.call(LOADER, 'plan', second, '--layer')['data']['ticket']
        self.call(LOADER, 'install', second, '--layer', '--expect', ticket)
        self.assertEqual(self.file.read_bytes(), b'upper')
        plan = self.call(TOOL, 'order', 'test.upper', 'test.shared', '--dry-run')['data']
        self.call(LOADER, 'order', 'test.upper', 'test.shared', '--expect', plan['ticket'])
        self.assertEqual(self.file.read_bytes(), b'modified')
        self.assertTrue(self.call(TOOL, 'verify', 'test.upper')['data']['valid'])
        self.call(TOOL, 'remove', 'test.shared'); self.assertEqual(self.file.read_bytes(), b'upper')
        self.call(LOADER, 'remove', 'test.upper'); self.assertEqual(self.file.read_bytes(), b'original')

    def test_tool_install_loader_remove_and_external_change_guard(self):
        self.call(TOOL, 'install', self.pack)
        self.assertEqual(self.call(LOADER, 'list')['data']['mods'][0]['metadata']['id'], 'test.shared')
        self.file.write_bytes(b'external edit')
        self.assertEqual(self.call(LOADER, 'remove', 'test.shared', code=3)['error']['code'], 'external_change')
        self.assertEqual(self.file.read_bytes(), b'external edit')
        self.file.write_bytes(b'modified')
        self.call(LOADER, 'remove', 'test.shared')
        self.assertEqual(self.file.read_bytes(), b'original')

    def test_replace_across_apps_keeps_original_backup(self):
        self.call(TOOL, 'install', self.pack)
        meta = json.loads((self.pack / 'mod.json').read_bytes())
        meta['version'] = '2.0.0'
        (self.pack / 'mod.json').write_text(json.dumps(meta), encoding='utf-8')
        (self.pack / 'payload').write_bytes(b'rebuilt mod')
        plan = self.call(LOADER, 'plan', self.pack, '--replace')['data']
        self.assertEqual(plan['replaces']['version'], '1.0.0')
        self.call(LOADER, 'install', self.pack, '--replace', '--expect', plan['ticket'])
        self.assertEqual(self.file.read_bytes(), b'rebuilt mod')
        self.assertTrue(self.call(TOOL, 'verify', 'test.shared')['data']['valid'])
        self.call(TOOL, 'remove', 'test.shared')
        self.assertEqual(self.file.read_bytes(), b'original')

    def test_preferences_keep_authoring_fields_and_preserve_broken_file(self):
        with patch.dict(os.environ, self.env):
            data = dict(workspace='projects', recent=['first'], game='old', custom={'keep': True})
            self.settings.write_text(json.dumps(data), encoding='utf-8')
            loaderprefs.save(game=str(self.game), lang='en')
            saved = loaderprefs.read()
            for key in ('workspace', 'recent', 'custom'):
                self.assertEqual(saved[key], data[key])
            self.assertEqual(saved['game'], str(self.game))
            self.settings.write_text('{broken', encoding='utf-8')
            with self.assertRaises(ValueError):
                loaderprefs.save(lang='es')
            self.assertEqual(self.settings.read_text(), '{broken')

    def test_discovery_matches_tool_and_no_game_is_written(self):
        self.assertEqual(gamepaths.find_game(str(self.game)), str(self.game))
        with self.assertRaises(gamepaths.GameNotFound):
            gamepaths.find_game(str(self.root))
        self.assertFalse(self.settings.exists())

    def test_loader_has_no_authoring_or_image_imports(self):
        code = "import sys; sys.path.insert(0,sys.argv[1]); import loaderui,loadercli; assert not any(n in sys.modules for n in ('numpy','PIL','moderngl','kit','viewer','convert','automap')); from loaderui import TEXT; assert set(TEXT['es']) == set(TEXT['en'])"
        p = subprocess.run([sys.executable, '-I', '-c', code, str(ROOT / 'kit')], capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == '__main__':
    unittest.main()
