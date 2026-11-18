"""Application updates need no game, preserve preferences, and never block the UI or open a browser by themselves."""
import contextlib
import io
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import time
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'kit'))
import appupdate
from appupdateui import Notice, TEXT
import modcli
import modupdate

EXECUTABLE = None
if '--exe' in sys.argv:
    index = sys.argv.index('--exe')
    EXECUTABLE = str(Path(sys.argv[index + 1]).resolve())
    del sys.argv[index:index + 2]


class Updates(unittest.TestCase):
    def setUp(self):
        version = patch.object(appupdate, 'VERSION', '0.3')
        version.start()
        self.addCleanup(version.stop)
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-appupdate-')
        self.root = Path(self.temp.name)
        self.settings = self.root / 'settings.json'
        self.settings.write_text('{"game":"keep", "recent":["project"], "custom":true}')
        self.before = self.settings.read_bytes()
        self.env = patch.dict(os.environ, TS3TOOL_SETTINGS=str(self.settings))
        self.env.start()
        self.fetch = Mock(return_value={'tag': 'v0.4', 'url': 'https://untrusted.example/download'})

    def tearDown(self):
        self.assertEqual(self.settings.read_bytes(), self.before)
        self.env.stop()
        self.temp.cleanup()

    def test_both_apps_check_a_fixed_repo_without_game_and_use_official_page(self):
        with patch.object(appupdate, 'VERSION', '0.3'):
            result = appupdate.check(fetch=self.fetch, now=10000)
        self.assertTrue(result['update'])
        self.assertEqual((result['installed'], result['latest']), ('0.3.0', '0.4.0'))
        self.assertEqual(result['url'], appupdate.RELEASES)
        self.fetch.assert_called_once_with('keyloor/ts3-modding-tool')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['settings.app-updates.json', 'settings.json'])

    def test_daily_cache_manual_force_and_new_installed_version(self):
        appupdate.check(fetch=self.fetch, now=10000)
        appupdate.check(fetch=self.fetch, now=10001)
        self.assertEqual(self.fetch.call_count, 1)
        appupdate.check(force=True, fetch=self.fetch, now=10002)
        self.assertEqual(self.fetch.call_count, 2)
        with patch.object(appupdate, 'VERSION', '0.4'):
            self.assertFalse(appupdate.check(fetch=self.fetch, now=10003)['update'])
        appupdate.check(fetch=self.fetch, now=10002 + modupdate.DAY)
        self.assertEqual(self.fetch.call_count, 3)

    def test_offline_is_an_error_not_a_current_version_and_retries_after_an_hour(self):
        self.fetch.side_effect = OSError('offline')
        result = appupdate.check(fetch=self.fetch, now=10000)
        self.assertFalse(result['update'])
        self.assertIn('offline', result['error'])
        appupdate.check(fetch=self.fetch, now=10001)
        self.assertEqual(self.fetch.call_count, 1)
        self.fetch.side_effect = None
        self.assertTrue(appupdate.check(fetch=self.fetch, now=10000 + modupdate.RETRY)['update'])

    def test_corrupt_cache_and_unusable_release(self):
        cache = self.settings.with_suffix('.app-updates.json')
        for contents in ('{broken', '[]', 'null', json.dumps({appupdate.REPOSITORY: 'broken'}),
                         json.dumps({appupdate.REPOSITORY: {'time': 'bad', 'tag': 'v99'}})):
            with self.subTest(contents=contents):
                cache.write_text(contents)
                self.assertTrue(appupdate.check(fetch=self.fetch, now=10000)['update'])
        self.fetch.return_value = {'tag': 'nightly', 'url': appupdate.RELEASES}
        result = appupdate.check(force=True, fetch=self.fetch, now=10001)
        self.assertFalse(result['update'])
        self.assertIsNotNone(result['error'])

    def test_cli_app_check_never_resolves_or_opens_game(self):
        output = io.StringIO()
        result = {'update': True, 'latest': '0.4.0', 'installed': '0.3.0', 'error': None}
        with patch.object(appupdate, 'check', return_value=result) as check, \
                patch.object(modcli, 'Store', side_effect=AssertionError('must not open game')), \
                contextlib.redirect_stdout(output):
            status = modcli.main(['updates', '--app', '--force', '--json'],
                                 game_resolver=Mock(side_effect=AssertionError('must not find game')))
        envelope = json.loads(output.getvalue())
        self.assertEqual((status, envelope['ok'], envelope['command']), (0, True, 'mods.updates'))
        self.assertEqual(envelope['data']['application'], result)
        check.assert_called_once_with(force=True)

    def test_source_or_frozen_cli_uses_cache_without_game_or_network(self):
        cache = {appupdate.REPOSITORY: {'tag': 'v99.0', 'url': 'https://untrusted.example', 'time': time.time()}}
        self.settings.with_suffix('.app-updates.json').write_text(json.dumps(cache))
        commands = [[EXECUTABLE]] if EXECUTABLE else [[sys.executable, '-I', str(ROOT / 'kit' / script)]
                                                     for script in ('cli.py', 'loadercli.py')]
        for command in commands:
            result = subprocess.run(command + ['mods', 'updates', '--app', '--json'],
                                    capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)['data']['application']
            self.assertTrue(data['update'])
            self.assertEqual((data['latest'], data['url']), ('99.0.0', appupdate.RELEASES))


