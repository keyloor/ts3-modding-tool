"""Bounded, read-only FSB5 bank inspection, isolated decoding and WAV previews."""
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
import time
import wave

from modfile import ModError, inside

RATES = (4000, 8000, 11000, 11025, 16000, 22050, 24000, 32000, 44100, 48000, 96000)
MAX_SECONDS = 120
MAX_PCM = 96 * 1024 * 1024


def invalid(message):
    raise ModError(message, 'invalid_audio')


def bank(data):
    """Find one FSB5 through validated RIFF chunks; never scan arbitrary payload bytes."""
    base, end = 0, len(data)
    if data[:4] != b'FSB5':
        if len(data) < 12 or data[:4] != b'RIFF' or data[8:12] != b'FEV ':
            invalid('Expected an FSB5 or RIFF FEV sound bank.')
        end = 8 + struct.unpack_from('<I', data, 4)[0]
        if end != len(data): invalid('Invalid bank length.')
        found, budget = {}, [0]
        def chunks(start, limit, depth=0):
            if depth > 16: invalid('Bank nesting is too deep.')
            while start < limit:
                budget[0] += 1
                if budget[0] > 200000 or start + 8 > limit: invalid('Invalid bank chunks.')
                cid, size = data[start:start+4], struct.unpack_from('<I', data, start+4)[0]
                stop = start + 8 + size
                if stop > limit: invalid('Bank chunk exceeds its container.')
                if cid in (b'SNDH', b'SND '):
                    if cid in found: invalid('Multiple sound data sections are unsupported.')
                    found[cid] = (start, size)
                if cid in (b'LIST', b'RIFF'):
                    if size < 4: invalid('Invalid bank list.')
                    chunks(start+12, stop, depth+1)
                start = stop + (size & 1)
            if start != limit: invalid('Missing bank chunk padding.')
        chunks(12, end)
        if b'SNDH' not in found or b'SND ' not in found:
            raise ModError('No audio samples in this bank; choose its .assets.bank companion.', 'no_audio')
        header, size = found[b'SNDH']; snd, length = found[b'SND ']
        if size < 12: invalid('Truncated sound data pointer.')
        base, fsb_length = struct.unpack_from('<II', data, header+12)
        end = base + fsb_length
        if base < snd+8 or end > snd+8+length: invalid('Sound data pointer leaves its chunk.')
    if base+60 > end or data[base:base+4] != b'FSB5': invalid('Missing FSB5 header.')
    ver, count, heads, names, length, mode = struct.unpack_from('<6I', data, base+4)
    if ver != 1: raise ModError('Only FSB5 version 1 is supported.', 'unsupported_audio')
    nt, db = base+60+heads, base+60+heads+names
    if not 1 <= count <= 20000 or heads < count*8 or names < count*4 or db+length != end:
        invalid('Invalid FSB5 section lengths or sample count.')
    off, sounds = base+60, []
    for i in range(count):
        if off+8 > nt: invalid('Truncated sample header.')
        v = struct.unpack_from('<Q', data, off)[0]; off += 8
        code = (v >> 1) & 15
        rate = RATES[code] if code < len(RATES) else 0
        channels = (1, 2, 6, 8)[(v >> 5) & 3]
        more, extensions = v & 1, 0
        while more:
            extensions += 1
            if extensions > 128: invalid('Too many sample extensions.')
            if off+4 > nt: invalid('Truncated sample extension.')
            chunk = struct.unpack_from('<I', data, off)[0]; off += 4
            more, size, kind = chunk & 1, (chunk >> 1) & 0xffffff, chunk >> 25
            if off+size > nt: invalid('Sample extension exceeds its section.')
            if kind == 1 and size == 1: channels = data[off]
            if kind == 2 and size == 4: rate = struct.unpack_from('<I', data, off)[0]
            off += size
        if not 1 <= channels <= 8 or not 4000 <= rate <= 192000: invalid('Unsupported sample rate/channels.')
        name_offset = struct.unpack_from('<I', data, nt+i*4)[0]
        if not count*4 <= name_offset < names: invalid('Sample name leaves its section.')
        zero = data.find(b'\0', nt+name_offset, min(db, nt+name_offset+4097))
        if zero < 0: invalid('Unterminated or oversized sample name.')
        samples, offset = v >> 34, ((v >> 7) & 0x7ffffff)*32
        if offset > length or (sounds and offset < sounds[-1]['offset']): invalid('Invalid sample data offset.')
        sounds.append(dict(index=i, name=data[nt+name_offset:zero].decode('latin1'), rate=rate,
                           channels=channels, samples=samples, seconds=samples/rate, offset=offset))
    if off != nt: invalid('Unexpected sample header bytes.')
    for i, sound in enumerate(sounds):
        stop = sounds[i+1]['offset'] if i+1 < count else length
        sound['data_start'], sound['data_end'] = db+sound['offset'], db+stop
        if mode == 2 and sound['samples']*sound['channels']*2 > stop-sound['offset']:
            invalid('Truncated PCM16 sample data.')
    return dict(mode=mode, sounds=sounds, fsb=data[base:end])


