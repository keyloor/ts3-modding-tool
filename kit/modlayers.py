"""Ordered mod layers. Whole-file snapshots or ZIP member deltas against one saved baseline.

Registry v2 retains each layer's standalone output by SHA-256. Composition never needs
the downloaded packages again. Preview is pure; Store persists objects only after review.
"""
import copy
import hashlib
import os
import struct

import modstore as M
from modfile import ModError, Package, MAX_FILE, MAX_TOTAL, MAX_FILES, game_path, identifier, json_bytes, validate


def targets(state):
    return {r['path'].casefold(): r for m in state['mods'] for r in m['files']}


def validate_state(state):
    ids, paths = set(), {}
    try:
        for mod in state['mods']:
            meta = validate(mod['metadata'])
            if meta['id'] in ids or not isinstance(mod['files'], list) or not 1 <= len(mod['files']) <= MAX_FILES:
                raise ValueError('Invalid installed layer.')
            ids.add(meta['id']); seen = set()
            for row in mod['files']:
                path = game_path(row['path']); key = path.casefold()
                if key in seen or row['kind'] not in ('file', 'archive'): raise ValueError('Duplicate/invalid layer target.')
                seen.add(key); M.hex_hash(row['payload']); M.hex_hash(row['after'])
                if row['before'] is not None: M.hex_hash(row['before'])
                common = (path, row['before'], row['after'])
                if key in paths and paths[key] != common: raise ValueError('Inconsistent shared target records.')
                paths[key] = common
    except (KeyError, TypeError, ValueError) as e:
        raise ModError('Invalid layered registry; preserve backups: '+str(e), 'invalid_registry') from e
    return state


def shared(state):
    result = {}
    for mod in state['mods']:
        for row in mod['files']:
            item = result.setdefault(row['path'].casefold(), dict(path=row['path'], mods=[], kinds=[]))
            item['mods'].append(mod['metadata']['id']); item['kinds'].append(row.get('kind', 'file'))
    return [dict(path=r['path'], mods=r['mods'], rule='archive_members' if set(r['kinds']) == {'archive'} else 'whole_file_and_members')
            for r in result.values() if len(r['mods']) > 1]


def archive_entries(data):
    try:
        rows = M.archive.read_zip(data)
        by = {e['name'].decode('latin1').casefold(): e for e in rows}
        if len(by) != len(rows): raise ValueError('Duplicate archive members.')
        if sum(e['usize'] for e in rows) > MAX_TOTAL: raise ValueError('Archive exceeds unpacked size limit.')
        for e in rows:
            if e['method'] not in (0, 8) or e['usize'] > MAX_FILE: raise ValueError('Unsupported archive member.')
            # Ordinary whole-ZIP packages may lack the game's KF/MD5 extension. Compute it with bounds
            # before write_zip can use its older unbounded unpack helper.
            if e['md5'] is None:
                if e['method'] == 8:
                    decoder = M.zlib.decompressobj(-15); raw = decoder.decompress(e['data'], e['usize']+1)
                    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail: raise ValueError('Invalid compressed member.')
                else: raw = e['data']
                if len(raw) != e['usize'] or (e['crc'] and M.zlib.crc32(raw) != e['crc']): raise ValueError('Invalid archive member checksum.')
                e['md5'] = hashlib.md5(raw).digest()
        return rows, by
    except (AssertionError, ValueError, TypeError, IndexError, struct.error, M.zlib.error) as e:
        raise ModError('Cannot compose this archive layer: '+str(e), 'unsupported_layer') from e


def delta(base, payload):
    """Keep original packed entries and spelling; reject deletions and duplicate aliases."""
    _, original = archive_entries(base)
    rows, after = archive_entries(payload)
    if original.keys() - after.keys():
        raise ModError('A layered archive patch cannot delete original members.', 'unsupported_layer')
    return [e for e in rows if original.get(e['name'].decode('latin1').casefold()) != e]


def overlay(current, entries):
    rows, _ = archive_entries(current)
    by = {e['name'].decode('latin1').casefold(): i for i, e in enumerate(rows)}
    if len(by) != len(rows): raise ModError('Duplicate archive members.', 'invalid_data')
    for entry in entries:
        key = entry['name'].decode('latin1').casefold()
        if key in by: rows[by[key]] = dict(entry, name=rows[by[key]]['name'])
        else: by[key] = len(rows); rows.append(entry)
    data = M.archive.write_zip(rows)
    if M.archive.read_zip(data) != rows: raise ModError('Layered archive verification failed.', 'invalid_data')
    return data