class Interface(unittest.TestCase):
    def notice(self):
        notice = Notice.__new__(Notice)
        notice.root = SimpleNamespace(after=Mock())
        notice.product = 'Toy Story 3 Mod Loader'
        notice.language = lambda: 'es'
        notice.queue = queue.Queue()
        notice.checking = notice.manual = False
        notice.force_pending = False
        notice.result = None
        notice.panel, notice.label, notice.download = Mock(), Mock(), Mock()
        return notice

    def test_automatic_errors_are_quiet_and_manual_errors_are_not_current(self):
        notice = self.notice()
        notice.result = {'error': 'offline'}
        notice.render()
        notice.panel.pack_forget.assert_called_once()
        notice.label.config.assert_not_called()
        notice.manual = True
        notice.render()
        notice.label.config.assert_called_once_with(text=TEXT['es']['failed'])
        notice.download.pack_forget.assert_called_once()

    def test_worker_never_touches_tk_and_check_does_not_wait_or_open_browser(self):
        notice = self.notice()
        with patch('appupdateui.threading.Thread') as thread, \
                patch('appupdateui.webbrowser.open') as browser, \
                patch.object(appupdate, 'check', return_value={'error': 'offline'}) as check:
            notice.check(force=True)
            self.assertTrue(notice.checking)
            check.assert_not_called()
            thread.assert_called_once()
            self.assertTrue(thread.call_args.kwargs['daemon'])
            notice.render = Mock()
            thread.call_args.kwargs['target']()
            notice.render.assert_not_called()
            notice.poll()
            self.assertFalse(notice.checking)
            notice.render.assert_called_once()
            check.assert_called_once_with(force=True)
            browser.assert_not_called()

    def test_notice_keeps_its_state_across_rebuilds_and_languages(self):
        notice = self.notice()
        notice.result = {'update': True, 'latest': '0.4.0', 'installed': '0.3.0', 'error': None}
        notice.render()
        self.assertIn(notice.product, notice.label.config.call_args.kwargs['text'])
        notice.download.pack.assert_called_once()
        notice.language = lambda: 'en'
        notice.panel, notice.label, notice.download = Mock(), Mock(), Mock()
        notice.render()
        self.assertIn('is available', notice.label.config.call_args.kwargs['text'])
        self.assertEqual(set(TEXT['es']), set(TEXT['en']))

    def test_manual_check_during_startup_still_forces_a_fresh_query(self):
        notice = self.notice()
        notice.checking = True
        notice.check(force=True)
        self.assertTrue(notice.force_pending)
        notice.queue.put({'update': False, 'installed': '0.3.0', 'error': None})
        notice.check = Mock()
        notice.poll()
        self.assertFalse(notice.force_pending)
        notice.check.assert_called_once_with(force=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
