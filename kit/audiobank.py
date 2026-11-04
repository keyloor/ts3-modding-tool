"""Bounded, read-only FSB5 bank inspection, isolated decoding and WAV previews."""
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
DECODER_MESSAGES = {
    'unsupported_runtime': "This game's audio runtime is not supported.",
    'format_mismatch': 'The decoded sample does not match its bank information.',
    'unsupported_format': 'This sample uses an unsupported audio format.',
    'sample_not_found': 'The selected sample is no longer in this bank.',
    'size_limit': 'Choose a shorter audio excerpt.',
    'incomplete_audio': 'The sample could not be decoded completely.',
    'invalid_read': 'The audio decoder returned invalid sample data.',
    'decode_failed': 'The selected sample could not be decoded.',
}


def error_text(message, lang):
    """GUI failures stay actionable/localized; native diagnostics remain in the CLI response."""
    message = str(message)
    spanish = {
        'unsupported_runtime': 'Esta versión del audio del juego todavía no es compatible.',
        'format_mismatch': 'El sonido obtenido no coincide con la información del banco. Prueba con otra muestra.',
        'unsupported_format': 'El formato de esta muestra todavía no es compatible.',
        'sample_not_found': 'La muestra elegida ya no está en este banco. Vuelve a inspeccionarlo.',
        'size_limit': 'Elige un fragmento de audio más corto.',
        'incomplete_audio': 'No se pudo decodificar esta muestra completa. Prueba con otra muestra.',
        'invalid_read': 'El decodificador devolvió datos de audio incorrectos. Prueba con otra muestra.',
        'decode_failed': 'No se pudo decodificar esta muestra. Prueba con otra muestra.',
    }
    for problem, text in DECODER_MESSAGES.items():
        if message == text: return spanish[problem] if lang == 'es' else text
    if "fmod.dll" in message or 'matching architectures' in message or 'companion TS3 Modding CLI.exe' in message:
        return ('Falta un componente para leer el audio. Comprueba la carpeta del juego y que la herramienta esté completa.' if lang == 'es' else
                'An audio component is missing. Check the game folder and that all tool files are present.')
    if 'timed out' in message:
        return 'El audio tardó demasiado en prepararse. Prueba con un fragmento más corto.' if lang == 'es' else 'Preparing audio took too long. Try a shorter excerpt.'
    if 'changed' in message:
        return 'El archivo cambió. Vuelve a inspeccionarlo antes de escuchar o guardar.' if lang == 'es' else 'The file changed. Inspect it again before playing or saving.'
    if 'size limit' in message or 'Preview exceeds' in message: return spanish['size_limit'] if lang == 'es' else DECODER_MESSAGES['size_limit']
    return ('No se pudo reproducir o guardar el audio. Comprueba el archivo elegido y la carpeta de destino.' if lang == 'es' else
            'The audio could not be played or saved. Check the selected file and output folder.')


def invalid(message):
    raise ModError(message, 'invalid_audio')