class Preparation:
    def __init__(self, store, original):
        self.store, self.original = store, original
        self.state = copy.deepcopy(original)
        self.objects, self.total = {}, 0
        self.registry_hash = M.digest(M.read_file(store.path(M.REGISTRY)))
        # Migration changes only the eventual registry. Never write or save during preview.
        if original['schema_version'] == 1:
            for mod in self.state['mods']:
                full = {r['target'].casefold() for r in mod['metadata']['files']}
                for row in mod['files']:
                    data = M.read_file(store.path(row['path']))
                    if M.digest(data) != row['after']:
                        raise ModError('File changed outside the manager: '+row['path'], 'external_change')
                    if row['before'] is not None: self.get(row['before'])
                    row['kind'] = 'archive' if mod['metadata']['patches'] and row['path'].casefold() not in full else 'file'
                    row['payload'] = self.remember(data)
                    if row['kind'] == 'archive': delta(self.get(row['before']), data)
            self.state['schema_version'] = 2
        self.bases = targets(self.state)

    def remember(self, data):
        key = M.digest(data)
        if key is not None and key not in self.objects:
            self.total += len(data)
            if self.total > MAX_TOTAL: raise ModError('Layer preparation exceeds 2 GiB.', 'size_limit')
            self.objects[key] = data
        return key

    def get(self, key):
        return None if key is None else self.objects[key] if key in self.objects else self.store._object(key)

    def baseline(self, rel):
        known = self.bases.get(rel.casefold())
        if known: return known['path'], self.get(known['before'])
        return rel, M.read_file(self.store.path(rel))

    def package(self, source, replace=False, layer=False):
        with Package(source) as package:
            meta = package.metadata
            old = next((m for m in self.state['mods'] if m['metadata']['id'] == meta['id']), None) if replace else None
            others = {'mods': [m for m in self.state['mods'] if m is not old]}
            self.store._dependencies(meta, others)
            for mod in others['mods']:
                if any(d['id'] == meta['id'] and not M.matches(meta['version'], d['version']) for d in mod['metadata']['requires']):
                    raise ModError('Replacement would break dependent mod: '+mod['metadata']['id'], 'dependent_version')
            owners = targets(others); retained = {r['path'].casefold() for r in old['files']} if old else set()
            records, seen = [], set()
            def add(rel, base, data, kind):
                rel = game_path(rel); key = rel.casefold()
                if key in seen: raise ModError('Duplicate layer target: '+rel, 'file_conflict')
                if key in owners and not layer and key not in retained:
                    raise ModError('File conflict: '+rel+'; review installation with --layer.', 'file_conflict')
                seen.add(key)
                records.append(dict(path=rel, before=self.remember(base), after=M.digest(data),
                                    payload=self.remember(data), kind=kind))
            for patch in meta['patches']:
                manifest = patch['manifest']; folder = manifest.rsplit('/', 1)[0]+'/' if '/' in manifest else ''
                for row in M.rows(package.read(manifest)):
                    if len(row) != 4: raise ModError('Invalid patch manifest.')
                    rel, stem, before, after = row
                    rel, base = self.baseline(game_path(rel))
                    M.hex_hash(before, 32); M.hex_hash(after, 32)
                    if base is None: raise ModError('Missing game archive: '+rel, 'game_file_missing')
                    data = M.merge(base, M.parts(package, folder, stem))
                    if hashlib.md5(base).hexdigest() == before and hashlib.md5(data).hexdigest() != after:
                        raise ModError('Patched archive does not match manifest: '+rel)
                    add(rel, base, data, 'archive')
            for row in meta['files']:
                rel, base = self.baseline(game_path(row['target']))
                add(rel, base, package.read(row['source']), 'file')
            if not records: raise ModError('Empty mod.')
        record = dict(metadata=meta, files=records)
        if old: self.state['mods'][self.state['mods'].index(old)] = record
        else: self.state['mods'].append(record)
        affected = {r['path'].casefold() for r in records+(old['files'] if old else [])}
        plan = self.finish(affected, 'replace' if old else 'install', meta)
        if old:
            plan['replaces'] = old['metadata']
            plan['restores'] = [r['path'] for r in old['files'] if r['path'].casefold() not in seen]
        return plan

    def remove(self, mid):
        identifier(mid)
        mod = next((m for m in self.state['mods'] if m['metadata']['id'] == mid), None)
        if mod is None: raise ModError('Mod is not installed: '+mid, 'not_installed')
        for other in self.state['mods']:
            if any(d['id'] == mid for d in other['metadata']['requires']):
                raise ModError('Remove dependent mod first: '+other['metadata']['id'], 'dependent_installed')
        self.state['mods'].remove(mod)
        return self.finish({r['path'].casefold() for r in mod['files']}, 'remove', mod['metadata'])

    def order(self, ids):
        existing = {m['metadata']['id']: m for m in self.state['mods']}
        if (not isinstance(ids, (list, tuple)) or any(not isinstance(mid, str) for mid in ids)
                or len(ids) != len(existing) or len(set(ids)) != len(ids) or set(ids) != set(existing)):
            raise ModError('Supply every installed mod ID once, from lowest to highest priority.', 'invalid_arguments')
        self.state['mods'] = [existing[mid] for mid in ids]
        return self.finish(set(targets(self.state)), 'order')

    def finish(self, affected, action, meta=None):
        original, final = targets(self.original), targets(self.state)
        grouped = {}
        for mod in self.state['mods']:
            for item in mod['files']: grouped.setdefault(item['path'].casefold(), []).append(item)
        changes, transitions, total = {}, [], 0
        for key in sorted(affected):
            old, new = original.get(key), final.get(key)
            row = old or new; rel = row['path']
            current = M.read_file(self.store.path(rel)); before = M.digest(current)
            if before != (old['after'] if old else row['before']):
                raise ModError('File changed outside the manager; kept untouched: '+rel, 'external_change')
            base = self.get(row['before']); result = base
            for item in grouped.get(key, []):
                payload = self.get(item['payload'])
                result = payload if item['kind'] == 'file' else overlay(result, delta(base, payload))
            total += len(result) if result is not None else 0
            if total > MAX_TOTAL: raise ModError('Layer rebuild exceeds 2 GiB.', 'size_limit')
            after = M.digest(result)
            for item in grouped.get(key, []): item.update(path=rel, before=row['before'], after=after)
            changes[rel] = result
            transitions.append(dict(path=rel, before=before, after=after))
        validate_state(self.state)
        self.changes = changes
        self.expected = {r['path']: r['before'] for r in transitions}
        self.expected[M.REGISTRY] = self.registry_hash
        ticket = M.digest(json_bytes(dict(game=os.path.normcase(str(self.store.game)), action=action, before=self.original,
                                         after=self.state, files=transitions)))
        return dict(metadata=meta, files=transitions, bytes=total, ticket=ticket, layered=True,
                    order=[m['metadata']['id'] for m in self.state['mods']], shared=shared(self.state))

    def commit(self, plan, expected):
        if expected is not None and expected != plan['ticket']:
            raise ModError('Package, game or priority order changed since preview; review again.', 'plan_changed')
        for data in self.objects.values(): self.store._save(data)
        self.store._commit(self.changes, self.state, self.expected)


def verify(store, state, mid):
    mod = next((m for m in state['mods'] if m['metadata']['id'] == mid), None)
    if mod is None: raise ModError('Mod is not installed: '+mid, 'not_installed')
    checked = []
    grouped = {}
    for m in state['mods']:
        for r in m['files']: grouped.setdefault(r['path'].casefold(), []).append((m['metadata']['id'], r['payload']))
    def status(key):
        if key is None: return 'not_needed'
        raw = M.read_file(store.path(M.HOME+'/objects/'+key))
        return 'missing' if raw is None else 'ok' if M.digest(raw) == key else 'damaged'
    for row in mod['files']:
        actual = M.digest(M.read_file(store.path(row['path'])))
        layers = [dict(id=mid, status=status(payload)) for mid, payload in grouped[row['path'].casefold()]]
        checked.append(dict(row, actual=actual, status='ok' if actual == row['after'] else 'missing' if actual is None else 'modified',
                            backup_status=status(row['before']), layers=layers))
    return dict(metadata=mod['metadata'], files=checked,
                valid=all(r['status'] == 'ok' and r['backup_status'] in ('ok', 'not_needed')
                          and all(l['status'] == 'ok' for l in r['layers']) for r in checked))
