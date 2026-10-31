"""Install data-only mods with exclusive file ownership and recoverable multi-file transactions.

Backups preserve the state immediately before installation, including pre-existing external mods.
v1 refuses shared target files and external edits; it never guesses which version to restore.
"""
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
import zlib

import paths  # noqa: F401
import install as archive
from modfile import (ModError, Package, MAX_FILE, MAX_TOTAL, game_path, identifier, inside,
                     json_bytes, matches, relative, validate)

HOME = 'TS3 Modding Tool'
REGISTRY = HOME + '/installed.json'
JOURNAL = HOME + '/transaction.json'


@contextlib.contextmanager
def unmanaged(game, rel):
    """Keep the older project installer from bypassing the manager's ownership records."""
    store = Store(game)
    with store.locked():
        if store.path(JOURNAL).exists():
            raise ModError('interrupted operation: run mods recover first', 'recovery_required')
        for mod in store._state()['mods']:
            if any(f['path'].casefold() == rel.casefold() for f in mod['files']):
                raise ModError('remove the managed mod first: ' + mod['metadata']['id'])
        yield


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def hex_hash(value, length=64):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{%d}' % length, value):
        raise ModError('invalid checksum')
    return value


def read_file(path):
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > MAX_TOTAL:
        raise ModError('not a supported file: ' + str(path))
    return path.read_bytes()


