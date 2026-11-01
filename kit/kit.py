"""Toy Story 3 Modding Tool, characters: from a rigged FBX (or an OBJ) to Toy Story 3, in one command.

  python kit.py characters [--game <dir>]
      the characters that can be replaced, and where the game is
  python kit.py make <project dir> --character woody --fbx <model.fbx> [--textures <dir>] [--game <dir>]
                     [--remap] [--install] [--force]
      extract the character from the game, write the map (bones + textures), convert, check, draw the previews;
      --install also puts it into the game. The settings are kept in <project dir>/kit_project.json, so the next
      'make' needs only the project dir. An existing <project dir>/map.py is used as it is (your edits stay):
      --remap writes it again from scratch.
  python kit.py adjust <project dir> [--set KEY=VALUE] [--put KEY NAME=VALUE] [--unset KEY] [--drop KEY NAME]
                       [--joint BONE=X,Y,Z] [--reset-joints] [--save-version NAME] [--load-version NAME]
                       [--delete-version NAME] [--info] [--json]
      the fine-tuning the window's Adjustments tab makes (kit_project.json 'adjust'; keys in ADJUST_KEYS):
      shows it, with --info also what the tool measured and what can be chosen (bones, materials, eyes, face);
      changes it; keeps named versions of it. Then 'make --remap' converts with it.
  python kit.py diagnose <project dir> [--fix ID [--option N]] [--json]
      what looks wrong or could be better (a stretched neck, a torso made much wider, parts at the stretch limit,
      materials with no image, shut eyes, a face that could move...), each with its fixes; --fix applies one to
      the adjustments. Then 'make --remap'.
  python kit.py install <project dir>
  python kit.py restore <project dir>
      put the converted character into the game / put the game's own archive back (the game must be closed)
  python kit.py export <project dir> --name "<pack name>" [--version 1.0] [--author <you>] [--what <one line>]
                       [--model-credits <who made the model>] [--installer]
      a pack for Nexus in <project dir>/pack/: only this mod's changes to the game archive, mod.json and README,
      zipped; players install it with the Modding Tool (no scripts: no manual review on Nexus). --installer adds
      its own installer (.bat, the same as keyloor's mods) for players without the tool

What it writes in the project dir: game/<character>/ (the game's files), map.py, out/<character>/ (the converted
files), previews/body.png and face.png, report.txt (everything it printed). The first install keeps the game's
archive in '<game>/TS3 Modding Tool backup/'.
"""
import argparse, contextlib, hashlib, json, os, re, shutil, sys, uuid
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
    """a refusal the user can act on; code is the stable name --json gives it (from the message when not given)"""
    CODES = (('close Toy Story 3', 'game_running'), ('game was not found', 'game_not_found'),
             ('is not the game folder', 'game_not_found'), ('the game has no', 'no_character'),
             ('not a kit project', 'no_project'), ('no project at', 'no_project'),
             ('nothing converted yet', 'not_converted'), ('no backup of the original', 'original_missing'),
             ('--force to build on it', 'original_missing'), ('does not read back the same', 'check_failed'),
             ('has not changed', 'not_installed'))

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code or next((c for k, c in self.CODES if k in message), 'rejected')


class Parser(argparse.ArgumentParser):
    """argument errors as KitError, so --json reports them too"""
    def error(self, message):
        raise KitError(message, 'invalid_arguments')


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
    if not os.path.isfile(p):
        return {}
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save_project(work, proj):
    with open(os.path.join(work, 'kit_project.json'), 'w', encoding='utf-8') as f:
        json.dump(proj, f, indent=2)


