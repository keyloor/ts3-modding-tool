"""FMOD Studio sound banks (data_dx/sound/*.assets.bank): list, compare and merge their sounds.

  python fmodbank.py list <bank>
  python fmodbank.py diff <bank a> <bank b>
  python fmodbank.py merge <base bank> <out bank> <donor bank>=<sound>[,<sound>...] ...

A bank is RIFF 'FEV ': a PROJ list (WAVS list with an SNDH chunk = offset and size of the sound data, HASH), then an
'SND ' chunk holding one FSB5 at a 32-byte aligned offset. FSB5 (version 1, 60-byte header): sample headers (u64 each:
bit 0 more chunks, bits 1-4 rate code, 5-6 channels, 7-33 data offset / 32, 34-63 sample count; then chunks of u32
'more | size << 1 | type << 25' + bytes), the name table (u32 offsets + NUL strings), then each sound's data, 32-aligned.
Mode 15 = Vorbis; chunk type 11 = its CRC and seek table, so a sound is its header chunks + its data, nothing else.

  python fmodbank.py loop <events bank> <sounds bank> <sound> <out events bank> [loop start, seconds]

merge takes every sound from the base bank and the named ones (by name or index) from donors, rebuilds the FSB5 and
fixes the three sizes that depend on it (RIFF, SNDH, SND). The FSB5 header's 16-byte hash is kept from the base:
the game doesn't check it (community mods change it freely).

loop fits a music event to a replaced sound's length. The events bank (<name>.bank, same RIFF layout, no audio)
plays each sound through a waveform instrument: WAIS/WAIT/WAIB = instrument GUID + waveform GUID (the sounds bank's
WAVS/'WAV ' records: GUID, u32, u16, u32 sound index, u32). The event's timeline TLNS/TMLN/TLNB = timeline GUID,
u16 1, then u16 3, u16 24, instrument GUID, u32 start, u32 length; u16 0, u16 2, u16 26, loop region GUID, u32 start,
u16 0, u32 length; u16 1. Its TRNB (transition) = GUID, region GUID, u32 from, u32 to (both the region's end). The
timeline counts 48000 per second whatever the sound's rate (the game's sounds are all 48000 Hz, so their lengths are
their sample counts). A replaced sound keeps the old length, so a longer one is cut and looped back early: this sets
the instrument and the loop region to the new sound's length, the region starting at [loop start] (default 0).
"""
import struct, sys

RATES = {1: 8000, 2: 11000, 3: 11025, 4: 16000, 5: 22050, 6: 24000, 7: 32000, 8: 44100, 9: 48000}
OFF_MASK = 0x7FFFFFF << 7


def chunks(b, off, end):
    while off + 8 <= end:
        cid, size = b[off:off + 4], struct.unpack_from('<I', b, off + 4)[0]
        yield cid, off, size
        if cid in (b'RIFF', b'LIST'):
            yield from chunks(b, off + 12, off + 8 + size)
        off += 8 + size + (size & 1)


def read(path):
    b = open(path, 'rb').read()
    assert b[:4] == b'RIFF' and b[8:12] == b'FEV ', path
    found = {cid: (off, size) for cid, off, size in chunks(b, 0, len(b)) if cid in (b'SNDH', b'SND ')}
    snd, sndh = found[b'SND '], found[b'SNDH']
    base = struct.unpack_from('<I', b, sndh[0] + 12)[0]
    assert b[base:base + 4] == b'FSB5', 'no FSB5 where SNDH points'
    ver, n, shs, nts, ds, mode = struct.unpack_from('<6I', b, base + 4)
    assert ver == 1, 'FSB5 version %d' % ver
    off, sounds = base + 60, []
    for i in range(n):
        v = struct.unpack_from('<Q', b, off)[0]
        start = off
        off += 8
        more = v & 1
        while more:
            c = struct.unpack_from('<I', b, off)[0]
            more = c & 1
            off += 4 + ((c >> 1) & 0xFFFFFF)
        sounds.append({'head': b[start:off], 'v': v, 'doff': ((v >> 7) & 0x7FFFFFF) * 32})
    nt = base + 60 + shs
    dbase = nt + nts
    for i, s in enumerate(sounds):
        end = sounds[i + 1]['doff'] if i + 1 < n else ds
        s['data'] = b[dbase + s['doff']:dbase + end]
        o = struct.unpack_from('<I', b, nt + 4 * i)[0]
        s['name'] = b[nt + o:b.index(b'\0', nt + o)].decode('latin1')
        s['rate'] = RATES.get((s['v'] >> 1) & 0xF, 0)
        s['channels'] = (1, 2, 6, 8)[(s['v'] >> 5) & 3]
        s['samples'] = s['v'] >> 34
    assert [s['doff'] for s in sounds] == sorted(s['doff'] for s in sounds), 'sound data out of order'
    return {'bytes': b, 'base': base, 'mode': mode, 'names': b[nt:dbase], 'sndh': sndh[0], 'snd': snd[0],
            'sounds': sounds}


