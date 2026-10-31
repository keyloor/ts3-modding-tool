"""Build a mod's release folder: the mod's parts for each game archive (no whole game files) + the manifest.

  python build_release.py <mod dir>

The mod dir has a mod.py with TITLE (first line of the manifest), RELEASE (release folder, relative to the mod dir)
and ARCHIVES, a list of (folder in <mod>/output, game archive path). For each archive it takes the converted files in
<mod>/output/<folder>/ and the game's own archive from game/backup/<archive> and writes, in <release>/patches/,
  <archive stem>.txt   one 'put' line per file the mod puts in the archive (woody.zip -> woody.txt)
  <archive stem>.bin   those files' compressed bytes, one after the other
  manifest.txt         archive | parts | MD5 of the game's own archive | MD5 after installing into it
The MD5 after installing is computed with install.py's writer, which writes the same bytes as the PowerShell installer.
"""
import hashlib, importlib.util, os, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import install

PARTS_HEAD = """# Parts of {rel} (a game archive).
# Each 'put' line is one file the mod puts in: it replaces the archive's file of the same name (upper/lower case
# ignored), or is added at the end if the archive has none. Every other file in the archive stays as it is.
# put | file in the archive | start of its compressed bytes in {bin} | their length | compression (8 = deflate) |
#     DOS time | DOS date | CRC32 | unpacked size | MD5 of the unpacked file | CRC32 of the game's own version (new = none)
"""


def main(mod_dir):
    spec = importlib.util.spec_from_file_location('mod', os.path.join(mod_dir, 'mod.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pdir = os.path.join(mod_dir, mod.RELEASE, 'patches')
    os.makedirs(pdir, exist_ok=True)
    man = ['# ' + mod.TITLE,
           '# game archive | parts list | MD5 of the game\'s own archive | MD5 after installing into it']
    for name, rel in mod.ARCHIVES:
        orig = open(os.path.join(install.BACKUP, rel), 'rb').read()
        ents = install.read_zip(orig)
        by = {z['name'].decode('latin1').lower(): k for k, z in enumerate(ents)}
        src = os.path.join(mod_dir, 'output', name)
        base = os.path.splitext(os.path.basename(rel))[0]   # no '.zip' in the names: not taken for a zip in a zip
        lines, blob = [PARTS_HEAD.format(rel=rel, bin=base + '.bin')], b''
        for fn in sorted(os.listdir(src)):
            if fn.endswith('.log'):
                continue
            data = open(os.path.join(src, fn), 'rb').read()
            k = by.get(fn.lower())
            like = ents[k] if k is not None else None
            e = install.entry(like['name'] if like else fn.encode('latin1'), data, like)
            lines.append('put|%s|%d|%d|%d|%d|%d|%08x|%d|%s|%s' % (
                e['name'].decode('latin1'), len(blob), len(e['data']), e['method'], e['time'], e['date'], e['crc'],
                e['usize'], e['md5'].hex(), '%08x' % like['crc'] if like else 'new'))
            blob += e['data']
            if k is None:
                ents.append(e)
            else:
                ents[k] = e
        after = install.write_zip(ents)
        for z in install.read_zip(after):
            assert zlib.crc32(install.unpack(z)) == z['crc']
        open(os.path.join(pdir, base + '.txt'), 'w', newline='\r\n').write('\n'.join(lines) + '\n')
        open(os.path.join(pdir, base + '.bin'), 'wb').write(blob)
        man.append('%s|%s|%s|%s' % (rel, base, hashlib.md5(orig).hexdigest(), hashlib.md5(after).hexdigest()))
        print('%-48s %d parts, %d bytes' % (rel, len(lines) - 1, len(blob)))
    open(os.path.join(pdir, 'manifest.txt'), 'w', newline='\r\n').write('\n'.join(man) + '\n')
    keep = {'manifest.txt'} | {os.path.splitext(os.path.basename(rel))[0] + e
                               for _, rel in mod.ARCHIVES for e in ('.txt', '.bin')}
    for fn in os.listdir(pdir):                         # parts of an older build that the manifest no longer names
        if fn not in keep:
            os.remove(os.path.join(pdir, fn)); print('removed old', fn)
    print('\n'.join(man[2:]))


if __name__ == '__main__':
    main(sys.argv[1])