def describe(parsed):
    return [dict((k, v) for k, v in s.items() if k not in ('offset', 'data_start', 'data_end'))
            for s in parsed['sounds']]


def options(track, seconds):
    if type(track) is not int or track < 0 or isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 < seconds <= MAX_SECONDS:
        raise ModError('Use a sample index >= 0 and seconds > 0, at most 120.', 'invalid_arguments')


def pcm16(raw, channels, bits):
    """Clip float32, or retain PCM16; multichannel previews use a parity-average stereo downmix."""
    values = array.array('h' if bits == 16 else 'f'); values.frombytes(raw)
    if bits == 16 and channels <= 2: return raw
    pcm, out_channels = array.array('h'), min(2, channels)
    for start in range(0, len(values), channels):
        for channel in range(out_channels):
            group = values[start+channel:start+channels:out_channels]
            value = sum(group)/len(group)
            if bits == 32: value *= 32767
            pcm.append(round(max(-32768, min(32767, value))) if math.isfinite(value) else 0)
    return pcm.tobytes()


def worker_command():
    if getattr(sys, 'frozen', False):
        cli = Path(sys.executable).with_name('TS3 Modding CLI.exe')
        if not cli.is_file(): raise ModError('The companion TS3 Modding CLI.exe is missing.', 'decoder_unavailable')
        return [str(cli), '_audio-decode']
    return [sys.executable, '-I', str(Path(__file__).with_name('audio_worker.py'))]


def run_worker(game, fsb, target, track, seconds, cancel=None):
    if os.name != 'nt': raise ModError('Compressed bank playback currently requires Windows.', 'decoder_unavailable')
    dll = inside(game, 'fmod.dll')
    if not dll.is_file(): raise ModError('The game\'s fmod.dll is required to decode compressed sounds.', 'decoder_unavailable')
    # Reject a mismatched native architecture before loading any DLL.
    with dll.open('rb') as f:
        dos = f.read(64)
        if len(dos) != 64 or dos[:2] != b'MZ': raise ModError('Invalid game FMOD runtime.', 'decoder_unavailable')
        f.seek(struct.unpack_from('<I', dos, 60)[0]); pe = f.read(6)
    if pe != b'PE\0\0'+struct.pack('<H', 0x8664 if struct.calcsize('P') == 8 else 0x14c):
        raise ModError('FMOD and the tool need matching architectures.', 'decoder_unavailable')
    command = worker_command()+[str(dll), str(fsb), str(target), str(track), str(seconds)]
    with tempfile.TemporaryFile() as log:
        with subprocess.Popen(command, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW) as child:
            deadline = time.monotonic()+30
            try:
                while child.poll() is None:
                    if cancel is not None and cancel.is_set(): raise ModError('Audio preview cancelled.', 'interrupted')
                    if time.monotonic() > deadline: raise ModError('Audio decoder timed out.', 'decoder_failed')
                    time.sleep(.05)
            finally:
                if child.poll() is None: child.kill(); child.wait()
        log.seek(0); result = log.read(8192).decode('utf-8', errors='replace')
    if child.returncode or not target.is_file():
        try: message = json.loads(result)['error']
        except (ValueError, KeyError, TypeError): message = 'Native decoder failed (exit %s).' % child.returncode
        raise ModError(message, 'decoder_failed')