def write(bank, sounds):
    """The base bank's bytes with its FSB5 rebuilt from 'sounds' (same count and order as the bank's)."""
    b, base = bank['bytes'], bank['base']
    heads, data = b'', b''
    for s in sounds:
        assert len(data) % 32 == 0
        v = (s['v'] & ~OFF_MASK) | ((len(data) // 32) << 7)
        heads += struct.pack('<Q', v) + s['head'][8:]
        data += s['data'] + b'\0' * (-len(s['data']) % 32)
    names = bank['names']
    hdr = bytearray(b[base:base + 60])
    struct.pack_into('<6I', hdr, 4, 1, len(sounds), len(heads), len(names), len(data), bank['mode'])
    fsb = bytes(hdr) + heads + names + data
    out = bytearray(b[:base]) + fsb
    struct.pack_into('<I', out, 4, len(out) - 8)
    struct.pack_into('<I', out, bank['sndh'] + 16, len(fsb))
    struct.pack_into('<I', out, bank['snd'] + 4, len(out) - bank['snd'] - 8)
    return bytes(out)


def find(bank, key):
    if key.isdigit():
        return int(key)
    hits = [i for i, s in enumerate(bank['sounds']) if s['name'] == key]
    assert len(hits) == 1, 'sound %r: %d matches' % (key, len(hits))
    return hits[0]


def describe(i, s):
    return '%3d %-40s %6d Hz %d ch %9d samples %7.1f s %10d bytes' % (
        i, s['name'], s['rate'], s['channels'], s['samples'], s['samples'] / (s['rate'] or 1), len(s['data']))


def same(x, y):
    return x['head'][8:] == y['head'][8:] and x['data'] == y['data'] and x['v'] & ~OFF_MASK == y['v'] & ~OFF_MASK


TIMELINE_RATE = 48000


def fit_loop(events, sounds, i, loop_start=0.0):
    """The events bank's bytes with sound i's instrument and loop region set to its length."""
    m = bytearray(events)
    leaves = [(cid, off, size) for cid, off, size in chunks(m, 0, len(m)) if cid not in (b'RIFF', b'LIST')]
    wav = {}
    for cid, off, size in chunks(sounds['bytes'], 0, sounds['base']):
        if cid == b'WAV ':
            wav[struct.unpack_from('<I', sounds['bytes'], off + 8 + 22)[0]] = sounds['bytes'][off + 8:off + 24]
    s = sounds['sounds'][i]
    length = s['samples'] * TIMELINE_RATE // s['rate']
    start = round(loop_start * TIMELINE_RATE)
    inst = [m[off + 8:off + 24] for cid, off, size in leaves if cid == b'WAIB' and m[off + 24:off + 40] == wav[i]]
    assert len(inst) == 1, 'sound %d: %d waveform instruments' % (i, len(inst))
    tl = [off + 8 for cid, off, size in leaves if cid == b'TLNB' and m[off + 30:off + 46] == inst[0]]
    assert len(tl) == 1, 'sound %d: %d timelines' % (i, len(tl))
    t = tl[0]
    assert struct.unpack_from('<3H', m, t + 16) == (1, 3, 24), 'unexpected timeline layout'
    assert struct.unpack_from('<3H', m, t + 46) == (0, 2, 26), 'timeline has no single loop region'
    old_len = struct.unpack_from('<I', m, t + 42)[0]
    region = bytes(m[t + 52:t + 68])
    r_start, r_len = struct.unpack_from('<I', m, t + 68)[0], struct.unpack_from('<I', m, t + 74)[0]
    assert r_start + r_len == old_len, 'loop region does not end at the instrument end'
    tr = [off + 8 for cid, off, size in leaves if cid == b'TRNB' and m[off + 24:off + 40] == region]
    assert all(struct.unpack_from('<2I', m, p + 32) == (old_len, old_len) for p in tr), 'unexpected transition'
    print('sound %d: length %d -> %d, loop %d-%d -> %d-%d (%d transitions)' % (
        i, old_len, length, r_start, old_len, start, length, len(tr)))
    struct.pack_into('<I', m, t + 42, length)
    struct.pack_into('<I', m, t + 68, start)
    struct.pack_into('<I', m, t + 74, length - start)
    for p in tr:
        struct.pack_into('<2I', m, p + 32, length, length)
    return bytes(m)


def main(args):
    cmd = args[0]
    if cmd == 'list':
        bank = read(args[1])
        for i, s in enumerate(bank['sounds']):
            print(describe(i, s))
    elif cmd == 'diff':
        a, b = read(args[1]), read(args[2])
        assert [s['name'] for s in a['sounds']] == [s['name'] for s in b['sounds']], 'different sound lists'
        for i, (x, y) in enumerate(zip(a['sounds'], b['sounds'])):
            if not same(x, y):
                print('a ' + describe(i, x))
                print('b ' + describe(i, y))
    elif cmd == 'merge':
        bank = read(args[1])
        sounds = list(bank['sounds'])
        for spec in args[3:]:
            path, keys = spec.rsplit('=', 1)
            donor = read(path)
            assert [s['name'] for s in donor['sounds']] == [s['name'] for s in sounds], path + ': different sound list'
            for key in keys.split(','):
                i = find(donor, key)
                sounds[i] = donor['sounds'][i]
                print('from %s: %s' % (path, describe(i, sounds[i])))
        open(args[2], 'wb').write(write(bank, sounds))
        check = read(args[2])
        assert all(same(x, y) for x, y in zip(check['sounds'], sounds)), 'merged bank reads back wrong'
        print('wrote', args[2], len(check['bytes']), 'bytes')
    elif cmd == 'loop':
        sounds = read(args[2])
        out = fit_loop(open(args[1], 'rb').read(), sounds, find(sounds, args[3]), float(args[5]) if len(args) > 5 else 0)
        open(args[4], 'wb').write(out)
        print('wrote', args[4])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:]) if len(sys.argv) > 2 else sys.exit(__doc__)