# kit_project.json 'adjust': what each key holds (the window's Adjustments tab writes them; 'adjust' sets them)
ADJUST_KEYS = {
    'head_cm': 'number: the head (and the end of the neck) up (+) or down (-), in cm',
    'torso': '[x, y, z]: the torso block wider / taller / deeper, in percent',
    'head_pct': 'number: head size, percent', 'neck_pct': 'number: neck thickness, percent',
    'arms_pct': 'number: arm thickness, percent', 'legs_pct': 'number: leg thickness, percent',
    'scale_pct': "number: the whole model bigger / smaller, percent (the joints stay on the game's)",
    'stretch_limit': '{neck | arms | legs | hands: L}: that part may stretch up to L and squeeze to 1/L (1.25 is '
                     "the converter's own)",
    'shoulders_cm': 'number: each arm further out (+) or in (-), cm',
    'hips_cm': 'number: each leg further out (+) or in (-), cm',
    'props': '{model bone: hand_left | hand_right | head | chest | hips | out}: where a loose object goes',
    'garments': '{model material: percent}: that material narrower / wider (x and z, about the hips)',
    'weights': '{model bone: game bone | {game bone: share}}: which game bones move that bone\'s vertices',
    'smooth': 'whole number: passes smoothing the weights (0 = none)',
    'eyes_open': '{"top": degrees, "bottom": degrees}: open shut lids (needs eye and lid bones)',
    'face': 'true / false: the face moves with the game\'s face bones (jaw, lips, brows)',
    'head_by_face': 'true / false: place the head by the face bones instead of the head joint'}


def check_adjust(adj):
    """KitError (code invalid_value) if a key or value is not one the tool reads"""
    try:
        _check_adjust(adj)
    except KitError as e:
        raise KitError(str(e), 'invalid_value') from None


def _check_adjust(adj):
    for k, v in adj.items():
        if k not in ADJUST_KEYS:
            raise KitError('unknown adjust key %r (known: %s)' % (k, ', '.join(ADJUST_KEYS)), 'invalid_value')
        if k in ('props', 'garments', 'weights', 'eyes_open', 'stretch_limit') and not isinstance(v, dict):
            raise KitError('%s must be a JSON object: %s' % (k, ADJUST_KEYS[k]))
        if k == 'torso' and not (isinstance(v, list) and len(v) == 3):
            raise KitError('torso must be [x, y, z]')
        if k == 'stretch_limit':
            bad = [p for p in v if p not in ('neck', 'arms', 'legs', 'hands')]
            if bad:
                raise KitError('stretch_limit: unknown part %r (neck, arms, legs, hands)' % bad[0])
        if k == 'props':
            bad = [p for p in v.values() if p not in tuple(AM.PROP_PLACES) + ('out',)]
            if bad:
                raise KitError('props: unknown place %r (hand_left, hand_right, head, chest, hips, out)' % bad[0])


def strain(work):
    """how far the last conversion stretched or squeezed each part, from report.txt: {game bone: factor} (1 = the
    model's own length; the converter keeps limbs within 0.8..1.25 and the torso block's width / height too)"""
    out = {}
    try:
        with open(os.path.join(work, 'report.txt'), encoding='utf-8') as f:
            lines = f.read().splitlines()
    except OSError:
        return out
    torso = None
    for line in lines:
        m = re.match(r'^\s+(.+?)\s+->\s+(\S+)\s+turn\s+-?[\d.]+ deg\s+stretch ([\d.]+)', line)
        if m:
            out[m.group(2)] = float(m.group(3))
        m = re.search(r'torso block.*scale \[([^\]]+)\]', line)
        if m:
            torso = [float(x) for x in m.group(1).split()]
    if torso:
        k = max(torso[:2], key=lambda x: abs(np.log(x)))
        for n in ('Hips', 'Spine1', 'Spine2', 'Spine3'):
            out.setdefault(n, k)
    return out


LIMIT_PARTS = {'arms': ('Bicep', 'Forearm'), 'legs': ('Thigh', 'Calf'), 'hands': ('Hand',)}


def limit_step(k):
    """a stretch limit just above k, on the window's 0.05 steps (at most 2.5)"""
    return min(2.5, float(np.ceil((k + 0.05) * 20) / 20))   # some room: the converter measures a little differently


