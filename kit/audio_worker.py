"""Private, crash-isolated FMOD 2.03 decoder. Uses only the selected game's DLL."""
import ctypes as C
import json
import os
from pathlib import Path
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def decode(dll, source, target, track, seconds):
    from audiobank import bank, options, MAX_PCM, pcm16
    options(track, seconds)
    parsed = bank(Path(source).read_bytes())
    if track >= len(parsed['sounds']): raise ValueError('Sample index not found.')
    sample = parsed['sounds'][track]
    frames = min(sample['samples'], int(sample['rate']*seconds))
    if frames < 1 or frames*sample['channels']*4 > MAX_PCM: raise ValueError('Preview exceeds decoded audio limit.')
    d = C.WinDLL(str(Path(dll).resolve()), winmode=0x1100)
    P, I, U = C.c_void_p, C.c_int, C.c_uint
    def bind(name, args):
        fn = getattr(d, 'FMOD_'+name); fn.argtypes, fn.restype = args, I
        return fn
    def ok(code):
        if code: raise ValueError('FMOD decoder error %d.' % code)
    create = bind('System_Create', [C.POINTER(P), U])
    version = bind('System_GetVersion', [P, C.POINTER(U), C.POINTER(U)])
    output = bind('System_SetOutput', [P, I]); init = bind('System_Init', [P, I, U, P])
    create_sound = bind('System_CreateSound', [P, C.c_char_p, U, P, C.POINTER(P)])
    count = bind('Sound_GetNumSubSounds', [P, C.POINTER(I)])
    sub = bind('Sound_GetSubSound', [P, I, C.POINTER(P)])
    form = bind('Sound_GetFormat', [P, C.POINTER(I), C.POINTER(I), C.POINTER(I), C.POINTER(I)])
    defaults = bind('Sound_GetDefaults', [P, C.POINTER(C.c_float), C.POINTER(I)])
    read = bind('Sound_ReadData', [P, P, U, C.POINTER(U)])
    release_sound = bind('Sound_Release', [P]); release_system = bind('System_Release', [P])
    system, sound = P(), P()
    try:
        ok(create(C.byref(system), 0x20300))
        v = U(); ok(version(system, C.byref(v), None))
        if v.value >> 8 != 0x203: raise ValueError('Audio preview supports the game\'s FMOD 2.03 runtime.')
        ok(output(system, 2))  # NOSOUND: decode offline without opening the user's device.
        ok(init(system, 32, 0, None))
        ok(create_sound(system, str(Path(source)).encode('utf-8'), 0x2000 | 0x80, None, C.byref(sound)))
        n = I(); ok(count(sound, C.byref(n)))
        if n.value != len(parsed['sounds']): raise ValueError('FMOD sample count differs from the bank.')
        chosen = P(); ok(sub(sound, track, C.byref(chosen)))
        typ, fmt, channels, bits = I(), I(), I(), I()
        ok(form(chosen, C.byref(typ), C.byref(fmt), C.byref(channels), C.byref(bits)))
        rate = C.c_float(); ok(defaults(chosen, C.byref(rate), None))
        if channels.value != sample['channels'] or abs(rate.value-sample['rate']) > .1:
            raise ValueError('FMOD sample format differs from the bank.')
        if (fmt.value, bits.value) not in ((2, 16), (5, 32)):
            raise ValueError('Only PCM16 and float32 decoded samples are supported.')
        frame_bytes, out_channels = channels.value*(bits.value//8), min(2, channels.value)
        with wave.open(str(target), 'wb') as wav:
            wav.setparams((out_channels, 2, sample['rate'], 0, 'NONE', 'not compressed'))
            remaining = frames
            while remaining:
                chunk_frames = min(16384, remaining); size = chunk_frames*frame_bytes
                buffer = C.create_string_buffer(size); got = U()
                code = read(chosen, buffer, size, C.byref(got))
                # EOF is acceptable only if the complete requested frame block was returned.
                if got.value != size: raise ValueError('Decoder returned incomplete audio (%d).' % code)
                if code not in (0, 16): ok(code)
                wav.writeframesraw(pcm16(buffer.raw[:size], channels.value, bits.value))
                remaining -= chunk_frames
    finally:
        if sound.value: release_sound(sound)
        if system.value: release_system(system)


def main(argv=None):
    try:
        dll, source, target, track, seconds = sys.argv[1:] if argv is None else argv
        decode(dll, source, target, int(track), float(seconds))
        print(json.dumps(dict(ok=True)))
        return 0
    except Exception as e:
        print(json.dumps(dict(error=str(e))))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
