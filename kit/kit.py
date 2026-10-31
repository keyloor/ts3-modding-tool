"""Toy Story 3 Modding Tool, characters: from a rigged FBX (or an OBJ) to Toy Story 3, in one command.

  python kit.py characters [--game <dir>]
      the characters that can be replaced, and where the game is
  python kit.py make <project dir> --character woody --fbx <model.fbx> [--textures <dir>] [--game <dir>]
                     [--remap] [--install] [--force]
      extract the character from the game, write the map (bones + textures), convert, check, draw the previews;
      --install also puts it into the game. The settings are kept in <project dir>/kit_project.json, so the next
      'make' needs only the project dir. An existing <project dir>/map.py is used as it is (your edits stay):
      --remap writes it again from scratch.
  python kit.py install <project dir>
  python kit.py restore <project dir>
      put the converted character into the game / put the game's own archive back (the game must be closed)
  python kit.py export <project dir> --name "<pack name>" [--version 1.0] [--author <you>] [--what <one line>]
                       [--model-credits <who made the model>]
      a pack for Nexus in <project dir>/pack/: an installer that puts only this mod's files into each player's own
      game archive (the same installer as keyloor's mods), README, and a zip of it all

What it writes in the project dir: game/<character>/ (the game's files), map.py, out/<character>/ (the converted
files), previews/body.png and face.png, report.txt (everything it printed). The first install keeps the game's
archive in '<game>/TS3 Modding Tool backup/'.
"""
import argparse, contextlib, hashlib, json, os, shutil, sys, uuid
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True                         # loading map.py would leave a __pycache__ in the project
import paths  # noqa: F401  (puts the shared tools on sys.path)
import modfile
import modstore
from about import CREDIT
import automap as AM
import objlib
import install as INS
import convert as CV
CV.Scene = objlib.open_scene                           # the converter reads OBJ models too (given a skeleton)
import ts3model as T
import render as RD
from octlib import Oct
from PIL import Image

GAME_DIR = 'Toy Story 3 Complete Edition'
BACKUP_DIR = 'TS3 Modding Tool backup'
OLD_BACKUP_DIR = 'TS3 Character Kit backup'          # version 0.1 test builds
# MD5 of the game's own archives (Steam, Complete Edition): a different one means another mod is installed
ORIGINAL = {'woody': 'd6a261b2d4e9f42b9e09311bd6cfda5d', 'buzzlightyear': '13048dabd945adccba1f7977657ed6d0',
            'jessie': '1a8c43bcc16f43530d3e0a309b48c45e'}
IMAGES = ('.png', '.tga', '.jpg', '.jpeg', '.bmp', '.dds')


class KitError(Exception):
    pass