def atomic(path, data):
    """Flush a sibling temporary file before replacing the live file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('xb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def rows(data):
    return [line.strip().split('|') for line in data.decode('utf-8-sig').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def parts(package, folder, stem):
    stem = relative(stem)
    blob = package.read(folder + stem + '.bin')
    result, seen, total = [], set(), 0
    for fields in rows(package.read(folder + stem + '.txt')):
        if len(fields) != 11 or fields[0] != 'put':
            raise ModError('invalid patch row: ' + stem)
        _, name, at, size, method, tm, dt, crc, usize, md5, before = fields
        name = relative(name)
        if name.casefold() in seen:
            raise ModError('duplicate patch member: ' + name)
        seen.add(name.casefold())
        at, size, method, tm, dt, usize = map(int, (at, size, method, tm, dt, usize))
        crc = int(hex_hash(crc.lower(), 8), 16)
        md5 = hex_hash(md5.lower(), 32)
        if before != 'new':
            hex_hash(before.lower(), 8)
        if at < 0 or size < 0 or at + size > len(blob) or method not in (0, 8) or not (0 <= usize <= MAX_FILE):
            raise ModError('invalid patch bounds or compression: ' + name)
        if not (0 <= tm <= 65535 and 0 <= dt <= 65535):
            raise ModError('invalid patch timestamp: ' + name)
        total += usize
        if total > MAX_TOTAL:
            raise ModError('patch exceeds unpacked size limit')
        compressed = blob[at:at + size]
        if method == 8:
            dec = zlib.decompressobj(-15)
            data = dec.decompress(compressed, usize + 1)
            if not dec.eof or dec.unused_data or dec.unconsumed_tail:
                raise ModError('invalid compressed patch: ' + name)
        else:
            data = compressed
        if len(data) != usize or zlib.crc32(data) != crc or hashlib.md5(data).hexdigest() != md5:
            raise ModError('patch checksum mismatch: ' + name)
        result.append((dict(name=name.encode('latin1'), method=method, time=tm, date=dt,
                            crc=crc, usize=usize, data=compressed, md5=bytes.fromhex(md5)), before))
    if not result:
        raise ModError('empty patch: ' + stem)
    return result


def merge(current, replacements):
    entries = archive.read_zip(current)
    by = {e['name'].decode('latin1').casefold(): i for i, e in enumerate(entries)}
    if len(by) != len(entries):
        raise ModError('duplicate members in game archive')
    for entry, before in replacements:
        key = entry['name'].decode('latin1').casefold()
        i = by.get(key)
        if (before == 'new' and i is not None) or (before != 'new' and
                (i is None or entries[i]['crc'] != int(before, 16))):
            raise ModError('archive member was changed by another mod: ' + key, 'external_change')
        if i is None:
            by[key] = len(entries)
            entries.append(entry)
        else:
            entry = dict(entry, name=entries[i]['name'])
            entries[i] = entry
    result = archive.write_zip(entries)
    check = archive.read_zip(result)
    if len(check) != len(entries) or any(a != b for a, b in zip(entries, check)):
        raise ModError('archive verification failed')
    return result


class Store:
    def __init__(self, game):
        self.game = Path(game).resolve()
        if not self.game.is_dir() or not any((self.game / p).is_dir() for p in ('assets', 'data_dx')):
            raise ModError('expected a game folder containing assets/ or data_dx/', 'game_not_found')

    def path(self, rel):
        return inside(self.game, rel)

    @contextlib.contextmanager
    def locked(self):
        root = self.path(HOME)
        root.mkdir(exist_ok=True)
        lock = self.path(HOME + '/lock')
        with lock.open('a+b') as f:
            if f.tell() == 0:
                f.write(b'0'); f.flush()
            f.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as e:
                raise ModError('another mod operation is running', 'store_busy') from e
            try:
                yield
            finally:
                f.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _closed(self):
        if os.name == 'nt' and archive.game_running():
            raise ModError('close Toy Story 3 before changing mods', 'game_running')

    def _state(self):
        raw = read_file(self.path(REGISTRY))
        if raw is None:
            return {'schema_version': 1, 'mods': []}
        state = json.loads(raw)
        if not isinstance(state, dict) or state.get('schema_version') != 1 or not isinstance(state.get('mods'), list):
            raise ModError('invalid installed.json; preserve the backups')
        ids, targets = set(), set()
        for mod in state['mods']:
            meta = validate(mod['metadata'])
            if meta['id'] in ids or not isinstance(mod['files'], list) or not mod['files']:
                raise ModError('invalid installed mod record')
            ids.add(meta['id'])
            for row in mod['files']:
                key = game_path(row['path']).casefold()
                if key in targets:
                    raise ModError('multiple owners of a registered file')
                targets.add(key)
                hex_hash(row['after'])
                if row['before'] is not None:
                    hex_hash(row['before'])
        return state

    def _object(self, key):
        data = read_file(self.path(HOME + '/objects/' + hex_hash(key)))
        if data is None or digest(data) != key:
            raise ModError('backup is missing or damaged: ' + key, 'backup_damaged')
        return data

    def _save(self, data):
        key = digest(data)
        if key is not None:
            path = self.path(HOME + '/objects/' + key)
            if not path.exists():
                atomic(path, data)
            elif digest(read_file(path)) != key:
                raise ModError('damaged backup: ' + key, 'backup_damaged')
        return key

    def _recover(self):
        raw = read_file(self.path(JOURNAL))
        if raw is None:
            return False
        journal = json.loads(raw)
        if not isinstance(journal, dict) or journal.get('schema_version') != 1 or not isinstance(journal.get('undo'), list):
            raise ModError('invalid recovery journal; preserve the backups')
        undo, seen = [], set()
        for row in journal['undo']:
            rel = row['path'] if row['path'] == REGISTRY else game_path(row['path'])
            if rel.casefold() in seen:
                raise ModError('duplicate recovery target')
            seen.add(rel.casefold())
            data = self._object(row['before']) if row['before'] is not None else None
            if row['after'] is not None:
                hex_hash(row['after'])
            if digest(read_file(self.path(rel))) not in (row['before'], row['after']):
                raise ModError('external edit prevents recovery: ' + rel, 'external_change')
            undo.append((rel, data))
        for rel, data in reversed(undo):
            self._put(rel, data)
        self.path(JOURNAL).unlink()
        return True

    def recover(self):
        with self.locked():
            self._closed()
            return self._recover()

    def _put(self, rel, data):
        path = self.path(rel)
        if data is None:
            path.unlink(missing_ok=True)
        else:
            atomic(path, data)

    def _commit(self, changes, state, expected):
        # Back up EVERY target and the registry before changing any of them. The journal remains until all succeed.
        changes = dict(changes)
        changes[REGISTRY] = json_bytes(state)
        undo = [{'path': rel, 'before': self._save(read_file(self.path(rel))), 'after': digest(data)}
                for rel, data in changes.items()]
        for row in undo:
            if row['path'] in expected and row['before'] != expected[row['path']]:
                raise ModError('file changed before commit: ' + row['path'], 'external_change')
        atomic(self.path(JOURNAL), json_bytes({'schema_version': 1, 'undo': undo}))
        try:
            for row in undo:
                if digest(read_file(self.path(row['path']))) != row['before']:
                    raise ModError('file changed during installation: ' + row['path'], 'external_change')
                self._put(row['path'], changes[row['path']])
            self.path(JOURNAL).unlink()
        except Exception:
            self._recover()
            raise

    def list(self):
        with self.locked():
            if self.path(JOURNAL).exists():
                raise ModError('interrupted operation: run mods recover first', 'recovery_required')
            return copy.deepcopy(self._state()['mods'])

    def _dependencies(self, metadata, state):
        installed = {m['metadata']['id']: m['metadata'] for m in state['mods']}
        if metadata['id'] in installed:
            raise ModError('mod is already installed; remove it before installing another version', 'already_installed')
        for dep in metadata['requires']:
            found = installed.get(dep['id'])
            if found is None or not matches(found['version'], dep['version']):
                raise ModError('missing dependency: %s %s' % (dep['id'], dep['version']), 'missing_dependency')
        for other in installed.values():
            for a, b in ((metadata, other), (other, metadata)):
                if any(c['id'] == b['id'] and matches(b['version'], c['version']) for c in a['conflicts']):
                    raise ModError('declared conflict with ' + other['id'], 'declared_conflict')

    def _prepare(self, source, state):
        owners = {f['path'].casefold(): m['metadata']['id'] for m in state['mods'] for f in m['files']}
        changes, records, total = {}, [], 0
        with Package(source) as package:
            meta = package.metadata
            self._dependencies(meta, state)

            def add(rel, data, previous):
                nonlocal total
                rel = game_path(rel)
                key = rel.casefold()
                if key in owners or any(p.casefold() == key for p in changes):
                    raise ModError('file conflict: %s (%s)' % (rel, owners.get(key, 'this package')), 'file_conflict')
                total += len(data)
                if total > MAX_TOTAL:
                    raise ModError('installation exceeds size limit')
                changes[rel] = data
                records.append({'path': rel, 'before': digest(previous), 'after': digest(data)})

            for patch in meta['patches']:
                manifest = patch['manifest']
                folder = manifest.rsplit('/', 1)[0] + '/' if '/' in manifest else ''
                for row in rows(package.read(manifest)):
                    if len(row) != 4:
                        raise ModError('invalid patch manifest')
                    rel, stem, before, after = row
                    rel = game_path(rel)
                    hex_hash(before, 32); hex_hash(after, 32)
                    previous = read_file(self.path(rel))
                    if previous is None:
                        raise ModError('missing game archive: ' + rel, 'game_file_missing')
                    data = merge(previous, parts(package, folder, stem))
                    if hashlib.md5(previous).hexdigest() == before and hashlib.md5(data).hexdigest() != after:
                        raise ModError('patched archive does not match manifest: ' + rel)
                    add(rel, data, previous)
            for row in meta['files']:
                add(row['target'], package.read(row['source']), read_file(self.path(row['target'])))
            if not records:
                raise ModError('empty mod')
        return meta, changes, records

    def _ticket(self, meta, records, action='install'):
        return digest(json_bytes({'game': os.path.normcase(str(self.game)), 'action': action,
                                  'metadata': meta, 'files': records}))

    def preview(self, source):
        """Validate and describe the exact planned changes without modifying game files or storing backups."""
        with self.locked():
            if self.path(JOURNAL).exists():
                raise ModError('interrupted operation: run mods recover first', 'recovery_required')
            meta, changes, records = self._prepare(source, self._state())
            return {'metadata': meta, 'files': records, 'bytes': sum(map(len, changes.values())),
                    'ticket': self._ticket(meta, records)}

    def install(self, source, expected=None):
        with self.locked():
            self._closed()
            self._recover()
            state = self._state()
            meta, changes, records = self._prepare(source, state)
            if expected is not None and expected != self._ticket(meta, records):
                raise ModError('package or game changed since preview; review the package again', 'plan_changed')
            state['mods'].append({'metadata': meta, 'files': records})
            self._commit(changes, state, {r['path']: r['before'] for r in records})
            return meta

    def _prepare_remove(self, mid, state):
        identifier(mid)
        mod = next((m for m in state['mods'] if m['metadata']['id'] == mid), None)
        if mod is None:
            raise ModError('mod is not installed: ' + mid, 'not_installed')
        for other in state['mods']:
            if any(d['id'] == mid for d in other['metadata']['requires']):
                raise ModError('remove dependent mod first: ' + other['metadata']['id'], 'dependent_installed')
        changes = {}
        for row in mod['files']:
            if digest(read_file(self.path(row['path']))) != row['after']:
                raise ModError('file changed outside the manager; kept untouched: ' + row['path'], 'external_change')
            changes[row['path']] = self._object(row['before']) if row['before'] is not None else None
        return mod, changes

    def preview_remove(self, mid):
        with self.locked():
            if self.path(JOURNAL).exists():
                raise ModError('interrupted operation: run mods recover first', 'recovery_required')
            mod, changes = self._prepare_remove(mid, self._state())
            return {'metadata': mod['metadata'],
                    'files': [{'path': r['path'], 'before': r['after'], 'after': r['before']} for r in mod['files']],
                    'bytes': sum(len(data) for data in changes.values() if data is not None),
                    'ticket': self._ticket(mod['metadata'], mod['files'], 'remove')}

    def verify(self, mid):
        """Check installed content and its backups without fixing or recovering anything."""
        identifier(mid)
        with self.locked():
            if self.path(JOURNAL).exists():
                raise ModError('interrupted operation: run mods recover first', 'recovery_required')
            mod = next((m for m in self._state()['mods'] if m['metadata']['id'] == mid), None)
            if mod is None:
                raise ModError('mod is not installed: ' + mid, 'not_installed')
            checked = []
            for r in mod['files']:
                actual = digest(read_file(self.path(r['path'])))
                backup = None if r['before'] is None else read_file(self.path(HOME + '/objects/' + r['before']))
                backup_status = 'not_needed' if r['before'] is None else 'missing' if backup is None else (
                    'ok' if digest(backup) == r['before'] else 'damaged')
                checked.append(dict(r, actual=actual,
                    status='ok' if actual == r['after'] else 'missing' if actual is None else 'modified',
                    backup_status=backup_status))
            return {'metadata': mod['metadata'], 'files': checked,
                    'valid': all(r['status'] == 'ok' and r['backup_status'] in ('ok', 'not_needed') for r in checked)}

    def remove(self, mid, expected=None):
        identifier(mid)
        with self.locked():
            self._closed()
            self._recover()
            state = self._state()
            mod, changes = self._prepare_remove(mid, state)
            if expected is not None and expected != self._ticket(mod['metadata'], mod['files'], 'remove'):
                raise ModError('installed mod changed since preview; review the removal again', 'plan_changed')
            state['mods'].remove(mod)
            self._commit(changes, state, {r['path']: r['after'] for r in mod['files']})
            return mod['metadata']
