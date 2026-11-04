"""Verification wiring and guards in both products, without a Tk window or game writes."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'kit'))
from app import App
from loaderui import LoaderApp
import modview


REPORT = dict(metadata=dict(id='test.mod', name='Test'), valid=True,
              files=[dict(path='data_dx/test.bank', status='ok', backup_status='ok')])


class Controls(unittest.TestCase):
    def test_tool_verify_reads_selected_store_then_retains_the_result(self):
        panel = SimpleNamespace(busy=False, mods_ready=True, mods_pending=False, root=Mock(),
            mods_tree=Mock(), settings={'game': 'isolated-game'}, mods_health={}, lang='es',
            filter_mods=Mock(), mods_note=Mock(), show_mod_verification=Mock(), mods_failed=Mock())
        panel.root.grab_current.return_value = None
        panel.mods_tree.selection.return_value = ('test.mod',)
        def run(job, done, **kwargs): done(job())
        panel.run = run
        with patch('app.K.modstore.Store') as store:
            store.return_value.verify.return_value = REPORT
            App.verify_mod(panel)
        store.assert_called_once_with('isolated-game')
        store.return_value.verify.assert_called_once_with('test.mod')
        self.assertIs(panel.mods_health['test.mod'], REPORT)
        panel.filter_mods.assert_called_once_with('test.mod')
        panel.show_mod_verification.assert_called_once()

    def test_tool_refuses_verify_during_work_or_recovery(self):
        for busy, ready, pending in ((True, True, False), (False, False, False), (False, True, True)):
            panel = SimpleNamespace(busy=busy, mods_ready=ready, mods_pending=pending, mods_tree=Mock(), run=Mock())
            panel.mods_tree.selection.return_value = ('test.mod',)
            App.verify_mod(panel)
            panel.run.assert_not_called()

    def test_loader_verify_retains_report_and_redraws_health(self):
        panel = SimpleNamespace(busy=False, pending=False, current_id=lambda: 'test.mod', game='isolated-game',
            health={}, lang='en', filter=Mock(), show_notice=Mock(), show_verification=Mock())
        panel.run = lambda job, done: done(job())
        with patch('loaderui.Store') as store:
            store.return_value.verify.return_value = REPORT
            LoaderApp.verify(panel)
        store.return_value.verify.assert_called_once_with('test.mod')
        self.assertIs(panel.health['test.mod'], REPORT)
        panel.filter.assert_called_once_with('test.mod'); panel.show_verification.assert_called_once()

    def test_reopening_result_is_read_only_and_modal_guarded(self):
        for tool in (True, False):
            panel = SimpleNamespace(root=Mock(), busy=False, lang='es')
            panel.root.grab_current.return_value = None
            if tool:
                panel.mods_tree = Mock(); panel.mods_tree.selection.return_value = ('test.mod',)
                panel.mods_health = {'test.mod': REPORT}; panel.mods_rows = {}; panel.mods_pending = False
                show = App.show_mod_verification
            else:
                panel.current_id = lambda: 'test.mod'; panel.health = {'test.mod': REPORT}
                panel.records = {}; panel.pending = False; show = LoaderApp.show_verification
            with patch.object(modview, 'VerificationDialog') as dialog:
                show(panel); dialog.assert_called_once()
                panel.root.grab_current.return_value = 'another-dialog'
                show(panel); self.assertEqual(dialog.call_count, 1)


if __name__ == '__main__': unittest.main()
