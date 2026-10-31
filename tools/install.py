"""Put converted files into a game archive, keeping a backup of the game's own archive.

  python install.py install <game dir> <archive rel path> <dir with files>   (every file in the dir goes in)
  python install.py restore <game dir> <archive rel path>

Archives are rewritten in the game's own layout: end record + directory at the front, the files, directory + end
record at the back, and every directory entry carries the game's 'KF' extra field ("MD5" + MD5 of the file).
Files already in the archive are replaced (case-insensitive name), others are added; the rest keep their bytes.
"""
import hashlib, os, shutil, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(os.path.dirname(HERE), 'game', 'backup')   # the game's own archives, shared by every mod


def read_zip(b):
    e = len(b) - 22
    while e >= 0 and struct.unpack_from('<I', b, e)[0] != 0x06054B50:
        e -= 1
    n, = struct.unpack_from('<H', b, e + 10)
    p, = struct.unpack_from('<I', b, e + 16)
    if struct.unpack_from('<I', b, p)[0] != 0x02014B50 and struct.unpack_from('<I', b, 0)[0] == 0x06054B50:
        p = 22
    out = []
    for _ in range(n):
        (sig, _vm, _vn, _fl, method, tm, dt, crc, cs, us, nl, xl, cl, _d, _ia, _ea, lho) = struct.unpack_from('<IHHHHHHIIIHHHHHII', b, p)
        assert sig == 0x02014B50, 'damaged directory'
        name = b[p + 46:p + 46 + nl]
        md5 = None
        q, xe = p + 46 + nl, p + 46 + nl + xl
        while q + 4 <= xe:
            tag, sz = struct.unpack_from('<HH', b, q)
            if tag == 0x464B and sz == 19 and b[q + 4:q + 7] == b'MD5':
                md5 = b[q + 7:q + 23]
            q += 4 + sz
        lnl, lxl = struct.unpack_from('<HH', b, lho + 26)
        data = b[lho + 30 + lnl + lxl: lho + 30 + lnl + lxl + cs]
        out.append(dict(name=name, method=method, time=tm, date=dt, crc=crc, usize=us, data=data, md5=md5))
        p += 46 + nl + xl + cl
    return out


def unpack(z):
    return zlib.decompress(z['data'], -15) if z['method'] == 8 else z['data']


def write_zip(ents):
    for z in ents:
        if z['md5'] is None:
            z['md5'] = hashlib.md5(unpack(z)).digest()
    cd_size = sum(46 + len(z['name']) + 23 for z in ents)
    pos = 22 + cd_size
    body, cd = [], []
    for z in ents:
        body.append(struct.pack('<IHHHHHIIIHH', 0x04034B50, 20, 0, z['method'], z['time'], z['date'], z['crc'],
                                len(z['data']), z['usize'], len(z['name']), 0) + z['name'] + z['data'])
        cd.append(struct.pack('<IHHHHHHIIIHHHHHII', 0x02014B50, 20, 20, 0, z['method'], z['time'], z['date'], z['crc'],
                              len(z['data']), z['usize'], len(z['name']), 23, 0, 0, 0, 0, pos) + z['name'] +
                  struct.pack('<HH', 0x464B, 19) + b'MD5' + z['md5'])
        pos += 30 + len(z['name']) + len(z['data'])
    cdb = b''.join(cd)
    end = struct.pack('<IHHHHIIH', 0x06054B50, 0, 0, len(ents), len(ents), len(cdb), pos, 0)
    return end + cdb + b''.join(body) + cdb + end


def entry(name, data, like=None):
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    packed = c.compress(data) + c.flush()
    return dict(name=name, method=8, time=like['time'] if like else 0, date=like['date'] if like else 0x5B21,
                crc=zlib.crc32(data), usize=len(data), data=packed, md5=hashlib.md5(data).digest())


def game_running():
    try:
        import subprocess
        out = subprocess.run(['tasklist'], capture_output=True, text=True).stdout
        return 'Toy Story 3 Complete Edition' in out
    except Exception:
        return False


def install(game, rel, src):
    live = os.path.join(game, rel)
    bak = os.path.join(BACKUP, rel)
    if not os.path.exists(bak):
        os.makedirs(os.path.dirname(bak), exist_ok=True)
        shutil.copy2(live, bak)
        print('backup:', bak)
    ents = read_zip(open(bak, 'rb').read())           # always start from the game's own archive
    by = {z['name'].decode('latin1').lower(): k for k, z in enumerate(ents)}
    for root, _, files in os.walk(src):
        for fn in files:
            if fn.endswith('.log'):
                continue
            path = os.path.join(root, fn)
            name = os.path.relpath(path, src).replace('\\', '/')
            data = open(path, 'rb').read()
            k = by.get(name.lower())
            if k is None:
                ents.append(entry(name.encode('latin1'), data)); print('  added   ', name)
            else:
                ents[k] = entry(ents[k]['name'], data, ents[k]); print('  replaced', name)
    out = write_zip(ents)
    # check: every file reads back with its CRC
    for z in read_zip(out):
        assert zlib.crc32(unpack(z)) == z['crc'], z['name']
    tmp = live + '.ts5_new'
    open(tmp, 'wb').write(out)
    os.replace(tmp, live)
    print('installed into', live, '(%d bytes)' % len(out))


def restore(game, rel):
    bak = os.path.join(BACKUP, rel)
    shutil.copy2(bak, os.path.join(game, rel))
    print('restored', rel)


if __name__ == '__main__':
    if game_running():
        raise SystemExit('Close Toy Story 3 first.')
    if sys.argv[1] == 'install':
        install(*sys.argv[2:5])
    else:
        restore(*sys.argv[2:4])
