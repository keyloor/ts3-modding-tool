"""Synthetic bank/decoder/export/CLI checks. No game runtime or audio device required."""
import array
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'kit'))
import audiobank as A
from explorer import Browser
from modfile import ModError

ENTRY = [sys.executable, '-I', str(ROOT/'kit/cli.py')]
if '--exe' in sys.argv:
    at = sys.argv.index('--exe'); ENTRY = [str(Path(sys.argv[at+1]).resolve())]; del sys.argv[at:at+2]


def fsb(mode=2):
    heads, names, samples = b'', struct.pack('<II', 8, 14)+b'first\0second\0', b''
    for channels, frames in ((1, 800), (2, 1600)):
        offset = len(samples)
        heads += struct.pack('<Q', (1 << 1) | ((channels-1) << 5) | ((offset//32) << 7) | (frames << 34))
        samples += struct.pack('<'+'h'*(frames*channels), *[round(10000*math.sin(i/10)) for i in range(frames*channels)])
        samples += b'\0'*(-len(samples) % 32)
    return b'FSB5'+struct.pack('<6I', 1, 2, len(heads), len(names), len(samples), mode)+bytes(32)+heads+names+samples


def chunk(kind, data):
    return kind+struct.pack('<I', len(data))+data+b'\0'*(len(data) & 1)


def riff(data=None):
    data = fsb() if data is None else data
    header = chunk(b'SNDH', struct.pack('<III', 0, 64, len(data)))
    project = chunk(b'LIST', b'PROJ'+chunk(b'LIST', b'WAVS'+header))
    body = b'FEV '+project+chunk(b'SND ', bytes(64-(12+len(project)+8))+data)
    return b'RIFF'+struct.pack('<I', len(body))+body


class Audio(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-audio-test-'); self.root = Path(self.temp.name)
        self.game = self.root/'game'; (self.game/'assets').mkdir(parents=True); (self.game/'data_dx').mkdir()
        self.path = self.game/'data_dx/test.assets.bank'; self.path.write_bytes(riff())
        self.browser = Browser(self.game, self.root/'cache')
        self.before = self.path.read_bytes()

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args):
        env = dict(os.environ, TS3TOOL_SETTINGS=str(self.root/'isolated.json'))
        p = subprocess.run(ENTRY+['explore', *args, '--game', str(self.game), '--json'], capture_output=True, text=True,
                           encoding='utf-8', env=env)
        result = json.loads(p.stdout); self.assertNotEqual(p.returncode, 5, p.stderr)
        return p.returncode, result

    def test_riff_and_direct_fsb_metadata(self):
        for data in (fsb(), riff()):
            bank = A.bank(data); rows = A.describe(bank)
            self.assertEqual([s['name'] for s in rows], ['first', 'second'])
            self.assertEqual([s['channels'] for s in rows], [1, 2])
            self.assertEqual([s['seconds'] for s in rows], [.1, .2])
            self.assertEqual(bank['fsb'], fsb())

    def test_decodes_selected_pcm_and_limits_preview(self):
        data, info = A.decode(self.browser, 'data_dx/test.assets.bank', track=1, seconds=.05)
        self.assertEqual((info['name'], info['decoded_seconds'], info['truncated']), ('second', .05, True))
        with wave.open(io.BytesIO(data)) as wav:
            self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()), (2, 2, 8000, 400))
            self.assertTrue(any(wav.readframes(400)))
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_full_sample_is_not_padded_to_limit(self):
        data, info = A.decode(self.browser, 'data_dx/test.assets.bank', seconds=30)
        self.assertFalse(info['truncated']); self.assertEqual(info['decoded_seconds'], .1)

    def test_float_clipping_nonfinite_and_multichannel_downmix(self):
        raw = array.array('f', [2, -2, float('nan'), float('inf'), .5, -.5]).tobytes()
        values = array.array('h'); values.frombytes(A.pcm16(raw, 2, 32))
        self.assertEqual(list(values), [32767, -32768, 0, 0, 16384, -16384])
        raw = array.array('h', [100, -100, 200, -200, 300, -300]).tobytes()
        values = array.array('h'); values.frombytes(A.pcm16(raw, 6, 16))
        self.assertEqual(list(values), [200, -200])

    def test_invalid_track_and_time_refuse_before_decoder(self):
        for track, seconds, code in [(-1, 30, 'invalid_arguments'), (True, 30, 'invalid_arguments'),
                                     (99, 30, 'sample_not_found'), (0, 0, 'invalid_arguments'),
                                     (0, float('nan'), 'invalid_arguments'), (0, 121, 'invalid_arguments')]:
            with self.subTest(track=track, seconds=seconds), self.assertRaises(ModError) as e:
                A.decode(self.browser, 'data_dx/test.assets.bank', track=track, seconds=seconds)
            self.assertEqual(e.exception.code, code)

    def test_event_bank_is_distinct_from_corruption(self):
        data = b'RIFF'+struct.pack('<I', 4)+b'FEV '
        with self.assertRaises(ModError) as e: A.bank(data)
        self.assertEqual(e.exception.code, 'no_audio')
        self.path.write_bytes(data)
        report = self.browser.inspect('data_dx/test.assets.bank')
        self.assertEqual(report['sounds'], []); self.assertIn('.assets.bank', report['note'])

    def test_malformed_banks_are_bounded_and_refused(self):
        edits = []
        for offset, value in ((4, 2), (8, 20001), (12, 15), (16, 1), (20, 0xffffffff)):
            data = bytearray(fsb()); struct.pack_into('<I', data, offset, value); edits.append(data)
        data = bytearray(fsb()); struct.pack_into('<I', data, 76, 0xffffffff); edits.append(data)
        data = bytearray(fsb()); data[84:] = b'x'*(len(data)-84); edits.append(data)
        edits += [b'', riff()[:-1], b'RIFF'+struct.pack('<I', 12)+b'FEV JUNK'+struct.pack('<I', 0xffffffff)]
        for data in edits:
            with self.subTest(size=len(data)), self.assertRaises(ModError): A.bank(data)

    def test_extension_chain_has_a_work_limit(self):
        heads = struct.pack('<Q', 1 | (1 << 1))+struct.pack('<I', 1)*129
        names = struct.pack('<I', 4)+b'name\0'
        data = b'FSB5'+struct.pack('<6I', 1, 1, len(heads), len(names), 0, 15)+bytes(32)+heads+names
        with self.assertRaises(ModError) as e: A.bank(data)
        self.assertEqual(e.exception.code, 'invalid_audio')
        self.assertIn('Too many', str(e.exception))
        self.path.write_bytes(data)
        status, result = self.call('inspect', 'data_dx/test.assets.bank')
        self.assertEqual((status, result['error']['code']), (3, 'invalid_audio'))
        self.assertIn('Too many', result['error']['message'])

    def test_export_is_staged_and_never_overwrites_or_writes_game(self):
        out = self.root/'export'; info = A.export(self.browser, 'data_dx/test.assets.bank', None, out, 1, .1)
        self.assertEqual(sorted(p.name for p in out.iterdir()), ['audio.json', 'sample.wav'])
        self.assertEqual(json.loads((out/'audio.json').read_text())['index'], 1)
        for output, code in ((out, 'destination_exists'), (self.game/'audio', 'invalid_path')):
            with self.assertRaises(ModError) as e: A.export(self.browser, 'data_dx/test.assets.bank', None, output)
            self.assertEqual(e.exception.code, code)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_zip_member_and_unicode_output(self):
        path = self.game/'assets/audio.zip'
        with zipfile.ZipFile(path, 'w') as z: z.writestr('sounds/test.bank', riff())
        out = self.root/'escucha ñ'
        result = A.export(self.browser, 'assets/audio.zip', 'sounds/test.bank', out)
        self.assertTrue((out/'sample.wav').is_file()); self.assertEqual(result['name'], 'first')

    def test_source_change_and_worker_failure_leave_no_output(self):
        self.path.write_bytes(riff(fsb(15)))
        def changed(game, source, target, track, seconds, cancel):
            with wave.open(str(target), 'wb') as wav:
                wav.setparams((1, 2, 8000, 0, 'NONE', 'not compressed')); wav.writeframes(bytes(1600))
            self.path.write_bytes(riff())
        out = self.root/'changed'
        with patch.object(A, 'run_worker', changed), self.assertRaises(ModError) as e:
            A.export(self.browser, 'data_dx/test.assets.bank', None, out)
        self.assertEqual(e.exception.code, 'source_changed'); self.assertFalse(out.exists())
        self.path.write_bytes(riff(fsb(15)))
        with patch.object(A, 'run_worker', side_effect=ModError('Failed', 'decoder_failed')), self.assertRaises(ModError):
            A.export(self.browser, 'data_dx/test.assets.bank', None, out)
        self.assertFalse(out.exists()); self.assertEqual(list(self.root.glob('.ts3-audio-*')), [])

    def test_decoder_output_is_validated(self):
        self.path.write_bytes(riff(fsb(15)))
        def corrupt(game, source, target, track, seconds, cancel): target.write_bytes(b'not a wav')
        with patch.object(A, 'run_worker', corrupt), self.assertRaises(ModError) as e:
            A.decode(self.browser, 'data_dx/test.assets.bank')
        self.assertEqual(e.exception.code, 'invalid_audio')

    def test_cancelled_decode_does_not_invoke_native_code(self):
        cancel = threading.Event(); cancel.set()
        with patch.object(A, 'run_worker') as worker, self.assertRaises(ModError) as e:
            A.decode(self.browser, 'data_dx/test.assets.bank', cancel=cancel)
        self.assertEqual(e.exception.code, 'interrupted'); worker.assert_not_called()

    def test_cli_inspect_export_and_refusals(self):
        status, result = self.call('inspect', 'data_dx/test.assets.bank')
        self.assertEqual(status, 0); self.assertEqual(len(result['data']['sounds']), 2)
        out = self.root/'cli'
        status, result = self.call('audio', 'data_dx/test.assets.bank', '--out', str(out), '--track', '1', '--seconds', '.05')
        self.assertEqual(status, 0); self.assertEqual(result['command'], 'explore.audio')
        self.assertEqual(result['data']['decoded_seconds'], .05); self.assertTrue((out/'sample.wav').is_file())
        status, result = self.call('audio', 'data_dx/test.assets.bank', '--out', str(out))
        self.assertEqual((status, result['error']['code']), (3, 'destination_exists'))
        status, result = self.call('audio', 'data_dx/test.assets.bank', '--out', str(self.root/'bad'), '--seconds', 'nan')
        self.assertEqual((status, result['error']['code']), (2, 'invalid_arguments'))
        self.path.write_bytes(riff(fsb(15)))
        status, result = self.call('audio', 'data_dx/test.assets.bank', '--out', str(self.root/'compressed'))
        self.assertEqual((status, result['error']['code']), (3, 'decoder_unavailable'))

    @unittest.skipUnless(os.name == 'nt', 'native worker isolation')
    def test_native_worker_timeout_and_cancel_kill_only_owned_child(self):
        header = bytearray(64); header[:2] = b'MZ'; struct.pack_into('<I', header, 60, 64)
        (self.game/'fmod.dll').write_bytes(header+b'PE\0\0'+struct.pack('<H', 0x8664 if struct.calcsize('P') == 8 else 0x14c))
        class Child:
            returncode = None
            killed = waited = False
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def poll(self): return self.returncode
            def kill(self): self.killed = True; self.returncode = -9
            def wait(self): self.waited = True
        for cancelled in (False, True):
            child, cancel = Child(), threading.Event()
            if cancelled: cancel.set()
            with patch.object(A.subprocess, 'Popen', return_value=child), patch.object(A.time, 'monotonic', side_effect=[0, 31]), self.assertRaises(ModError) as e:
                A.run_worker(self.game, self.path, self.root/'output.wav', 0, 30, cancel)
            self.assertEqual(e.exception.code, 'interrupted' if cancelled else 'decoder_failed')
            self.assertTrue(child.killed and child.waited)

    @unittest.skipUnless(os.name == 'nt', 'WinMM backend')
    def test_player_stops_before_removing_its_temporary_wave(self):
        data, _ = A.decode(self.browser, 'data_dx/test.assets.bank')
        player = A.Player()
        with patch('winsound.PlaySound') as play:
            player.play(data); directory = Path(player.temp.name)
            self.assertTrue((directory/'preview.wav').is_file())
            player.stop(); self.assertEqual(play.call_args.args, (None, 0))
            self.assertFalse(directory.exists()); self.assertIsNone(player.temp)
            player.stop(); self.assertEqual(play.call_count, 2)


if __name__ == '__main__': unittest.main()