def decode(browser, path, member=None, track=0, seconds=30, cancel=None):
    """Returns bounded PCM16 WAV bytes; no playback and no game writes."""
    from explorer import signature
    options(track, seconds)
    source = browser.source(path); before = signature(source)
    data = browser.read(path, member); parsed = bank(data)
    if track >= len(parsed['sounds']): raise ModError('Sample index not found.', 'sample_not_found')
    sample = describe(parsed)[track]
    if sample['samples'] == 0: raise ModError('This sample is empty.', 'no_audio')
    frames = min(sample['samples'], int(sample['rate']*seconds))
    if frames < 1 or frames*sample['channels']*4 > MAX_PCM:
        raise ModError('Decoded preview exceeds the size limit; choose fewer seconds.', 'size_limit')
    if cancel is not None and cancel.is_set(): raise ModError('Audio preview cancelled.', 'interrupted')
    with tempfile.TemporaryDirectory(prefix='ts3-audio-') as temp:
        fsb, wav = Path(temp)/'input.fsb', Path(temp)/'sample.wav'
        if parsed['mode'] == 2:
            start = parsed['sounds'][track]['data_start']
            raw = pcm16(data[start:start+frames*sample['channels']*2], sample['channels'], 16)
            with wave.open(str(wav), 'wb') as w:
                w.setparams((min(2, sample['channels']), 2, sample['rate'], 0, 'NONE', 'not compressed'))
                w.writeframes(raw)
        else:
            fsb.write_bytes(parsed['fsb'])
            run_worker(browser.game, fsb, wav, track, seconds, cancel)
        if not wav.is_file() or wav.stat().st_size > MAX_PCM: invalid('Decoded audio exceeds preview limit.')
        result = wav.read_bytes()
    try:
        with wave.open(io.BytesIO(result), 'rb') as w:
            rate, channels, frames = w.getframerate(), w.getnchannels(), w.getnframes()
            expected = min(sample['samples'], int(sample['rate']*seconds))
            if (w.getsampwidth() != 2 or channels != min(2, sample['channels']) or rate != sample['rate']
                    or frames != expected or len(w.readframes(frames)) != frames*channels*2):
                invalid('Decoded WAV format or length does not match the selected sample.')
    except (wave.Error, EOFError) as e: invalid('Invalid decoded WAV: '+str(e))
    if signature(source) != before: raise ModError('Bank changed during audio decoding; retry.', 'source_changed')
    if cancel is not None and cancel.is_set(): raise ModError('Audio preview cancelled.', 'interrupted')
    return result, dict(sample, decoded_seconds=frames/rate, decoded_channels=channels,
                        truncated=frames < sample['samples'], decoder='pcm16' if parsed['mode'] == 2 else 'game-fmod')


def export(browser, path, member, output, track=0, seconds=30):
    from texpack import output_folder, publish
    output = output_folder(browser.game, output)
    with tempfile.TemporaryDirectory(prefix='.ts3-audio-', dir=output.parent) as temp:
        stage = Path(temp)/'result'; stage.mkdir()
        data, report = decode(browser, path, member, track, seconds)
        (stage/'sample.wav').write_bytes(data)
        info = dict(report, path=path, member=member)
        (stage/'audio.json').write_text(json.dumps(info, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        publish(stage, output)
    return dict(info, output=str(output), files=['sample.wav', 'audio.json'])


class Player:
    """Owns an async WinMM preview and its temporary WAV until stopped/closed."""
    def __init__(self):
        self.temp = None

    def play(self, data):
        self.stop()
        if os.name != 'nt': raise ModError('Playback currently requires Windows.', 'decoder_unavailable')
        import winsound
        self.temp = tempfile.TemporaryDirectory(prefix='ts3-listen-')
        path = Path(self.temp.name)/'preview.wav'; path.write_bytes(data)
        try: winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except BaseException:
            self.stop(); raise

    def stop(self):
        if self.temp is not None:
            import winsound
            winsound.PlaySound(None, 0)
            self.temp.cleanup(); self.temp = None