def merge_adjust(adj, change):
    """adj with change applied: dict values (stretch_limit, props...) are merged entry by entry"""
    out = json.loads(json.dumps(adj or {}))
    for k, v in change.items():
        out[k] = dict(out[k], **v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def diagnose(work, proj, tables=None, info=None):
    """what looks wrong or could be better, in plain words, each with the adjust changes that fix it:
    [{id, level ('warn' | 'tip'), message, args, fixes: [{label, set}], see: tab}]. 'kit.py diagnose' and the
    window's Diagnosis tab show it; tables / info from detect() (measured again when not given)."""
    if tables is None or info is None:
        tables, info = detect(work, proj, log=lambda *a: None)
    adj = proj.get('adjust', {})
    lim_now = adj.get('stretch_limit', {})
    out = []

    def add(id_, level, message, args=None, fixes=(), see=None):
        args = args or {}
        out.append(dict(id=id_, level=level, message=message % args, args=args, fixes=list(fixes), see=see))

    nf = info.get('neck')
    lim = float(lim_now.get('neck', 1.25))
    if nf and nf.get('stretch') and not 1 / lim - 0.005 <= nf['stretch'] <= lim + 0.005:
        args = dict(nf, how='stretched' if nf['stretch'] > 1 else 'squeezed')
        add('neck', 'warn', 'The neck is %(how)s past the limit: the model\'s is %(model_cm)s cm, the game\'s '
            '%(game_cm)s cm (x%(stretch)s). It will look distorted.', args,
            [{'label': 'head_natural', 'set': {'head_cm': nf['natural_cm']}},
             {'label': 'neck_limit', 'set': {'stretch_limit': {'neck': limit_step(max(nf['stretch'],
                                                                                      1 / nf['stretch']))}}}],
            'adjust')
    tf = info.get('torso') or {}
    torso = list(adj.get('torso', [100, 100, 100]))
    for ax, key in ((0, 'width_pct'), (1, 'height_pct')):
        p = tf.get(key, 100)
        if p >= 115 or p <= 87:
            keep = list(torso); keep[ax] = int(round(10000 / p))
            add('torso_' + key[:-4], 'warn' if p in (80, 125) else 'tip',
                'To reach the character\'s shoulders and hips the torso is made %(pct)s%% as %(dim)s as the model\'s.',
                {'pct': p, 'dim': 'wide' if ax == 0 else 'tall'},
                [{'label': 'torso_own', 'set': {'torso': keep}}], 'adjust')
    st = strain(work)
    for part, prefixes in LIMIT_PARTS.items():
        lim = float(lim_now.get(part, 1.25))
        hit = {n: k for n, k in st.items() if n.startswith(prefixes) and (k >= lim - 0.005 or k <= 1 / lim + 0.005)}
        if hit:
            worst = max(hit.values(), key=lambda k: abs(np.log(k)))
            add('limit_' + part, 'warn', 'The %(part)s reach the stretch limit (x%(k)s): they may not reach the '
                'game\'s joints. Raise the limit, or check their joints.', {'part': part, 'k': worst},
                [{'label': 'raise_limit', 'set': {'stretch_limit': {part: round(min(2.5, lim + 0.25), 2)}}}], 'joints')
    check = [m for m, why in tables.get('_tex_notes', {}).items() if why == 'check']
    if check:
        add('materials', 'warn', 'No image matched these materials (a guess is used): %(list)s.',
            {'list': ', '.join(check)}, (), 'materials')
    sk, body = info['skeleton'], info['body']
    if body.get('handLeft') in sk.pos and sk.pos[body['handLeft']][0] < 0:
        add('backwards', 'warn', 'The model seems to face backwards (its left hand is on the right): export it '
            'facing forward.', {}, (), None)
    if info.get('eyes') and not adj.get('eyes_open'):
        add('eyes', 'tip', 'The model has eye and lid bones (%(list)s): if its eyes look shut, they can be opened.',
            {'list': ', '.join(e for e, _, _ in info['eyes'].values())},
            [{'label': 'open_eyes', 'set': {'eyes_open': {'top': 15, 'bottom': 5}}}], 'adjust')
    if len(info.get('face') or {}) >= 2 and not adj.get('face'):
        add('face', 'tip', 'The model has face bones (%(n)d: jaw, lips, brows): its face can move with the game\'s.',
            {'n': len(info['face'])}, [{'label': 'animate_face', 'set': {'face': True}}], 'adjust')
    for b in info.get('extras', []):
        now = tables['WEIGHTS'].get(b)
        if set(AM.words(b)) & AM.PROP_WORDS and b not in adj.get('props', {}) and \
                not (isinstance(now, str) and now.startswith('Hand')):
            add('prop_' + b, 'tip', '%(bone)s looks like a held object but moves with %(now)s.', {'bone': b, 'now': now},
                [{'label': 'prop_right', 'set': {'props': {b: 'hand_right'}}},
                 {'label': 'prop_left', 'set': {'props': {b: 'hand_left'}}}], 'accessories')
    return out


def diagnose_cmd(a):
    work = os.path.abspath(a.project)
    proj = load_project(work)
    if not proj:
        raise KitError('no project at %s (make it first)' % work)
    found = diagnose(work, proj)
    applied = None
    if a.fix:
        item = next((d for d in found if d['id'] == a.fix), None)
        if item is None or not item['fixes']:
            raise KitError('no fix for %r (ids with fixes: %s)' % (a.fix, ', '.join(d['id'] for d in found if d['fixes'])
                                                                   or 'none'), 'invalid_value')
        if not 0 <= a.option < len(item['fixes']):
            raise KitError('%s has %d fixes (--option 0..%d)' % (a.fix, len(item['fixes']), len(item['fixes']) - 1),
                           'invalid_value')
        applied = item['fixes'][a.option]
        proj['adjust'] = merge_adjust(proj.get('adjust', {}), applied['set'])
        check_adjust(proj['adjust'])
        save_project(work, proj)
    out = dict(project=work, found=found, applied=applied, next='make --remap converts with it' if applied else None)
    if a.json:
        return out
    for d in found:
        print('[%s] %s: %s' % (d['level'], d['id'], d['message']))
        for k, f in enumerate(d['fixes']):
            print('    fix --fix %s --option %d (%s): adjust %s' % (d['id'], k, f['label'], json.dumps(f['set'])))
    if not found:
        print('nothing to point out')
    if applied:
        print('applied: %s. Convert with it: kit.py make "%s" --remap' % (json.dumps(applied['set']), a.project))
    return out


def adjust_info(work, proj):
    """what the tool measured on the model and what the adjust keys can name (needs the model and the game)"""
    tables, info = detect(work, proj, log=lambda *a: None)
    _, bones3, *_ = T.load(os.path.join(work, 'game', proj['character'], proj['character'] + '.oct'))
    sk = info['skeleton']
    return dict(neck=info['neck'], torso=info['torso'],
                props=[dict(bone=b, now=tables['WEIGHTS'].get(b)) for b in info['extras']],
                places=list(AM.PROP_PLACES) + ['out'],
                materials=sorted(tables.get('_tex_tris', {})),
                eyes={s: dict(eye=e, top=t, bottom=b) for s, (e, t, b) in info['eyes'].items()},
                face=info['face'], weights=tables['WEIGHTS'], model_bones=sorted(sk.skinned),
                game_bones=[b['name'] for b in bones3], joints=dict(info['body'], moved=list(info['moved'])),
                stretch=strain(work))


def adjust(a):
    work = os.path.abspath(a.project)
    proj = load_project(work)
    if not proj:
        raise KitError('no project at %s (make it first)' % work)
    adj = dict(proj.get('adjust', {}))

    def value(s):
        try:
            return json.loads(s)
        except ValueError:
            return s
    for kv in a.set or []:
        k, _, v = kv.partition('=')
        adj[k.strip()] = value(v)
    for k, kv in a.put or []:
        name, _, v = kv.partition('=')
        d = dict(adj.get(k) or {})
        d[name] = value(v)
        adj[k] = d
    for k in a.unset or []:
        adj.pop(k, None)
    for k, name in a.drop or []:
        if isinstance(adj.get(k), dict):
            adj[k].pop(name, None)
            if not adj[k]:
                adj.pop(k)
    check_adjust(adj)
    joints = dict(proj.get('joints', {}))
    if a.reset_joints:
        joints = {}
    for kv in a.joint or []:
        name, _, v = kv.partition('=')
        xyz = [float(x) for x in v.split(',')]
        if len(xyz) != 3:
            raise KitError('--joint wants BONE=X,Y,Z', 'invalid_value')
        joints[name] = xyz
    versions = proj.get('adjust_versions', {})
    if a.load_version:
        if a.load_version not in versions:
            raise KitError('no version %r (saved: %s)' % (a.load_version, ', '.join(versions) or 'none'),
                           'invalid_value')
        adj = dict(versions[a.load_version].get('adjust', {}))
        joints = dict(versions[a.load_version].get('joints', {}))
    for key, val in (('adjust', adj), ('joints', joints)):
        if val:
            proj[key] = val
        else:
            proj.pop(key, None)
    if a.save_version:
        versions[a.save_version] = {k: proj[k] for k in ('adjust', 'joints') if k in proj}
    if a.delete_version:
        versions.pop(a.delete_version, None)
    if versions:
        proj['adjust_versions'] = versions
    else:
        proj.pop('adjust_versions', None)
    changed = any([a.set, a.put, a.unset, a.drop, a.joint, a.reset_joints, a.save_version, a.load_version,
                   a.delete_version])
    if changed:
        save_project(work, proj)
    out = dict(project=work, adjust=proj.get('adjust', {}), joints=proj.get('joints', {}),
               versions=sorted(versions), keys=ADJUST_KEYS,
               next='make --remap converts with it' if changed else None)
    if a.info:
        out['info'] = adjust_info(work, proj)
    if a.json:
        return out
    print('project: %s' % work)
    print('adjust: %s' % json.dumps(out['adjust'], ensure_ascii=False))
    if out['joints']:
        print('joints moved by hand: %s' % ', '.join(out['joints']))
    print('versions: %s' % (', '.join(out['versions']) or 'none'))
    if 'info' in out:
        i = out['info']
        if i['neck']:
            print('neck: model %(model_cm)s cm, game %(game_cm)s cm, stretched x%(stretch)s; head_cm %(natural_cm)s '
                  'keeps its own length' % i['neck'])
        if i['torso']:
            print('torso: the tool already makes it %s%% wide, %s%% tall' % (i['torso'].get('width_pct', 100),
                                                                          i['torso'].get('height_pct', 100)))
        print('eyes found: %s' % (', '.join('%s %s (%d top / %d bottom lid bones)' % (s, e['eye'], len(e['top']),
              len(e['bottom'])) for s, e in i['eyes'].items()) or 'none'))
        print('face bones found: %s' % (', '.join('%s=%s' % kv for kv in i['face'].items()) or 'none'))
        print('loose bones (props): %s' % (', '.join(p['bone'] for p in i['props']) or 'none'))
        print('materials (garments): %s' % ', '.join(i['materials']))
    if changed:
        print('saved. Convert with it: kit.py make "%s" --remap' % a.project)
    return out


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
def compare_preview(work, character, before, now):
    """previews/compare.png: the conversion before this one next to this one, front and side"""
    bounds = (np.array([-1.3, 0.0]), np.array([1.3, 2.0]))
    row = RD.draw(before, character, 'oct', bounds) + RD.draw(now, character, 'oct', bounds)
    im = Image.new('RGB', (RD.W * len(row), RD.W), 'white')
    for k, r in enumerate(row):
        im.paste(r, (k * RD.W, 0))
    im.save(os.path.join(work, 'previews', 'compare.png'))


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
        prev = os.path.join(work, 'out_prev', c)         # the conversion before this one, for comparing
        if os.path.isdir(out):
            if os.path.isdir(prev):
                shutil.rmtree(prev)
            os.makedirs(os.path.dirname(prev), exist_ok=True)
            shutil.move(out, prev)
        CV.run(game_dir, c, fbx, tex or work, mpath, out)
        b = open(os.path.join(out, c + '.oct'), 'rb').read()
        if Oct.parse(b).to_bytes() != b:
            raise KitError('the converted %s.oct does not read back the same: do not install it' % c)
        print('check: %s.oct reads back byte for byte' % c)

        print('\n== previews')
        previews(work, c, out, game_dir)
        print('previews/body.png (left: the game\'s %s, right: yours), previews/face.png' % c)
        if os.path.isfile(os.path.join(prev, c + '.oct')):
            compare_preview(work, c, prev, out)
            print('previews/compare.png (left: the conversion before, right: this one)')

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
    check = build(work, proj, a.remap, a.force)
    c = proj['character']
    data = dict(project=work, character=c, map=os.path.join(work, 'map.py'), out=os.path.join(work, 'out', c),
                report=os.path.join(work, 'report.txt'), check_materials=check, installed=None,
                previews=[os.path.join(work, 'previews', n) for n in ('body.png', 'face.png', 'compare.png')
                          if os.path.isfile(os.path.join(work, 'previews', n))])
    try:
        data['diagnosis'] = diagnose(work, load_project(work))
    except Exception as e:                                # a hand-made map the measuring can't follow
        data['diagnosis'], data['diagnosis_error'] = [], str(e)
    if not a.json:
        print('Look at the previews. To fine-tune, edit map.py and run make again (docs/GUIA_MANUAL.md).')
        print('Into the game: kit.py install "%s"   (back to the original: kit.py restore "%s")' % (a.project, a.project))
        warns = [d['id'] for d in data['diagnosis'] if d['level'] == 'warn']
        if warns:
            print('Diagnosis: %s (kit.py diagnose "%s" for the fixes)' % (', '.join(warns), a.project))
    if a.install:
        data['installed'] = install(a)
    return data


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


def export_pack(work, name, version='1.0', author='', what='', model_credits='', installer=False):
    """a Nexus pack in <project>/pack/: '<name> for TS3/' (mod.json, README, patches/) and its zip, installed with
    the Modding Tool (drag and drop, or 'mods install'): no scripts, so Nexus doesn't hold it for a manual review.
    installer=True adds the pack's own installer (.ps1 + .bat files) for players without the tool; Nexus reviews
    every upload with scripts by hand. The patches are made by tools/build_release.py from the converted files and
    the game's own archive."""
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
    if installer:
        write('installer.ps1', script, ps=True)
        write('action.bat', 'Install %s.bat' % name, {'@@ACTION@@': 'install', '@@ACTION_TITLE@@': 'Installs'})
        write('action.bat', 'Uninstall %s.bat' % name, {'@@ACTION@@': 'uninstall', '@@ACTION_TITLE@@': 'Uninstalls'})
    write('README.txt' if installer else 'README_tool.txt', 'README.txt')
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


def project_place(work):
    proj = load_project(work)
    game = find_game(proj.get('game'))
    c = proj['character']
    return dict(project=work, character=c, game=game, archive=os.path.join(game, *archive(c).split('/')),
                backup=backup_path(game, c))


def install(a):
    work = os.path.abspath(a.project)
    c = install_project(work)
    if not a.json:
        print('installed. Start the game and play as %s; kit.py restore "%s" puts the original back.' % (c, a.project))
    return project_place(work)


def restore(a):
    work = os.path.abspath(a.project)
    c = restore_project(work)
    if not a.json:
        print('restored the game\'s %s' % archive(c))
    return project_place(work)


def list_characters(a):
    game = find_game(a.game)
    found = []
    for c in characters(game):
        live = os.path.join(game, *archive(c).split('/'))
        bak, now = backup_path(game, c), md5(live)          # restored = the same as the tool's backup
        state = 'original' if (c in ORIGINAL and now == ORIGINAL[c]) or (os.path.isfile(bak) and md5(bak) == now) \
            else 'changed_by_tool' if os.path.isfile(bak) else 'changed_by_another_mod' if c in ORIGINAL else 'unknown'
        found.append(dict(name=c, state=state, archive=live))
    if not a.json:
        print('game:', game)
        notes = {'changed_by_tool': '  (changed by the kit)', 'changed_by_another_mod': '  (changed by another mod)'}
        for d in found:
            print('  %s%s' % (d['name'], notes.get(d['state'], '')))
    return dict(game=game, characters=found)


def doctor(a):
    """what the tool runs on, for a bug report: versions, the game, the original archives, the 3D preview"""
    import platform, PIL
    data = dict(tool=CREDIT, python=platform.python_version(), platform=platform.platform(), frozen=paths.FROZEN,
                numpy=np.__version__, pillow=PIL.__version__)
    try:
        import moderngl
        ctx = moderngl.create_context(standalone=True)
        data['preview_3d'] = dict(ok=True, moderngl=moderngl.__version__, opengl=ctx.info['GL_VERSION'],
                                  renderer=ctx.info['GL_RENDERER'])
        ctx.release()
    except Exception as e:
        data['preview_3d'] = dict(ok=False, error=(str(e).splitlines() or [type(e).__name__])[0])
    try:
        game = find_game(a.game)
        data['game'] = game
        data['originals'] = {c: find_original(game, c) for c in ORIGINAL}
    except KitError as e:
        data['game'], data['game_error'] = None, str(e)
    if not a.json:
        print(CREDIT)
        print('python %s, %s%s' % (data['python'], data['platform'], ' (frozen .exe)' if paths.FROZEN else ''))
        print('numpy %s, Pillow %s' % (data['numpy'], data['pillow']))
        g = data['preview_3d']
        print('3D preview: moderngl %s, OpenGL %s, %s' % (g['moderngl'], g['opengl'], g['renderer']) if g['ok'] else
              '3D preview: not available (%s): the window shows still images' % g['error'])
        if data['game']:
            print('game:', data['game'])
            for c, src in data['originals'].items():
                print('  %-14s original: %s' % (c, os.path.relpath(src, data['game']) if src else
                                                'none found (another mod changed it)'))
        else:
            print('game:', data['game_error'])
    return data


def export_cmd(a):
    work = os.path.abspath(a.project)
    pack, zpath = export_pack(work, a.name, a.version, a.author, a.what, a.model_credits, a.installer)
    if not a.json:
        print('pack: %s\nzip:  %s' % (pack, zpath))
    return dict(project=work, pack=pack, zip=zpath, installer=a.installer, mod_id=load_project(work).get('mod_id'))


def to_json(o):
    """what json can't write by itself: sets and tuples as lists, numpy numbers as numbers"""
    if isinstance(o, (set, tuple)):
        return list(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.generic):
        return o.item()
    return str(o)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'mods':
        import modcli
        return modcli.main(argv[1:], game_resolver=find_game)
    as_json = '--json' in argv                            # anywhere, as with the mods commands
    argv = [x for x in argv if x != '--json']
    p = Parser(prog='kit.py', description=CREDIT, epilog='--json: one JSON object on stdout (see docs/CLI.md)')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('characters'); s.add_argument('--game'); s.set_defaults(fn=list_characters)
    s = sub.add_parser('doctor'); s.add_argument('--game'); s.set_defaults(fn=doctor)
    sub.add_parser('mods', help='non-interactive mod manager; mods --help for commands')
    s = sub.add_parser('make')
    s.add_argument('project'); s.add_argument('--character'); s.add_argument('--fbx'); s.add_argument('--textures')
    s.add_argument('--game'); s.add_argument('--remap', action='store_true'); s.add_argument('--install', action='store_true')
    s.add_argument('--force', action='store_true'); s.set_defaults(fn=make)
    s = sub.add_parser('adjust', help='show / change the fine-tuning (kit_project.json adjust), then make --remap')
    s.add_argument('project')
    s.add_argument('--set', action='append', metavar='KEY=VALUE', help='VALUE is JSON (2.5, [100,110,100], true) or a word')
    s.add_argument('--put', nargs=2, action='append', metavar=('KEY', 'NAME=VALUE'), help='one entry of props / garments / weights')
    s.add_argument('--unset', action='append', metavar='KEY')
    s.add_argument('--drop', nargs=2, action='append', metavar=('KEY', 'NAME'))
    s.add_argument('--joint', action='append', metavar='BONE=X,Y,Z', help='move a joint (model bone, or an OBJ\'s automatic one)')
    s.add_argument('--reset-joints', action='store_true')
    s.add_argument('--save-version', metavar='NAME'); s.add_argument('--load-version', metavar='NAME')
    s.add_argument('--delete-version', metavar='NAME')
    s.add_argument('--info', action='store_true', help='also what was measured and what can be chosen')
    s.set_defaults(fn=adjust)
    s = sub.add_parser('diagnose', help='what looks wrong or could be better, with fixes (then make --remap)')
    s.add_argument('project')
    s.add_argument('--fix', metavar='ID', help='apply that finding\'s fix to the adjustments')
    s.add_argument('--option', type=int, default=0, help='which of its fixes (default 0)')
    s.set_defaults(fn=diagnose_cmd)
    for name, fn in (('install', install), ('restore', restore)):
        s = sub.add_parser(name); s.add_argument('project'); s.set_defaults(fn=fn)
    s = sub.add_parser('export')
    s.add_argument('project'); s.add_argument('--name', required=True); s.add_argument('--version', default='1.0')
    s.add_argument('--author', default=''); s.add_argument('--what', default='')
    s.add_argument('--model-credits', default='')
    s.add_argument('--installer', action='store_true',
                   help='also its own installer (.bat), for players without the tool; Nexus reviews it by hand')
    s.set_defaults(fn=export_cmd)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    command, data, error, status = 'kit', None, None, 0
    try:
        a = p.parse_args(argv)
        a.json = as_json
        command = 'kit.' + a.cmd
        if as_json:                                      # progress goes to stderr: stdout holds only the answer
            with contextlib.redirect_stdout(sys.stderr):
                data = a.fn(a)
        else:
            data = a.fn(a)
    except KitError as e:
        status = 2 if e.code == 'invalid_arguments' else 3
        error = {'code': e.code, 'message': str(e)}
    except modfile.ModError as e:
        status, error = 3, {'code': 'invalid_value', 'message': str(e)}
    except SystemExit as e:                              # --help, or the converter stopping with its reason
        if e.code in (0, None):
            raise
        status, error = 3, {'code': 'convert_failed', 'message': str(e.code)}
    except (ValueError, OSError) as e:
        status, error = 3, {'code': 'io_error' if isinstance(e, OSError) else 'invalid_data', 'message': str(e)}
    except KeyboardInterrupt:
        status, error = 130, {'code': 'interrupted', 'message': 'interrupted'}
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        status, error = 5, {'code': 'internal_error', 'message': str(e) or type(e).__name__}
    if as_json:
        print(json.dumps({'schema_version': 1, 'ok': status == 0, 'command': command, 'data': data, 'error': error},
                         ensure_ascii=False, default=to_json))
    elif error:
        print('error: %s' % error['message'], file=sys.stderr)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
