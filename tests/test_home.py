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
from homeui import BLUE, ICONS, TASKS, icon_image, recent_rows


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

    def test_every_card_has_its_own_smooth_icon_inside_a_rounded_tile(self):
        self.assertEqual(set(TASKS), set(ICONS))
        ink = tuple(int(BLUE[i:i+2], 16) for i in (1, 3, 5))
        drawn = {}
        for task in TASKS:
            for size in (34, 51):
                image = icon_image(task, size)
                self.assertEqual((image.mode, image.size), ('RGB', (size, size)))
                self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))        # rounded corner shows the card
                colours = {colour for _, colour in image.getcolors(size*size)}
                # Only blends of ink, tile and card: nothing darker than the ink (no ringing), strokes close to
                # solid ink, and many in-between shades (smoothed edges).
                self.assertTrue(all(c >= i for colour in colours for c, i in zip(colour, ink)))
                self.assertLess(max(c - i for c, i in zip(min(colours, key=sum), ink)), 40)
                self.assertGreater(len(colours), 12)
            drawn[task] = icon_image(task).tobytes()
        self.assertEqual(len(set(drawn.values())), len(TASKS))
        self.assertEqual(icon_image('unknown').tobytes(), drawn['mods'])


if __name__ == '__main__':
    unittest.main()