def sample_count(path):
    """Header-only index hint, not a substitute for bank()'s full validation before use.

    Seek over payloads (including multi-GB dialogue banks). Zero means a validated
    RIFF container without sample data; damaged/unsupported files raise ModError.
    """
    with open(path, 'rb') as f:
        size = os.fstat(f.fileno()).st_size
        def read(at, length):
            if at < 0 or at + length > size: invalid('Truncated sound bank header.')
            f.seek(at)
            data = f.read(length)
            if len(data) != length: invalid('Truncated sound bank header.')
            return data
        header = read(0, 12)
        base, end = 0, size
        if header[:4] != b'FSB5':
            if header[:4] != b'RIFF' or header[8:12] != b'FEV ': invalid('Expected an FSB5 or RIFF FEV sound bank.')
            if 8 + struct.unpack_from('<I', header, 4)[0] != size: invalid('Invalid bank length.')
            found, budget = {}, [0]
            def chunks(at, limit, depth=0):
                if depth > 16: invalid('Bank nesting is too deep.')
                while at < limit:
                    budget[0] += 1
                    if budget[0] > 200000 or at+8 > limit: invalid('Invalid bank chunks.')
                    h = read(at, 8); cid, length = h[:4], struct.unpack_from('<I', h, 4)[0]
                    stop = at+8+length
                    if stop > limit: invalid('Bank chunk exceeds its container.')
                    if cid in (b'SNDH', b'SND '):
                        if cid in found: invalid('Multiple sound data sections are unsupported.')
                        found[cid] = (at, length)
                    if cid in (b'LIST', b'RIFF'):
                        if length < 4: invalid('Invalid bank list.')
                        chunks(at+12, stop, depth+1)
                    at = stop+(length & 1)
                if at != limit: invalid('Missing bank chunk padding.')
            chunks(12, size)
            if not found: return 0
            if b'SNDH' not in found or b'SND ' not in found: invalid('Incomplete sound data sections.')
            at, length = found[b'SNDH']; snd, snd_length = found[b'SND ']
            if length < 12: invalid('Truncated sound data pointer.')
            base, length = struct.unpack('<II', read(at+12, 8)); end = base+length
            if base < snd+8 or end > snd+8+snd_length: invalid('Sound data pointer leaves its chunk.')
        if base+60 > end: invalid('Missing FSB5 header.')
        h = read(base, 60)
        if h[:4] != b'FSB5': invalid('Missing FSB5 header.')
        ver, count, heads, names, length = struct.unpack_from('<5I', h, 4)
        if ver != 1: raise ModError('Only FSB5 version 1 is supported.', 'unsupported_audio')
        if not 1 <= count <= 20000 or heads < count*8 or names < count*4 or base+60+heads+names+length != end:
            invalid('Invalid FSB5 section lengths or sample count.')
        return count


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
    if bits == 16 and channels <= 2: return raw
    import numpy as np
    values = np.frombuffer(raw, dtype='<i2' if bits == 16 else '<f4').astype(np.float64).reshape(-1, channels)
    if channels > 2:
        with np.errstate(invalid='ignore'):
            values = np.column_stack((values[:, 0::2].mean(axis=1), values[:, 1::2].mean(axis=1)))
    if bits == 32: values *= 32767
    values[~np.isfinite(values)] = 0
    return np.rint(np.clip(values, -32768, 32767)).astype('<i2').tobytes()


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
        try: failure = json.loads(result)['error']
        except (ValueError, KeyError, TypeError): failure = {}
        if not isinstance(failure, dict): failure = {}
        problem = failure.get('problem', 'decode_failed')
        error = ModError(DECODER_MESSAGES.get(problem, DECODER_MESSAGES['decode_failed']), 'decoder_failed')
        error.details = dict(problem=problem, exit_code=child.returncode, native=failure.get('details', {}))
        raise error


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
    rate, channels, frames = validate_wav(result, sample, seconds)
    if signature(source) != before: raise ModError('Bank changed during audio decoding; retry.', 'source_changed')
    if cancel is not None and cancel.is_set(): raise ModError('Audio preview cancelled.', 'interrupted')
    return result, dict(sample, decoded_seconds=frames/rate, decoded_channels=channels,
                        truncated=frames < sample['samples'], decoder='pcm16' if parsed['mode'] == 2 else 'game-fmod')


def validate_wav(result, sample, seconds):
    """Shared output check for previews and the exhaustive real-bank regression scan."""
    try:
        with wave.open(io.BytesIO(result), 'rb') as w:
            rate, channels, frames = w.getframerate(), w.getnchannels(), w.getnframes()
            expected = min(sample['samples'], int(sample['rate']*seconds))
            if (w.getsampwidth() != 2 or channels != min(2, sample['channels']) or rate != sample['rate']
                    or frames != expected or len(w.readframes(frames)) != frames*channels*2):
                invalid('Decoded WAV format or length does not match the selected sample.')
    except (wave.Error, EOFError) as e: invalid('Invalid decoded WAV: '+str(e))
    return rate, channels, frames


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
