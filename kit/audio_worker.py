"""Private, crash-isolated FMOD 2.03 decoder. Uses only the selected game's DLL."""
import ctypes as C
import json
import os
from pathlib import Path
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


OPENONLY = 0x2000
FILE_EOF = 16


class DecodeError(ValueError):
    def __init__(self, problem, **details):
        self.problem, self.details = problem, details
        super().__init__(problem)


class Decoder:
    """Offline bank used by normal previews and the opt-in real-game regression scan."""
    def __init__(self, dll, source):
        from audiobank import bank
        self.parsed = bank(Path(source).read_bytes())
        self.system, self.sound = C.c_void_p(), C.c_void_p()
        self.library = C.WinDLL(str(Path(dll).resolve()), winmode=0x1100)
        P, I, U = C.c_void_p, C.c_int, C.c_uint
        self.create = self.bind('System_Create', [C.POINTER(P), U])
        self.version = self.bind('System_GetVersion', [P, C.POINTER(U), C.POINTER(U)])
        self.output = self.bind('System_SetOutput', [P, I]); self.init = self.bind('System_Init', [P, I, U, P])
        self.create_sound = self.bind('System_CreateSound', [P, C.c_char_p, U, P, C.POINTER(P)])
        self.count = self.bind('Sound_GetNumSubSounds', [P, C.POINTER(I)])
        self.sub = self.bind('Sound_GetSubSound', [P, I, C.POINTER(P)])
        self.form = self.bind('Sound_GetFormat', [P, C.POINTER(I), C.POINTER(I), C.POINTER(I), C.POINTER(I)])
        self.defaults = self.bind('Sound_GetDefaults', [P, C.POINTER(C.c_float), C.POINTER(I)])
        self.read = self.bind('Sound_ReadData', [P, P, U, C.POINTER(U)])
        self.seek = self.bind('Sound_SeekData', [P, U])
        self.release_sound = self.bind('Sound_Release', [P]); self.release_system = self.bind('System_Release', [P])
        try:
            self.ok(self.create(C.byref(self.system), 0x20300))
            version = U(); self.ok(self.version(self.system, C.byref(version), None))
            if version.value >> 8 != 0x203: raise DecodeError('unsupported_runtime', version=version.value)
            self.ok(self.output(self.system, 2))  # NOSOUND never opens the user's audio device.
            self.ok(self.init(self.system, 32, 0, None))
            # CREATESTREAM's FSB path fails on many short Vorbis samples with FILE_BAD/EOF.
            # OPENONLY leaves the file open for offline readData, without a stream buffer or
            # loading the bank's entire decoded PCM into memory.
            self.ok(self.create_sound(self.system, str(Path(source)).encode('utf-8'), OPENONLY, None, C.byref(self.sound)))
            count = I(); self.ok(self.count(self.sound, C.byref(count)))
            if count.value != len(self.parsed['sounds']): raise DecodeError('format_mismatch')
        except BaseException:
            self.close(); raise

    def bind(self, name, args):
        fn = getattr(self.library, 'FMOD_'+name); fn.argtypes, fn.restype = args, C.c_int
        return fn

    @staticmethod
    def ok(code):
        if code: raise DecodeError('decode_failed', fmod_result=code)

    def close(self):
        if self.sound.value:
            self.release_sound(self.sound); self.sound = C.c_void_p()
        if self.system.value:
            self.release_system(self.system); self.system = C.c_void_p()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    def decode(self, target, track, seconds):
        from audiobank import options, MAX_PCM, pcm16
        options(track, seconds)
        if track >= len(self.parsed['sounds']): raise DecodeError('sample_not_found')
        sample = self.parsed['sounds'][track]
        frames = min(sample['samples'], int(sample['rate']*seconds))
        if frames < 1 or frames*sample['channels']*4 > MAX_PCM: raise DecodeError('size_limit')
        chosen = C.c_void_p(); self.ok(self.sub(self.sound, track, C.byref(chosen)))
        typ, fmt, channels, bits = C.c_int(), C.c_int(), C.c_int(), C.c_int()
        self.ok(self.form(chosen, C.byref(typ), C.byref(fmt), C.byref(channels), C.byref(bits)))
        rate = C.c_float(); self.ok(self.defaults(chosen, C.byref(rate), None))
        if channels.value != sample['channels'] or abs(rate.value-sample['rate']) > .1: raise DecodeError('format_mismatch')
        if (fmt.value, bits.value) not in ((2, 16), (5, 32)): raise DecodeError('unsupported_format')
        self.ok(self.seek(chosen, 0))
        frame_bytes, out_channels = channels.value*(bits.value//8), min(2, channels.value)
        with wave.open(str(target), 'wb') as wav:
            wav.setparams((out_channels, 2, sample['rate'], 0, 'NONE', 'not compressed'))
            self.write_frames(chosen, wav, frames, frame_bytes, channels.value, bits.value, pcm16)

    def write_frames(self, sound, wav, frames, frame_bytes, channels, bits, convert):
        remaining = frames
        while remaining:
            size = min(16384, remaining)*frame_bytes
            buffer, got = C.create_string_buffer(size), C.c_uint()
            code = self.read(sound, buffer, size, C.byref(got))
            if got.value > size or got.value % frame_bytes:
                raise DecodeError('invalid_read', read_bytes=got.value, requested_bytes=size)
            if code not in (0, FILE_EOF): self.ok(code)
            if not got.value or (code == FILE_EOF and got.value != remaining*frame_bytes):
                raise DecodeError('incomplete_audio', fmod_result=code, remaining_frames=remaining, read_bytes=got.value)
            wav.writeframesraw(convert(buffer.raw[:got.value], channels, bits))
            remaining -= got.value//frame_bytes


def decode(dll, source, target, track, seconds):
    with Decoder(dll, source) as decoder: decoder.decode(target, track, seconds)


def main(argv=None):
    try:
        dll, source, target, track, seconds = sys.argv[1:] if argv is None else argv
        decode(dll, source, target, int(track), float(seconds))
        print(json.dumps(dict(ok=True)))
        return 0
    except DecodeError as e:
        print(json.dumps(dict(error=dict(problem=e.problem, details=e.details))))
        return 3
    except Exception:
        print(json.dumps(dict(error=dict(problem='decode_failed'))))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
