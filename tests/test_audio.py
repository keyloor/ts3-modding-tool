"""Synthetic bank/decoder/export/CLI checks. No game runtime or audio device required."""
import array
import ctypes as C
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
import audio_worker as W
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

    def test_sample_count_reads_headers_only(self):
        for data in (fsb(), riff()):
            self.path.write_bytes(data)
            actual_open, reads = open, []
            class HeaderReader:
                def __enter__(inner): inner.file = actual_open(self.path, 'rb'); return inner
                def __exit__(inner, *args): inner.file.close()
                def fileno(inner): return inner.file.fileno()
                def seek(inner, at): return inner.file.seek(at)
                def read(inner, length):
                    reads.append(length)
                    self.assertLessEqual(length, 60, 'index attempted a payload read')
                    return inner.file.read(length)
            with patch('builtins.open', return_value=HeaderReader()):
                self.assertEqual(A.sample_count(self.path), 2)
            self.assertLess(sum(reads), 200)

    def test_sample_count_distinguishes_events_from_damaged_audio(self):
        self.path.write_bytes(b'RIFF'+struct.pack('<I', 4)+b'FEV ')
        self.assertEqual(A.sample_count(self.path), 0)
        for data in (b'bad', riff()[:-1], riff(fsb()[:60]),
                     b'RIFF'+struct.pack('<I', 16)+b'FEV '+chunk(b'SNDH', bytes(4))):
            self.path.write_bytes(data)
            with self.assertRaises(ModError): A.sample_count(self.path)

    def test_playable_filter_and_cached_hint_upgrade(self):
        events = self.game/'data_dx/test.bank'
        events.write_bytes(b'RIFF'+struct.pack('<I', 4)+b'FEV ')
        unknown = self.game/'data_dx/unknown.fsb'; unknown.write_bytes(b'bad')
        with zipfile.ZipFile(self.game/'assets/audio.zip', 'w') as z: z.writestr('inside.fsb', fsb())
        index = self.browser.index()
        self.assertEqual(len(Browser.search(index, category='sound')), 4)
        self.assertEqual([r['path'] for r in Browser.search(index, playable=True)], ['data_dx/test.assets.bank'])
        self.assertIsNone(index['files']['data_dx/unknown.fsb']['audio_samples'])
        self.assertIn('audio_note', index['files']['data_dx/unknown.fsb'])
        # Existing schema 2 ZIP caches need no rebuild just to add sound hints.
        for info in index['files'].values(): info.pop('audio_samples', None)
        self.browser.cache_file.write_text(json.dumps(index))
        with patch('explorer.directory', side_effect=AssertionError('unnecessary ZIP rebuild')):
            index = self.browser.index()
        self.assertEqual(index['reused'], 4)
        self.assertEqual(len(Browser.search(index, playable=True)), 1)
        events.write_bytes(fsb())
        index = self.browser.index()
        self.assertEqual(len(Browser.search(index, playable=True)), 2)

    def test_cli_playable_lists_only_verified_loose_banks(self):
        (self.game/'data_dx/events.bank').write_bytes(b'RIFF'+struct.pack('<I', 4)+b'FEV ')
        code, out = self.call('list', '--playable')
        self.assertEqual(code, 0)
        self.assertEqual(out['data']['total'], 1)
        self.assertEqual(out['data']['items'][0]['audio_samples'], 2)
        code, out = self.call('list', '--playable', '--kind', 'texture')
        self.assertEqual(code, 2)
        self.assertEqual(out['error']['code'], 'invalid_arguments')

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

    def test_dialogue_fsb_is_indexed_as_sound_even_after_old_cache(self):
        (self.game/'data_dx/dialog_str.fsb').write_bytes(fsb())
        self.browser.cache.mkdir()
        self.browser.cache_file.write_text(json.dumps(dict(schema_version=1, game=str(self.browser.game), files={})))
        index = self.browser.index()
        self.assertEqual(index['files']['data_dx/dialog_str.fsb']['kind'], 'sound')
        status, result = self.call('inspect', 'data_dx/dialog_str.fsb')
        self.assertEqual(status, 0); self.assertEqual(len(result['data']['sounds']), 2)

    def test_vectorized_pcm_conversion_matches_reference_rounding_and_downmix(self):
        import random
        rng = random.Random(2841)
        for bits in (16, 32):
            for channels in (1, 2, 3, 6, 8):
                source = [rng.uniform(-2, 2) if bits == 32 else rng.randrange(-32768, 32768) for _ in range(128*channels)]
                if bits == 32: source[0:4] = [float('nan'), float('inf'), float('-inf'), .5]
                values = array.array('f' if bits == 32 else 'h', source); expected = array.array('h')
                for start in range(0, len(values), channels):
                    for channel in range(min(channels, 2)):
                        group = values[start+channel:start+channels:min(channels, 2)]
                        value = sum(group)/len(group)*(32767 if bits == 32 else 1)
                        expected.append(round(max(-32768, min(32767, value))) if math.isfinite(value) else 0)
                with self.subTest(bits=bits, channels=channels):
                    self.assertEqual(A.pcm16(values.tobytes(), channels, bits), expected.tobytes())

    def test_audio_errors_are_localized_without_native_codes(self):
        for message in list(A.DECODER_MESSAGES.values())+['Decoder returned incomplete audio (13).', 'Native decoder failed (exit -12345).']:
            spanish = A.error_text(message, 'es'); english = A.error_text(message, 'en')
            self.assertNotEqual(spanish, english)
            for text in (spanish, english):
                self.assertNotIn('(13)', text); self.assertNotIn('-12345', text); self.assertNotIn('FMOD', text)
        self.assertIn('carpeta del juego', A.error_text("The game's fmod.dll is required", 'es'))

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


