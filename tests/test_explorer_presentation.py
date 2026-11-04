"""Explorer action availability and readable metadata, without starting Tk or touching the game."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'kit'))
import explorerpresent as P


def row(kind, path='assets/characters/woody/woody.zip', member=None, **fields):
    return dict(kind=kind, path=path, member=member, size=10500, **fields)


class Presentation(unittest.TestCase):
    def test_context_actions_do_not_offer_unsupported_exports(self):
        self.assertEqual(P.actions(None), ())
        for r in (row('sound'), row('text'), row('mesh'), row('other'), row('texture')):
            self.assertFalse(set(P.actions(r)) & {'glb', 'mesh_dump', 'tex_dump'})
        self.assertIn('audio', P.actions(row('sound')))
        self.assertIn('preview', P.actions(row('texture')))
        self.assertEqual(set(P.actions(row('oct', path='assets/loose.oct'))) & {'glb', 'mesh_dump', 'tex_dump'}, set())
        self.assertTrue({'glb', 'mesh_dump', 'tex_dump'} <= set(P.actions(row('oct', member='model.oct'))))
        self.assertIn('tex_dump', P.actions(row('archive')))
        self.assertNotIn('mesh_dump', P.actions(row('archive')))
        self.assertNotIn('glb', P.actions(row('archive', member='nested.zip')))

    def test_names_preserve_source_identity_and_search_matches_display(self):
        r = row('sound', path='data_dx/sound/wt_characters_wt_characters.assets.bank')
        original = dict(r)
        self.assertEqual(P.name(r), 'wt characters.assets.bank')
        self.assertEqual(P.name(row('sound', path='data_dx/st_junkyard_st_junkyard_str.assets.bank')), 'st junkyard str.assets.bank')
        self.assertTrue(P.matches(r, 'wt characters', 'es'))
        self.assertTrue(P.matches(r, 'assets.bank', 'es'))
        self.assertEqual(r, original)
        dialogue = row('sound', path='data_dx/sound/DIALOGes-ES/dialog_str.fsb')
        self.assertTrue(P.matches(dialogue, 'dialogos espanol', 'es'))
        self.assertFalse(P.matches(dialogue, 'Spanish', 'es'))
        self.assertTrue(P.matches(dialogue, 'dialogue Spanish', 'en'))
        self.assertEqual(P.name(row('oct', member='objects/western_gate.oct')), 'western gate.oct')

    def test_extensions_are_visible_including_compound_and_uppercase(self):
        for kind, path, expected in (
            ('archive', 'assets/woody.zip', 'woody.zip'),
            ('sound', 'data_dx/DIALOGes-ES/dialog_str.fsb', 'dialog str.fsb'),
            ('sound', 'data_dx/audio.assets.BANK', 'audio.assets.BANK'),
            ('texture', 'assets/blue_hat.DDS', 'blue hat.DDS'),
            ('text', 'assets/read_me.txt', 'read me.txt'),
            ('other', 'assets/file', 'file')):
            self.assertEqual(P.name(row(kind, path)), expected)

    def test_preview_hints_do_not_promise_unchecked_models_or_event_audio(self):
        self.assertEqual(P.preview_kind(row('oct', member='model.oct')), 'check')
        archive = row('archive')
        self.assertEqual(P.preview_kind(archive), 'check')
        self.assertEqual(P.preview_kind(archive, [{'member': 'WOODY.OCT'}]), 'check')
        self.assertEqual(P.preview_kind(archive, [{'member': 'other.oct'}]), 'none')
        self.assertEqual(P.preview_kind(row('archive', member='nested.zip')), 'none')
        self.assertEqual(P.preview_kind(row('texture')), 'image')
        self.assertEqual(P.preview_kind(row('text')), 'text')
        self.assertEqual(P.preview_kind(row('mesh')), 'none')
        self.assertEqual(P.preview_kind(row('sound')), 'check_audio')
        self.assertEqual(P.preview_kind(row('sound', audio_samples=1)), 'audio')
        events = row('sound', audio_samples=0)
        self.assertEqual(P.preview_kind(events), 'none')
        self.assertNotIn('audio', P.actions(events))
        self.assertEqual(P.actions(events)[0], 'inspect')
        checked = row('oct', member='model.oct', preview_hint='none')
        self.assertNotIn('preview', P.actions(checked))
        self.assertNotIn('export', P.actions(checked))
        checked['preview_hint'] = 'model'
        self.assertIn('preview', P.actions(checked))
        self.assertEqual(P.preview_text(checked, 'es'), 'Modelo 3D')
        self.assertEqual(P.preview_text(checked, 'en'), '3D model')

    def test_summary_is_human_and_technical_details_are_separate(self):
        r = row('sound', audio_samples=1)
        self.assertIn('1 sonido', P.summary(r, 'es'))
        self.assertNotIn('1 sonidos', P.summary(r, 'es'))
        self.assertIn('1 sound', P.summary(r, 'en'))
        info = dict(r, audio_mode=15, sounds=[], note='No audio samples in this bank')
        for lang in ('es', 'en'):
            self.assertNotIn('audio_mode', P.summary(r, lang, info))
            self.assertNotIn('No audio samples in this bank', P.summary(r, lang, info))
        self.assertIn('no hay audio', P.summary(r, 'es', info))
        info = dict(row('text'), text='hello document')
        self.assertIn('hello document', P.summary(info, 'en', info))

    def test_counter_and_units_are_localized(self):
        self.assertEqual(P.count(1, 'es'), '1 resultado')
        self.assertEqual(P.count(2, 'es'), '2 resultados')
        self.assertEqual(P.count(1, 'en'), '1 result')
        self.assertEqual(P.count(0, 'en'), '0 results')
        self.assertEqual(P.size(1500000, 'es'), '1,5 MB')
        self.assertEqual(P.size(1500000, 'en'), '1.5 MB')


if __name__ == '__main__': unittest.main()