# ------------------------------------------------------------------------------------------- the game
def steam_libraries():
    roots = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as k:
            roots.append(winreg.QueryValueEx(k, 'SteamPath')[0])
    except Exception:
        pass
    roots += [r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam']
    libs = []
    for r in roots:
        libs.append(r)
        vdf = os.path.join(r, 'steamapps', 'libraryfolders.vdf')
        if os.path.isfile(vdf):
            for line in open(vdf, encoding='utf-8', errors='replace'):
                parts = line.strip().split('"')
                if len(parts) >= 4 and parts[1] == 'path':
                    libs.append(parts[3].replace('\\\\', '\\'))
    return libs


def find_game(given=None):
    cands = [given] if given else [os.path.join(lib, 'steamapps', 'common', GAME_DIR) for lib in steam_libraries()]
    for c in cands:
        if c and os.path.isdir(os.path.join(c, 'assets', 'characters')):
            return os.path.normpath(c)
    if given:
        raise KitError('%s is not the game folder (it has no assets/characters)' % given)
    raise KitError('the game was not found in Steam\'s folders: give it with --game "<folder of %s>"' % GAME_DIR)


def archive(character):
    return 'assets/characters/%s/%s.zip' % (character, character)


def backup_root(game, character):
    """the folder that holds the kit's backup of this character's archive (an older name if it made one there)"""
    old = os.path.join(game, OLD_BACKUP_DIR)
    return old if os.path.isfile(os.path.join(old, *archive(character).split('/'))) else os.path.join(game, BACKUP_DIR)


def backup_path(game, character):
    return os.path.join(backup_root(game, character), *archive(character).split('/'))


def characters(game):
    """characters whose archive holds a <name>.oct"""
    out = []
    root = os.path.join(game, 'assets', 'characters')
    for c in sorted(os.listdir(root)):
        z = os.path.join(root, c, c + '.zip')
        if os.path.isfile(z):
            names = {e['name'].decode('latin1').lower() for e in INS.read_zip(open(z, 'rb').read())}
            if c.lower() + '.oct' in names:
                out.append(c)
    return out


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def find_original(game, character):
    """the game's own archive of this character: the tool's backup, the game's if no mod changed it, or another mod
    installer's backup (the '<name> backup' folders next to the game that keyloor's packs and others make)"""
    rel = archive(character).split('/')
    cands = [backup_path(game, character), os.path.join(game, *rel)]
    cands += [os.path.join(game, d, *rel) for d in sorted(os.listdir(game)) if d.lower().endswith(' backup')]
    want = ORIGINAL.get(character)
    for c in cands:
        if os.path.isfile(c) and (want is None or md5(c) == want):
            return c
    return None


SOURCE = '.ts3tool_source'                              # in an extracted character: which archive it came from


def extract(game, character, dst, force, log):
    """the game's own files of this character (found by find_original); with force, the game's archive as it is"""
    live = os.path.join(game, *archive(character).split('/'))
    if not os.path.isfile(live):
        raise KitError('the game has no %s (see: kit.py characters)' % archive(character))
    src = find_original(game, character)
    if src is None:
        msg = ('%s is not the game\'s original: another mod is installed on this character and no backup of the '
               'original was found. Uninstall that mod first (with its own uninstaller)' % archive(character))
        if not force:
            raise KitError(msg + ', or run again with --force to build on it anyway.')
        log('warning: ' + msg)
        src = live
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    ents = INS.read_zip(open(src, 'rb').read())
    for e in ents:
        p = os.path.join(dst, *e['name'].decode('latin1').split('/'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(INS.unpack(e))
    with open(os.path.join(dst, SOURCE), 'w', encoding='utf-8') as f:
        f.write('%s\n%s\n' % ('original' if src != live or character not in ORIGINAL or md5(live) == ORIGINAL[character]
                              else 'modded', src))
    log('extracted %d files of %s from %s' % (len(ents), character, os.path.relpath(src, game)))


def needs_extract(game, character, dst):
    """not extracted yet, extracted by an older version (no SOURCE note), or built on a modded archive while an
    original can be found now"""
    if not os.path.isfile(os.path.join(dst, character + '.oct')) or not os.path.isfile(os.path.join(dst, SOURCE)):
        return True
    return open(os.path.join(dst, SOURCE), encoding='utf-8').readline().strip() == 'modded' and \
        find_original(game, character) is not None


def check_closed():
    if INS.game_running():
        raise KitError('close Toy Story 3 first')


# ------------------------------------------------------------------------------------------- project
def load_project(work):
    p = os.path.join(work, 'kit_project.json')
    return json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else {}


def save_project(work, proj):
    with open(os.path.join(work, 'kit_project.json'), 'w', encoding='utf-8') as f:
        json.dump(proj, f, indent=2)


def guess_textures(fbx):
    """a 'textures' folder next to the FBX (or one up), else the FBX's own folder if it holds images"""
    d = os.path.dirname(os.path.abspath(fbx))
    for c in (os.path.join(d, 'textures'), os.path.join(d, 'Textures'), os.path.join(os.path.dirname(d), 'textures')):
        if os.path.isdir(c):
            return c
    if any(fn.lower().endswith(IMAGES) for fn in os.listdir(d)):
        return d
    return None


class Tee:
    def __init__(self, *outs):
        self.outs = outs

    def write(self, s):
        for o in self.outs:
            o.write(s)

    def flush(self):
        for o in self.outs:
            o.flush()


# ------------------------------------------------------------------------------------------- previews
def previews(work, character, out_dir, game_dir):
    os.makedirs(os.path.join(work, 'previews'), exist_ok=True)
    bounds = (np.array([-1.3, 0.0]), np.array([1.3, 2.0]))
    row = RD.draw(game_dir, character, None, bounds) + RD.draw(out_dir, character, 'oct', bounds)
    body = Image.new('RGB', (RD.W * len(row), RD.W), 'white')
    for k, im in enumerate(row):
        body.paste(im, (k * RD.W, 0))
    body.save(os.path.join(work, 'previews', 'body.png'))
    # the head, from three sides: framed on the model's own points above the game's neck (a model's face may sit
    # lower than the game's face bones)
    _, bones3, *_ = T.load(os.path.join(game_dir, character + '.oct'))
    neck = next(np.array(b['pivot']) for b in bones3 if b['name'].lower() == 'neck')
    parts, _, f = RD.load_mesh(out_dir, character)
    P = np.concatenate([p[0] for p in parts])
    top = P[(P[:, 1] > neck[1]) & (np.abs(P[:, 0]) < 0.3)]
    if not len(top):
        top = neck[None]
    c = np.array([0, (neck[1] + top[:, 1].max()) / 2, float(np.median(top[:, 2]))])
    half = max(0.2, 0.6 * (top[:, 1].max() - neck[1]))
    tex = RD.oct_textures(f)
    ims = []
    for yaw in (0, 35, 80):
        a = np.radians(yaw)
        R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
        rp = [(((P - c) @ R.T + c).astype(np.float32), (N @ R.T).astype(np.float32), UV, Tt, m) for P, N, UV, Tt, m in parts]
        img, _ = RD.raster(rp, 'front', tex, bounds=(c[:2] - half, c[:2] + half))
        ims.append(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)))
    fc = Image.new('RGB', (RD.W * len(ims), RD.W), 'white')
    for k, im in enumerate(ims):
        fc.paste(im, (k * RD.W, 0))
    fc.save(os.path.join(work, 'previews', 'face.png'))


# ------------------------------------------------------------------------------------------- commands
def prepare(work, proj, force=False, log=print):
    """check the project's settings, fill in the game and textures folders, save them, extract the character;
    the extracted character's folder"""
    if not proj.get('fbx') or not proj.get('character'):
        raise KitError('the first make needs --character and --fbx')
    if not os.path.isfile(proj['fbx']):
        raise KitError('no model at %s' % proj['fbx'])
    if not proj['fbx'].lower().endswith(('.fbx', '.obj')):
        raise KitError('the model must be an .fbx or an .obj file')
    proj['game'] = find_game(proj.get('game'))
    if not proj.get('textures'):
        proj['textures'] = guess_textures(proj['fbx'])
    os.makedirs(work, exist_ok=True)
    save_project(work, proj)
    c = proj['character']
    game_dir = os.path.join(work, 'game', c)
    if needs_extract(proj['game'], c, game_dir):
        extract(proj['game'], c, game_dir, force, log)
    return game_dir


def detect(work, proj, force=False, log=print):
    """the map's tables as the kit would write them now (the project's own bone and material choices applied),
    without writing anything but the project file: (tables, automap info)"""
    game_dir = prepare(work, proj, force, log)
    objlib.use_joints(proj.get('joints'))
    tables, info = AM.automap(proj['fbx'], game_dir, proj['character'], log, proj.get('bones'), proj.get('adjust'))
    AM.add_textures(tables, proj['fbx'], proj['textures'], log, proj.get('materials'))
    return tables, info


def build(work, proj, remap=False, force=False):
    """map (unless the project has one and remap is False), convert, check, previews; everything printed also goes to
    report.txt. Returns the materials to check."""
    game_dir = prepare(work, proj, force)
    c, fbx, tex = proj['character'], proj['fbx'], proj['textures']
    objlib.use_game(game_dir, c)
    objlib.use_joints(proj.get('joints'))               # an OBJ's joints the user moved by hand
    with open(os.path.join(work, 'report.txt'), 'w', encoding='utf-8') as rep, \
            contextlib.redirect_stdout(Tee(sys.stdout, rep)):
        print('%s: %s -> %s' % (CREDIT, os.path.basename(fbx), c))
        print('game: %s\ntextures: %s' % (proj['game'], tex or '(none: solid colours)'))
        mpath = os.path.join(work, 'map.py')
        check = []
        if os.path.isfile(mpath) and not remap:
            print('\n== map: using your map.py as it is (--remap writes a new one)')
        else:
            print('\n== map: bones')
            tables, info = AM.automap(fbx, game_dir, c, print, proj.get('bones'), proj.get('adjust'))
            AM.report(info)
            print('\n== map: textures')
            check = AM.add_textures(tables, fbx, tex, print, proj.get('materials'))
            AM.write_map(tables, info, mpath, fbx, c)
            print('wrote', mpath)

        print('\n== convert')
        out = os.path.join(work, 'out', c)
        if os.path.isdir(out):
            shutil.rmtree(out)
        CV.run(game_dir, c, fbx, tex or work, mpath, out)
        b = open(os.path.join(out, c + '.oct'), 'rb').read()
        if Oct.parse(b).to_bytes() != b:
            raise KitError('the converted %s.oct does not read back the same: do not install it' % c)
        print('check: %s.oct reads back byte for byte' % c)

        print('\n== previews')
        previews(work, c, out, game_dir)
        print('previews/body.png (left: the game\'s %s, right: yours), previews/face.png' % c)

        print('\n== done')
        if check:
            print('CHECK in map.py: no image matched %s (guessed, marked CHECK)' % ', '.join(map(repr, check)))
    return check


def make(a):
    work = os.path.abspath(a.project)
    proj = load_project(work)
    for k in ('character', 'fbx', 'textures', 'game'):
        v = getattr(a, k)
        if v:
            proj[k] = os.path.abspath(v) if k != 'character' else v
    build(work, proj, a.remap, a.force)
    print('Look at the previews. To fine-tune, edit map.py and run make again (docs/GUIA_MANUAL.md).')
    print('Into the game: kit.py install "%s"   (back to the original: kit.py restore "%s")' % (a.project, a.project))
    if a.install:
        install(a)


def install_project(work):
    proj = load_project(work)
    if not proj:
        raise KitError('%s is not a kit project: run make first' % work)
    c, game = proj['character'], find_game(proj.get('game'))
    out = os.path.join(work, 'out', c)
    if not os.path.isfile(os.path.join(out, c + '.oct')):
        raise KitError('nothing converted yet: run make first')
    check_closed()
    with modstore.unmanaged(game, archive(c)):
        INS.BACKUP = backup_root(game, c)               # the game's own archive is kept next to the game
        INS.install(game, archive(c), out)
    return c


def restore_project(work):
    proj = load_project(work)
    if not proj:
        raise KitError('%s is not a kit project' % work)
    c, game = proj['character'], find_game(proj.get('game'))
    bak = backup_path(game, c)
    if not os.path.isfile(bak):
        raise KitError('the kit has not changed %s (no backup at %s)' % (c, bak))
    check_closed()
    with modstore.unmanaged(game, archive(c)):
        shutil.copy2(bak, os.path.join(game, *archive(c).split('/')))
    return c


def export_pack(work, name, version='1.0', author='', what='', model_credits=''):
    """a Nexus pack in <project>/pack/: '<name> for TS3/' (installer, .bat files, README, patches/) and its zip.
    The patches are made by tools/build_release.py from the converted files and the game's own archive."""
    import re, zipfile, build_release
    name = re.sub(r'[^A-Za-z0-9 ._()-]', '', name).strip()
    version = modfile.version(version)
    if not name:
        raise KitError('the pack needs a name (letters, digits, spaces)')
    proj = load_project(work)
    c, game = proj['character'], find_game(proj.get('game'))
    out = os.path.join(work, 'out', c)
    if not os.path.isfile(os.path.join(out, c + '.oct')):
        raise KitError('nothing converted yet: run make first')
    rel = archive(c)
    # the game's own archive: the kit's backup, or the game's if nothing changed it
    orig = find_original(game, c)
    if orig is None:
        raise KitError('%s is changed by another mod and no backup of the original was found: uninstall that mod '
                       'first, the pack is made against the game\'s own archive' % rel)
    # The project owns its mod identity, which survives renames and new exports.
    if 'mod_id' not in proj:
        proj['mod_id'] = 'mod.' + uuid.uuid4().hex
        save_project(work, proj)
    modfile.identifier(proj['mod_id'])
    root = os.path.join(work, 'pack')
    stage = os.path.join(root, 'build')
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    bak = os.path.join(stage, 'original')
    os.makedirs(os.path.dirname(os.path.join(bak, *rel.split('/'))))
    shutil.copy2(orig, os.path.join(bak, *rel.split('/')))
    shutil.copytree(out, os.path.join(stage, 'output', c))
    folder = '%s for TS3' % name
    with open(os.path.join(stage, 'mod.py'), 'w', encoding='utf-8') as f:
        f.write('TITLE = %r\nRELEASE = %r\nARCHIVES = [(%r, %r)]\n' % (name + ' for Toy Story 3', os.path.join('..', folder), c, rel))
    dst = os.path.join(root, folder)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    old = INS.BACKUP
    INS.BACKUP = bak                                     # build_release reads the game's archive from install.BACKUP
    try:
        build_release.main(stage)
    finally:
        INS.BACKUP = old
    shutil.rmtree(stage)

    script = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_') + '.ps1'
    what = what.strip() or '%s replaces %s in single player.' % (name, c)
    fill = {'@@NAME@@': name, '@@VERSION@@': version, '@@MARKER@@': rel.replace('/', '\\'), '@@ARCHIVE@@': rel,
            '@@ARCHIVE_WIN@@': rel.replace('/', '\\'), '@@SCRIPT@@': script, '@@AUTHOR@@': author.strip() or 'unknown',
            '@@MODEL_CREDITS@@': model_credits.strip() or 'see the mod page'}
    tpl = os.path.join(paths.KIT, 'kit', 'pack')

    def write(src, dst_name, extra=None, ps=False):
        t = open(os.path.join(tpl, src), encoding='utf-8').read()
        f2 = dict(fill, **(extra or {}))
        f2['@@WHAT@@'] = what.replace("'", "''") if ps else what   # inside PowerShell single quotes
        for k, v in f2.items():
            t = t.replace(k, v)
        enc = 'utf-8-sig' if ps else 'utf-8'                       # Windows PowerShell 5.1 needs the BOM for accents
        with open(os.path.join(dst, dst_name), 'w', encoding=enc, newline='\r\n') as f:
            f.write(t)
    write('installer.ps1', script, ps=True)
    write('action.bat', 'Install %s.bat' % name, {'@@ACTION@@': 'install', '@@ACTION_TITLE@@': 'Installs'})
    write('action.bat', 'Uninstall %s.bat' % name, {'@@ACTION@@': 'uninstall', '@@ACTION_TITLE@@': 'Uninstalls'})
    write('README.txt', 'README.txt')
    metadata = modfile.validate({
        'schema_version': 1, 'id': proj['mod_id'], 'name': name, 'version': version,
        'author': author.strip(), 'description': what, 'game': 'ts3-pc',
        'credits': [CREDIT] + ([model_credits.strip()] if model_credits.strip() else []),
        'patches': [{'manifest': 'patches/manifest.txt'}], 'files': [], 'requires': [], 'conflicts': []})
    with open(os.path.join(dst, 'mod.json'), 'wb') as f:
        f.write(modfile.json_bytes(metadata))
    zpath = os.path.join(root, '%s v%s.zip' % (folder, version))
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(dst):
            for fn in files:
                p = os.path.join(base, fn)
                z.write(p, os.path.join(folder, os.path.relpath(p, dst)))
    return dst, zpath


def install(a):
    c = install_project(os.path.abspath(a.project))
    print('installed. Start the game and play as %s; kit.py restore "%s" puts the original back.' % (c, a.project))


def restore(a):
    c = restore_project(os.path.abspath(a.project))
    print('restored the game\'s %s' % archive(c))


def list_characters(a):
    game = find_game(a.game)
    print('game:', game)
    for c in characters(game):
        live = os.path.join(game, *archive(c).split('/'))
        state = ''
        if os.path.isfile(backup_path(game, c)):
            state = '  (changed by the kit)'
        elif c in ORIGINAL and md5(live) != ORIGINAL[c]:
            state = '  (changed by another mod)'
        print('  %s%s' % (c, state))


def doctor(a):
    """what the tool runs on, for a bug report: versions, the game, the original archives, the 3D preview"""
    import platform, PIL
    print(CREDIT)
    print('python %s, %s%s' % (platform.python_version(), platform.platform(), ' (frozen .exe)' if paths.FROZEN else ''))
    print('numpy %s, Pillow %s' % (np.__version__, PIL.__version__))
    try:
        import moderngl
        ctx = moderngl.create_context(standalone=True)
        print('3D preview: moderngl %s, OpenGL %s, %s' % (moderngl.__version__, ctx.info['GL_VERSION'], ctx.info['GL_RENDERER']))
        ctx.release()
    except Exception as e:
        print('3D preview: not available (%s): the window shows still images' % (str(e).splitlines() or [e])[0])
    try:
        game = find_game(a.game)
        print('game:', game)
        for c in ORIGINAL:
            src = find_original(game, c)
            print('  %-14s original: %s' % (c, os.path.relpath(src, game) if src else 'none found (another mod changed it)'))
    except KitError as e:
        print('game:', e)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'mods':
        import modcli
        return modcli.main(argv[1:], game_resolver=find_game)
    p = argparse.ArgumentParser(prog='kit.py', description=CREDIT)
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('characters'); s.add_argument('--game'); s.set_defaults(fn=list_characters)
    s = sub.add_parser('doctor'); s.add_argument('--game'); s.set_defaults(fn=doctor)
    sub.add_parser('mods', help='non-interactive mod manager; mods --help for commands')
    s = sub.add_parser('make')
    s.add_argument('project'); s.add_argument('--character'); s.add_argument('--fbx'); s.add_argument('--textures')
    s.add_argument('--game'); s.add_argument('--remap', action='store_true'); s.add_argument('--install', action='store_true')
    s.add_argument('--force', action='store_true'); s.set_defaults(fn=make)
    for name, fn in (('install', install), ('restore', restore)):
        s = sub.add_parser(name); s.add_argument('project'); s.set_defaults(fn=fn)
    s = sub.add_parser('export')
    s.add_argument('project'); s.add_argument('--name', required=True); s.add_argument('--version', default='1.0')
    s.add_argument('--author', default=''); s.add_argument('--what', default='')
    s.add_argument('--model-credits', default='')
    s.set_defaults(fn=lambda a: print('pack: %s\nzip:  %s' % export_pack(
        os.path.abspath(a.project), a.name, a.version, a.author, a.what, a.model_credits)))
    a = p.parse_args(argv)
    try:
        a.fn(a)
    except (KitError, ValueError, OSError) as e:
        sys.exit('error: %s' % e)


if __name__ == '__main__':
    raise SystemExit(main())
