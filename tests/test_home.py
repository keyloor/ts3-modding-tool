"""Recent-project resilience and navigation guards, without a window or game writes."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'kit'))
from app import App
from homeui import recent_rows


class Home(unittest.TestCase):
    def test_bad_recent_files_do_not_hide_good_projects_or_modify_any_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            samples = {'broken': b'{invalid', 'wrong-shape': b'[]',
                       'wrong-fields': b'{"fbx": []}', 'invalid-text': b'\xff',
                       'good': json.dumps({'character': 'woody', 'fbx': 'models/woody.glb',
                                           'adjust': {'head_pct': 115}}).encode('utf-8')}
            paths = []
            for name, content in samples.items():
                project = root/name; project.mkdir(); paths.append(str(project))
                (project/'kit_project.json').write_bytes(content)
            paths.insert(0, str(root/'missing'))
            for lang in ('es', 'en'):
                rows = recent_rows(paths, {'woody': 'Woody'}, lang)
                self.assertEqual([row['path'] for row in rows], paths)
                self.assertEqual([row['readable'] for row in rows], [False]*5+[True])
                self.assertEqual((rows[-1]['character'], rows[-1]['model']), ('Woody', 'woody.glb'))
            self.assertFalse((root/'missing').exists())
            self.assertEqual({name: (root/name/'kit_project.json').read_bytes() for name in samples}, samples)

    def test_busy_navigation_cannot_destroy_the_active_screen(self):
        app = SimpleNamespace(busy=True, screen='project', clear_body=Mock(),
                              build_characters=Mock(), build_explorer=Mock())
        App.show_characters(app)
        App.show_explorer(app, 'models')
        self.assertEqual(app.screen, 'project')
        app.clear_body.assert_not_called()
        app.build_characters.assert_not_called()
        app.build_explorer.assert_not_called()

    def test_explorer_rebuild_retains_task_context_without_modifying_settings(self):
        settings = {'game': 'isolated-game', 'recent': ['owned-project']}
        app = SimpleNamespace(busy=False, screen='home', settings=settings,
                              clear_body=Mock(), build_explorer=Mock(), lang='es')
        for mode in ('textures', 'models', 'sounds', 'all'):
            App.show_explorer(app, mode)
            app.lang = 'en'
            with patch('explorerui.ExplorerPane') as pane:
                App.build_explorer(app)
                pane.assert_called_once_with(app, mode=mode)
        self.assertEqual(settings, {'game': 'isolated-game', 'recent': ['owned-project']})


if __name__ == '__main__':
    unittest.main()
