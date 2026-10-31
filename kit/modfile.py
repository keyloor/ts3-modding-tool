"""Versioned, data-only mod packages. Never execute a package's installer or Python files."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import zipfile

MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_FILES = 20000
ID = re.compile(r'[a-z0-9][a-z0-9._-]{0,127}\Z')
RESERVED = re.compile(r'(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)', re.I)


class ModError(ValueError):
    def __init__(self, message, code='invalid_mod'):
        super().__init__(message)
        self.code = code


def relative(value):
    """A portable relative path, including Windows device/ADS restrictions on every host."""
    if not isinstance(value, str) or not value:
        raise ModError('empty or invalid path')
    value = value.replace('\\', '/')
    parts = value.split('/')
    if any(p in ('', '.', '..') or p[-1:] in (' ', '.') or RESERVED.match(p)
           or any(ord(c) < 32 or c in ':<>"|?*' for c in p) for p in parts):
        raise ModError('unsafe path: %r' % value)
    return '/'.join(parts)


def game_path(value):
    value = relative(value)
    if value.split('/')[0].lower() not in ('assets', 'data_dx') or '/' not in value:
        raise ModError('mod targets must be inside assets/ or data_dx/: ' + value)
    return value


def inside(root, rel):
    """Reject links/junctions as well as lexical traversal before reading or writing."""
    root = Path(root).resolve()
    target = root.joinpath(*relative(rel).split('/'))
    for p in (target, *target.parents):
        if p == root:
            break
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ModError('links and junctions are not allowed: ' + str(p))
    if not target.resolve().is_relative_to(root):
        raise ModError('path leaves its folder: ' + rel)
    return target


def version(value):
    """v1 accepts numeric releases only; legacy 1 and 1.0 normalize to 1.0.0."""
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){0,2}', value):
        raise ModError('expected a numeric version such as 1.0.0: %r' % value)
    return '.'.join(value.split('.') + ['0'] * (3 - len(value.split('.'))))


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ModError('invalid mod id: %r' % value)
    return value


def matches(actual, requirement):
    if requirement == '*':
        return True
    op = '>=' if requirement.startswith('>=') else '=='
    wanted = requirement[2:] if requirement.startswith(('>=', '==')) else requirement
    a, b = tuple(map(int, version(actual).split('.'))), tuple(map(int, version(wanted).split('.')))
    return a >= b if op == '>=' else a == b


def validate(data):
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ModError('unsupported mod.json schema_version (expected 1)')
    d = copy.deepcopy(data)
    identifier(d.get('id'))
    for key in ('name', 'author', 'description'):
        if not isinstance(d.get(key), str) or (key == 'name' and not d[key].strip()):
            raise ModError('invalid mod field: ' + key)
    d['version'] = version(d.get('version'))
    if d.get('game') != 'ts3-pc':
        raise ModError('this package is not for ts3-pc')
    for key in ('requires', 'conflicts'):
        rows = d.setdefault(key, [])
        if not isinstance(rows, list):
            raise ModError(key + ' must be a list')
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ModError('invalid ' + key + ' entry')
            mid = identifier(row.get('id'))
            if mid == d['id'] or mid in seen:
                raise ModError('duplicate or self dependency/conflict: ' + mid)
            seen.add(mid)
            req = row.setdefault('version', '*')
            if not isinstance(req, str):
                raise ModError('dependency version must be a string')
            matches('0.0.0', req)   # validate syntax even when the dependency is absent
    if 'update' in d:
        up = d['update']
        if not isinstance(up, dict) or not isinstance(up.get('github'), str) or not re.fullmatch(
                r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', up['github']):
            raise ModError('update.github must be owner/repository')
    if not isinstance(d.setdefault('credits', []), list) or any(not isinstance(c, str) for c in d['credits']):
        raise ModError('credits must be a list of strings')
    patches, files = d.setdefault('patches', []), d.setdefault('files', [])
    if not isinstance(patches, list) or not isinstance(files, list) or not (patches or files):
        raise ModError('a mod must contain patches and/or files lists')
    for row in patches:
        if not isinstance(row, dict) or set(row) != {'manifest'}:
            raise ModError('each patches entry must contain manifest')
        row['manifest'] = relative(row['manifest'])
    seen = set()
    for row in files:
        if not isinstance(row, dict) or set(row) != {'source', 'target'}:
            raise ModError('each files entry must contain source and target')
        row['source'], row['target'] = relative(row['source']), game_path(row['target'])
        if row['target'].casefold() in seen:
            raise ModError('duplicate file target: ' + row['target'])
        seen.add(row['target'].casefold())
    return d


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


class Package:
    """Folder or ZIP with one unambiguous package root; read lazily, with bounded sizes."""
    def __init__(self, source):
        self.source = Path(source).resolve()
        self.zip = None
        self.entries = {}
        self.used = 0
        try:
            if self.source.is_dir():
                for base, dirs, files in os.walk(self.source, followlinks=False):
                    for name in dirs + files:
                        p = Path(base) / name
                        inside(self.source, p.relative_to(self.source).as_posix())
                    for name in files:
                        p = Path(base) / name
                        self._add(p.relative_to(self.source).as_posix(), p, p.stat().st_size)
            else:
                self.zip = zipfile.ZipFile(self.source)
                for info in self.zip.infolist():
                    relative(info.filename.rstrip('/'))
                    if stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
                        raise ModError('encrypted entries and links are not supported')
                    if not info.is_dir():
                        self._add(info.filename, info, info.file_size)
            self.prefix = self._root()
            manifests = [k for k in self.entries if k.endswith('/mod.json') or k == 'mod.json']
            key = self.prefix + 'mod.json'
            if key in self.entries:
                self.metadata = validate(json.loads(self.read('mod.json').decode('utf-8-sig')))
            elif manifests:
                raise ModError('ambiguous package: multiple mod.json files')
            else:
                self.metadata = self._legacy()
        except BaseException:
            self.close()
            raise

    def _add(self, name, ref, size):
        name = relative(name)
        key = name.casefold()
        if key in self.entries or size > MAX_FILE or size < 0:
            raise ModError('duplicate or oversized package entry: ' + name)
        self.used += size
        if self.used > MAX_TOTAL or len(self.entries) >= MAX_FILES:
            raise ModError('package exceeds size or file-count limit')
        self.entries[key] = (name, ref)

    def _root(self):
        roots = [k[:-len('mod.json')] for k in self.entries if k == 'mod.json' or k.endswith('/mod.json')]
        if not roots:
            roots = [k[:-len('patches/manifest.txt')] for k in self.entries
                     if k == 'patches/manifest.txt' or k.endswith('/patches/manifest.txt')]
        if roots:
            if len(roots) != 1:
                raise ModError('package must have exactly one root')
            return roots[0]
        roots = set()
        for key in self.entries:
            parts = key.split('/')
            for i, part in enumerate(parts[:-1]):
                if part in ('assets', 'data_dx'):
                    roots.add('/'.join(parts[:i]) + ('/' if i else ''))
                    break
        if len(roots) != 1:
            raise ModError('no unambiguous mod.json, patches/manifest.txt or game folder layout')
        return roots.pop()

    def read(self, rel):
        key = self.prefix + relative(rel).casefold()
        if key not in self.entries:
            raise ModError('missing package file: ' + rel)
        name, ref = self.entries[key]
        if self.zip:
            with self.zip.open(ref) as f:
                data = f.read(MAX_FILE + 1)
        else:
            with inside(self.source, name).open('rb') as f:
                data = f.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise ModError('package file too large: ' + rel)
        return data

    def _legacy(self):
        patches, files = [], []
        if self.prefix + 'patches/manifest.txt' in self.entries:
            patches = [{'manifest': 'patches/manifest.txt'}]
        else:
            for key, (name, _) in self.entries.items():
                if key.startswith(self.prefix):
                    rel = name[len(self.prefix):]
                    if rel.split('/')[0].lower() in ('assets', 'data_dx'):
                        files.append({'source': rel, 'target': game_path(rel)})
        # Content identity for old packs, not their download filename. Explicit mod.json provides stable update IDs.
        h = hashlib.sha256()
        for key in sorted(self.entries):
            if key.startswith(self.prefix):
                rel = key[len(self.prefix):]
                if rel.startswith(('patches/', 'assets/', 'data_dx/')):
                    h.update(rel.encode('utf-8') + b'\0')
                    h.update(hashlib.sha256(self.read(rel)).digest())
        name, ver = self._legacy_label()
        return validate({'schema_version': 1, 'id': 'legacy.' + h.hexdigest()[:24],
                         'name': name, 'version': ver, 'author': '', 'description': '',
                         'game': 'ts3-pc', 'patches': patches, 'files': files})

    def _legacy_label(self):
        """an old pack's name and version, read as text (never run): its installer's $Name / $Version, else the
        README's first line ('Restored Songs for Toy Story 3      version 1.1'), else the file name ('... v1.1')"""
        name, ver = None, None
        for key, (fname, _) in sorted(self.entries.items()):
            rel = key[len(self.prefix):] if key.startswith(self.prefix) else None
            if rel is None or '/' in rel or not rel.endswith(('.ps1', '.txt')):
                continue
            try:
                text = self.read(rel)[:65536].decode('utf-8-sig', 'replace')
            except ModError:
                continue
            if rel.endswith('.ps1'):
                m = re.search(r"^\$Name\s*=\s*'([^']+)'", text, re.M)
                v = re.search(r"^\$Version\s*=\s*'([^']+)'", text, re.M)
                name, ver = (m.group(1) if m else name), (v.group(1) if v else ver)
            elif rel.startswith('readme'):
                first = next((ln.strip() for ln in text.splitlines() if ln.strip()), '')
                m = re.match(r'(.+?)\s{2,}v(?:ersion)?\s*(\d+(?:\.\d+){0,2})\b', first, re.I)
                if m:
                    name, ver = name or m.group(1), ver or m.group(2)
        stem = self.source.name if self.source.is_dir() else self.source.stem   # a folder "x v1.2" has no suffix
        m = re.match(r'(.+?)[\s_-]+v?(\d+(?:\.\d+){1,2})$', stem)
        if m:
            stem, ver = m.group(1), ver or m.group(2)
        try:
            ver = version(ver) if ver else '0.0.0'
        except ModError:
            ver = '0.0.0'
        return (name or stem).strip()[:120] or stem, ver

    def close(self):
        if self.zip:
            self.zip.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
