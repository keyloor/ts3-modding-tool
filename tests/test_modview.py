"""Both managers present real verification findings, including hidden-layer data failures."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'kit'))
import modview as V
from modstore import Store


class ModView(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-modview-')
        self.root = Path(self.temp.name)
        self.game = self.root/'game'
        (self.game/'assets').mkdir(parents=True); (self.game/'data_dx').mkdir()
        self.target = self.game/'data_dx/test.bank'; self.target.write_bytes(b'original')
        self.store = Store(self.game)

    def tearDown(self): self.temp.cleanup()

    def install(self, mid='test.base', layer=False):
        package = self.root/mid; package.mkdir()
        (package/'payload').write_bytes(mid.encode())
        meta = dict(schema_version=1, id=mid, name='Mod '+mid, version='1.0.0', author='Test',
                    description='', game='ts3-pc', files=[dict(source='payload', target='data_dx/test.bank')])
        (package/'mod.json').write_text(json.dumps(meta), encoding='utf-8')
        self.store.install(package, layer=layer)

    def test_v1_report_and_modified_file_are_explained_without_hashes(self):
        self.install()
        report = self.store.verify('test.base')
        before = copy.deepcopy(report)
        self.assertTrue(V.valid(report)); self.assertEqual(V.state(report, 'es'), 'Verificado')
        for lang in ('es', 'en'):
            self.assertEqual(len(V.row_values(report['files'][0], lang)), 4)
            self.assertNotIn(report['files'][0]['after'], V.file_details(report['files'][0], lang))
        self.assertEqual(report, before)
        self.target.write_bytes(b'external')
        report = self.store.verify('test.base')
        self.assertFalse(V.valid(report)); self.assertEqual(V.state(report, 'es'), 'Revisar archivos')
        self.assertIn('fuera del gestor', V.file_details(report['files'][0], 'es'))
        self.assertIn('outside the manager', V.file_details(report['files'][0], 'en'))
        self.assertEqual(V.row_values(report['files'][0], 'es')[1], 'Modificado')
        self.assertEqual(V.row_values(report['files'][0], 'en')[1], 'Modified')
        self.assertIn('1 archivo comprobado', V.summary(report, 'es'))

    def test_missing_target_and_backup_are_distinguished(self):
        self.install()
        row = self.store.verify('test.base')['files'][0]
        self.store.path('TS3 Modding Tool/objects/'+row['before']).unlink()
        self.target.unlink()
        report = self.store.verify('test.base'); row = report['files'][0]
        self.assertFalse(V.valid(report))
        self.assertEqual(row['status'], 'missing'); self.assertEqual(row['backup_status'], 'missing')
        details = V.file_details(row, 'es')
        self.assertIn('Archivo del juego: No se encuentra', details)
        self.assertIn('Copia original: No se encuentra', details)

    def test_layer_snapshot_failure_never_looks_verified(self):
        self.install(layer=True); self.install('test.upper', layer=True)
        report = self.store.verify('test.base')
        self.assertTrue(V.valid(report))
        payload = next(r for r in self.store.list() if r['metadata']['id'] == 'test.base')['files'][0]['payload']
        self.store.path('TS3 Modding Tool/objects/'+payload).write_bytes(b'damaged snapshot')
        report = self.store.verify('test.upper'); row = report['files'][0]
        self.assertEqual(row['status'], 'ok')
        self.assertFalse(V.valid(report))
        self.assertEqual(V.row_values(row, 'en')[-1], 'Damaged')
        details = V.file_details(row, 'es', {'test.base': 'Base legible'})
        self.assertIn('Base legible: Dañado', details)
        self.assertIn('test.upper: Correcto', details)

    def test_new_file_needs_no_original_backup_and_unknown_is_not_green(self):
        self.target.unlink(); self.install()
        report = self.store.verify('test.base'); row = report['files'][0]
        self.assertTrue(V.valid(report)); self.assertEqual(row['backup_status'], 'not_needed')
        self.assertIn('no necesita una copia', V.file_details(row, 'es'))
        row['status'] = 'future_status'
        self.assertFalse(V.valid(report)); self.assertEqual(V.row_values(row, 'en')[1], 'Not checked')

    def test_filtered_counter_and_search_preserve_identity(self):
        meta = dict(id='creator.music', name='Música clásica', author='Keyloor', description='Western town')
        original = dict(meta)
        self.assertTrue(V.matches(meta, 'musica keyloor'))
        self.assertTrue(V.matches(meta, 'creator.music')); self.assertFalse(V.matches(meta, 'missing'))
        self.assertEqual(meta, original)
        self.assertEqual(V.count(1, 1, 'es'), '1 mod'); self.assertEqual(V.count(2, 2, 'en'), '2 mods')
        self.assertEqual(V.count(1, 3, 'es'), '1 de 3 mods')
        self.assertEqual(V.count(0, 3, 'en'), '0 of 3 mods')
        self.assertEqual(V.state(None, 'es'), 'Instalado')

    def test_health_issue_is_not_hidden_by_an_update_notice(self):
        self.install()
        report = self.store.verify('test.base')
        self.assertEqual(V.list_state(report, True, 'es'), 'Nueva versión')
        self.target.write_bytes(b'external')
        report = self.store.verify('test.base')
        self.assertEqual(V.list_state(report, True, 'es'), 'Revisar archivos')
        self.assertEqual(V.list_state(report, True, 'en'), 'Check files')


if __name__ == '__main__': unittest.main()