class Function:
    def __init__(self, callback): self.callback = callback
    def __call__(self, *args): return self.callback(*args)


class FakeFMOD:
    """Small SDK double: streaming mode fails, offline reads obey partial-read/EOF contracts."""
    def __init__(self, parsed):
        self.parsed, self.positions, self.modes, self.released = parsed, {}, [], []
        for name in ('System_Create', 'System_GetVersion', 'System_SetOutput', 'System_Init', 'System_CreateSound',
                     'Sound_GetNumSubSounds', 'Sound_GetSubSound', 'Sound_GetFormat', 'Sound_GetDefaults',
                     'Sound_ReadData', 'Sound_SeekData', 'Sound_Release', 'System_Release'):
            setattr(self, 'FMOD_'+name, Function(getattr(self, name)))
    def System_Create(self, ptr, version): ptr._obj.value = 1; return 0
    def System_GetVersion(self, system, version, build): version._obj.value = 0x20311; return 0
    def System_SetOutput(self, system, output): assert output == 2; return 0
    def System_Init(self, *args): return 0
    def System_CreateSound(self, system, path, mode, info, ptr):
        self.modes.append(mode)
        if mode & 0x80: return 13
        assert mode & 0x2000
        ptr._obj.value = 2; return 0
    def Sound_GetNumSubSounds(self, sound, ptr): ptr._obj.value = len(self.parsed['sounds']); return 0
    def Sound_GetSubSound(self, sound, track, ptr): ptr._obj.value = 100+track; self.positions.setdefault(track, 0); return 0
    def Sound_GetFormat(self, chosen, typ, fmt, channels, bits):
        typ._obj.value = 20; fmt._obj.value = 5; bits._obj.value = 32
        channels._obj.value = self.parsed['sounds'][chosen.value-100]['channels']; return 0
    def Sound_GetDefaults(self, chosen, rate, priority): rate._obj.value = 8000; return 0
    def Sound_SeekData(self, chosen, frame): self.positions[chosen.value-100] = frame; return 0
    def Sound_ReadData(self, chosen, buffer, size, got):
        track = chosen.value-100; sample = self.parsed['sounds'][track]; channels = sample['channels']
        frames = min(size//(channels*4), sample['samples']-self.positions[track], 127)
        raw = array.array('f', [.25 if track == 0 else -.25]*frames*channels).tobytes()
        C.memmove(buffer, raw, len(raw)); got._obj.value = len(raw); self.positions[track] += frames
        return 0
    def Sound_Release(self, sound): self.released.append('sound'); return 0
    def System_Release(self, system): self.released.append('system'); return 0


class NativeWorker(unittest.TestCase):
    def test_offline_mode_decodes_short_samples_and_repeated_selections_from_zero(self):
        with tempfile.TemporaryDirectory(prefix='ts3-native-test-') as temp:
            root = Path(temp); source = root/'synthetic.fsb'; source.write_bytes(fsb(15))
            fake = FakeFMOD(A.bank(source.read_bytes()))
            with patch.object(W.C, 'WinDLL', return_value=fake, create=True):
                with W.Decoder(root/'fmod.dll', source) as decoder:
                    output = root/'result.wav'
                    decoder.decode(output, 0, 30); first = output.read_bytes()
                    A.validate_wav(first, fake.parsed['sounds'][0], 30)
                    decoder.decode(output, 1, .05); self.assertNotEqual(output.read_bytes(), first)
                    decoder.decode(output, 0, 30); self.assertEqual(output.read_bytes(), first)
            self.assertEqual(fake.modes, [0x2000]); self.assertEqual(fake.released, ['sound', 'system'])

    def test_partial_reads_continue_but_truncation_errors_and_invalid_byte_counts_fail(self):
        def run(outcomes):
            decoder = object.__new__(W.Decoder); stream = io.BytesIO()
            def read(sound, buffer, size, got):
                code, count = outcomes.pop(0); got._obj.value = count
                if 0 <= count <= size: C.memmove(buffer, bytes(count), count)
                return code
            decoder.read = read
            with wave.open(stream, 'wb') as wav:
                wav.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
                decoder.write_frames(None, wav, 4, 4, 1, 32, A.pcm16)
            return stream.getvalue()
        result = run([(0, 4), (0, 4), (16, 8)])
        with wave.open(io.BytesIO(result)) as wav: self.assertEqual(wav.getnframes(), 4)
        for outcomes, problem in [([(16, 8)], 'incomplete_audio'), ([(0, 0)], 'incomplete_audio'),
                                  ([(13, 16)], 'decode_failed'), ([(0, 3)], 'invalid_read'), ([(0, 20)], 'invalid_read')]:
            with self.subTest(outcomes=outcomes), self.assertRaises(W.DecodeError) as e: run(outcomes)
            self.assertEqual(e.exception.problem, problem)


if __name__ == '__main__': unittest.main()
