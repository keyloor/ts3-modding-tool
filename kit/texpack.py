"""PNG texture workspaces and data-only mod packs. Never modifies the game.

The workspace records the source archive and original PNG hashes. Only changed PNGs
are encoded into OCT replacements. Packs use the existing manager/backup workflow.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
import zlib

from PIL import Image
import paths
from about import CREDIT
from ddsedit import layout, replace
from explorer import Browser, directory, signature, textures
from modfile import ModError, MAX_TOTAL, game_path, inside, json_bytes, relative, validate
from octlib import Oct
import install

MAX_TEXTURES = 20000
MAX_PNG = 64 * 1024 * 1024
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_ARCHIVES = 256


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprints(source):
    digest, md5 = hashlib.sha256(), hashlib.md5()
    with source.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk); md5.update(chunk)
    return digest.hexdigest(), md5.hexdigest()


def output_folder(game, output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ModError('Choose a new output folder: ' + str(output), 'destination_exists')
    if output.resolve().is_relative_to(Path(game).resolve()):
        raise ModError('Choose an output folder outside the game.', 'invalid_path')
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def publish(stage, output):
    if output.exists() or output.is_symlink():
        raise ModError('The output folder already exists.', 'destination_exists')
    stage.rename(output)


def archive_paths(archives):
    values = [archives] if isinstance(archives, str) else archives
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= MAX_ARCHIVES:
        raise ModError('Choose between 1 and 256 game ZIP archives.', 'invalid_arguments')
    result = [game_path(value) for value in values]
    if any(not value.lower().endswith('.zip') for value in result):
        raise ModError('Choose game ZIP archives.', 'unsupported_format')
    if len({value.casefold() for value in result}) != len(result):
        raise ModError('Do not select the same archive twice.', 'invalid_arguments')
    return result


def dump(game, archive, output, member=None, *, shared=False):
    """Export one or more archives; shared mode groups only byte-identical DDS textures."""
    browser = Browser(game)
    archives = archive_paths(archive)
    if member is not None and len(archives) != 1:
        raise ModError('--member requires exactly one archive.', 'invalid_arguments')
    member = relative(member) if member is not None else None
    output = output_folder(browser.game, output)
    rows, errors, sources, snapshots, pngs, shared_rows = [], [], [], {}, set(), {}
    modern = len(archives) > 1 or shared
    with tempfile.TemporaryDirectory(prefix='.ts3-textures-', dir=output.parent) as temp:
        stage = Path(temp) / 'workspace'; stage.mkdir()
        for path in archives:
            source = browser.source(path)
            snapshots[path] = signature(source)
            digest, md5 = fingerprints(source)
            sources.append(dict(path=path, sha256=digest, md5=md5))
            members = [e['member'] for e in directory(source) if e['member'].lower().endswith('.oct')
                       and (member is None or e['member'] == member)]
            if not members:
                raise ModError('No matching OCT files in: ' + path, 'not_found')
            for name in members:
                data = browser.read(path, name)
                f = Oct.parse(data)
                oct_hash = sha(data)
                for info, raw in textures(f):
                    if len(rows) >= MAX_TEXTURES:
                        raise ModError('Texture workspace exceeds 20000 entries.', 'size_limit')
                    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', info['name'])[:80] or 'texture'
                    dds_hash = sha(raw)
                    if shared and dds_hash in shared_rows:
                        rows.append(dict(shared_rows[dds_hash], archive=path, member=name,
                                         texture=info['index'], name=info['name'], oct_sha256=oct_hash))
                        continue
                    png = ('shared/%08x_%s.png' % (zlib.crc32(raw), dds_hash)) if shared else (
                        path + '/' + name + '/%04d_%s.png' % (info['index'], safe))
                    png = relative(png)
                    try:
                        with Image.open(io.BytesIO(raw)) as image:
                            if image.width * image.height > 8192 * 8192:
                                raise ModError('Texture is too large.', 'size_limit')
                            image = image.convert('RGBA')
                            buf = io.BytesIO(); image.save(buf, 'PNG')
                        payload = buf.getvalue()
                        meta = dict(format='unsupported', editable=False)
                        try:
                            details = layout(raw)
                            meta.update(format=details['format'], mipmaps=details['mipmaps'], editable=True)
                        except ModError:
                            pass
                        if png not in pngs:
                            target = inside(stage, png); target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(payload); pngs.add(png)
                        row = dict(member=name, texture=info['index'], name=info['name'], png=png,
                                   png_sha256=sha(payload), dds_sha256=dds_hash, oct_sha256=oct_hash,
                                   width=image.width, height=image.height, **meta)
                        if modern:
                            row['archive'] = path
                        rows.append(row)
                        if shared:
                            shared_rows[dds_hash] = row
                    except (OSError, ValueError) as e:
                        errors.append(dict(archive=path, member=name, texture=info['index'], message=str(e)))
        if not rows:
            raise ModError('No readable textures found.', 'unsupported_format')
        for path, before in snapshots.items():
            if signature(browser.source(path)) != before:
                raise ModError('Archive changed during texture export. Retry: ' + path, 'source_changed')
        manifest = dict(schema_version=2 if modern else 1, game='ts3-pc', workspace_id=uuid.uuid4().hex,
                        textures=rows, errors=errors)
        if modern:
            manifest.update(archives=sources, mode='shared' if shared else 'separate')
        else:
            manifest.update(archive=archives[0], archive_sha256=sources[0]['sha256'], archive_md5=sources[0]['md5'])
        (stage / 'index.json').write_bytes(json_bytes(manifest))
        (stage / 'README.txt').write_text(
            CREDIT + '\n\nEdit PNGs at their original size. Delete PNGs you do not want to replace.\n'
            'Shared mode: each PNG replaces ALL identical DDS occurrences in index.json, only in selected archives.\n'
            'Shared filenames use CRC32 plus full SHA-256; CRC collisions never group different DDS files.\n'
            'Then use Textures > Build texture pack, or: textures build WORKSPACE --out NEW_FOLDER ...\n'
            'Only changed PNGs go into the pack. These are game textures; keep the workspace local.\n', encoding='utf-8')
        publish(stage, output)
    return dict(output=str(output), archives=len(archives), textures=len(rows), png_files=len(pngs),
                shared=shared, editable=sum(r['editable'] for r in rows), errors=errors)


def workspace(folder):
    """Validate v1/v2 and normalize their sources in memory; never rewrite an existing workspace."""
    folder = Path(folder).resolve()
    index = inside(folder, 'index.json')
    if index.stat().st_size > 32 * 1024 * 1024:
        raise ModError('Texture index is too large.', 'size_limit')
    data = json.loads(index.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or type(data.get('schema_version')) is not int
            or data['schema_version'] not in (1, 2) or data.get('game') != 'ts3-pc'):
        raise ModError('Unsupported texture workspace.', 'invalid_data')
    if data['schema_version'] == 1:
        data['archives'] = [dict(path=data.get('archive'), sha256=data.get('archive_sha256'), md5=data.get('archive_md5'))]
        data['mode'] = 'separate'
    sources = data.get('archives')
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_ARCHIVES or any(not isinstance(s, dict) for s in sources):
        raise ModError('Invalid workspace archives.', 'invalid_data')
    archives = archive_paths([s.get('path') for s in sources])
    by_path = {s['path']: s for s in sources}
    for source in sources:
        for field, length in (('sha256', 64), ('md5', 32)):
            if not isinstance(source.get(field), str) or not re.fullmatch('[a-f0-9]{%d}' % length, source[field]):
                raise ModError('Invalid source checksum.', 'invalid_data')
    if data.get('mode') not in ('separate', 'shared'):
        raise ModError('Invalid texture editing mode.', 'invalid_data')
    rows = data.get('textures')
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_TEXTURES:
        raise ModError('Invalid texture list.', 'invalid_data')
    seen, pngs = set(), {}
    for row in rows:
        if not isinstance(row, dict) or type(row.get('texture')) is not int or row['texture'] < 0:
            raise ModError('Invalid texture entry.', 'invalid_data')
        if data['schema_version'] == 1:
            row['archive'] = archives[0]
        if not isinstance(row.get('archive'), str) or row['archive'] not in by_path:
            raise ModError('Texture references an unknown archive.', 'invalid_data')
        key = (row['archive'].casefold(), relative(row.get('member')).casefold(), row['texture'])
        png = relative(row.get('png'))
        if not png.lower().endswith('.png') or key in seen:
            raise ModError('Duplicate or invalid texture paths.', 'invalid_data')
        seen.add(key)
        for field in ('png_sha256', 'dds_sha256', 'oct_sha256'):
            if not isinstance(row.get(field), str) or not re.fullmatch('[a-f0-9]{64}', row[field]):
                raise ModError('Invalid workspace checksum.', 'invalid_data')
        for field in ('width', 'height'):
            if type(row.get(field)) is not int or not 1 <= row[field] <= 8192:
                raise ModError('Invalid texture dimensions.', 'invalid_data')
        identity = (png, row['dds_sha256'], row['png_sha256'], row['width'], row['height'])
        if png.casefold() in pngs and (data['mode'] != 'shared' or pngs[png.casefold()] != identity):
            raise ModError('Only identical DDS textures may share a PNG.', 'invalid_data')
        pngs[png.casefold()] = identity
    return folder, data


def patch_archive(original, replacements):
    entries = install.read_zip(original)
    by_name = {e['name'].decode('latin1').replace('\\', '/').casefold(): i for i, e in enumerate(entries)}
    if len(by_name) != len(entries):
        raise ModError('Duplicate source archive members.', 'invalid_data')
    blob, lines = bytearray(), []
    for member, raw in sorted(replacements.items()):
        if member.casefold() not in by_name:
            raise ModError('Missing source member: ' + member, 'source_changed')
        pos = by_name[member.casefold()]
        like = entries[pos]
        entry = install.entry(like['name'], raw, like)
        lines.append('put|%s|%d|%d|%d|%d|%d|%08x|%d|%s|%08x' % (
            like['name'].decode('latin1'), len(blob), len(entry['data']), entry['method'], entry['time'],
            entry['date'], entry['crc'], entry['usize'], entry['md5'].hex(), like['crc']))
        blob.extend(entry['data']); entries[pos] = entry
    return blob, lines, install.write_zip(entries)


def build(game, folder, output, *, mod_id, name, author, version='1.0.0'):
    meta = validate(dict(schema_version=1, id=mod_id, name=name, author=author, version=version,
                         description='Texture replacements for Toy Story 3.', game='ts3-pc', credits=[CREDIT],
                         patches=[{'manifest': 'patches/manifest.txt'}]))
    if any('\n' in text or '\r' in text for text in (name, author)):
        raise ModError('Use a single line for the name and author.', 'invalid_arguments')
    folder, index = workspace(folder)
    browser = Browser(game)
    sources, snapshots = {}, {}
    for source in index['archives']:
        path = source['path']; file = browser.source(path)
        snapshots[path] = signature(file)
        if file.stat().st_size > MAX_ARCHIVE:
            raise ModError('Archive exceeds the 512 MiB pack builder limit: ' + path, 'size_limit')
        if fingerprints(file)[0] != source['sha256']:
            raise ModError('The game archive changed since this workspace was exported. Export it again: ' + path, 'source_changed')
        sources[path] = source
    changed, pngs, png_bytes = {}, {}, 0
    for row in index['textures']:
        if row['png'] not in pngs:
            png = inside(folder, row['png'])
            payload = None
            if png.exists():
                if not png.is_file() or png.stat().st_size > MAX_PNG:
                    raise ModError('Invalid or oversized PNG: ' + row['png'], 'size_limit')
                data = png.read_bytes()
                if sha(data) != row['png_sha256']:
                    png_bytes += len(data)
                    if png_bytes > MAX_TOTAL:
                        raise ModError('Edited PNGs exceed the 2 GiB limit.', 'size_limit')
                    payload = data
            pngs[row['png']] = payload
        if pngs[row['png']] is not None:
            changed.setdefault((row['archive'], row['member']), []).append((row, pngs[row['png']]))
    if not changed:
        raise ModError('No changed PNGs. Edit a texture before building a pack.', 'nothing_changed')
    replacements, encoded_cache, count, total = {}, {}, 0, 0
    for (archive, member), edits in changed.items():
        raw = browser.read(archive, member)
        f = Oct.parse(raw)
        pools = f.find('TexturePool')
        if not pools:
            raise ModError('Source OCT has no TexturePool.', 'invalid_data')
        entries = f.children(pools[0])
        for row, png in edits:
            if sha(raw) != row['oct_sha256'] or row['texture'] >= len(entries):
                raise ModError('Texture index no longer matches its source.', 'source_changed')
            t = entries[row['texture']]
            data, crc = f.child(t, 'Data'), f.child(t, 'DataCRC')
            if data is None or crc is None:
                raise ModError('Texture is missing its data or checksum.', 'unsupported_format')
            original = bytes(f.recs[data].items()[1])
            if sha(original) != row['dds_sha256']:
                raise ModError('Texture checksum no longer matches its source.', 'source_changed')
            cache_key = (row['dds_sha256'], sha(png))
            if cache_key not in encoded_cache:
                with Image.open(io.BytesIO(png)) as image:
                    if image.format != 'PNG':
                        raise ModError('Expected a PNG image: ' + row['png'], 'invalid_data')
                    encoded_cache[cache_key] = replace(original, image)
            encoded = encoded_cache[cache_key]
            f.recs[data].set_items(encoded); f.recs[crc].set_items([zlib.crc32(encoded)])
            count += 1
        result = f.to_bytes()
        if Oct.parse(result).to_bytes() != result:
            raise ModError('Edited OCT failed its byte-exact roundtrip.', 'invalid_data')
        total += len(result)
        if total > MAX_TOTAL:
            raise ModError('Texture replacements exceed the 2 GiB limit.', 'size_limit')
        replacements.setdefault(archive, {})[member] = result
    output = output_folder(browser.game, output)
    if output.resolve().is_relative_to(folder):
        raise ModError('Build the pack outside the texture workspace.', 'invalid_path')
    with tempfile.TemporaryDirectory(prefix='.ts3-texpack-', dir=output.parent) as temp:
        stage = Path(temp) / 'pack'; stage.mkdir(); (stage / 'patches').mkdir()
        manifest, packed = [], 0
        for i, (archive, edits) in enumerate(sorted(replacements.items())):
            original = browser.source(archive).read_bytes()
            if sha(original) != sources[archive]['sha256']:
                raise ModError('Archive changed while building the pack: ' + archive, 'source_changed')
            blob, lines, after = patch_archive(original, edits)
            packed += len(blob)
            if packed > MAX_TOTAL:
                raise ModError('Texture pack exceeds the 2 GiB limit.', 'size_limit')
            stem = 'textures' if len(replacements) == 1 else 'textures-%04d' % (i + 1)
            (stage / ('patches/' + stem + '.bin')).write_bytes(blob)
            (stage / ('patches/' + stem + '.txt')).write_text('\n'.join(lines) + '\n', encoding='utf-8')
            manifest.append('%s|%s|%s|%s' % (archive, stem, hashlib.md5(original).hexdigest(), hashlib.md5(after).hexdigest()))
        (stage / 'mod.json').write_bytes(json_bytes(meta))
        (stage / 'patches/manifest.txt').write_text('\n'.join(manifest) + '\n', encoding='utf-8')
        (stage / 'README.txt').write_text('%s\nby %s\n\n%s\n\nDrop this folder on the Mod Loader or Modding Tool to install it.\n'
                                         'Remove it with Manage mods to restore the previous files.\n' % (name, author, CREDIT), encoding='utf-8')
        for archive, before in snapshots.items():
            if signature(browser.source(archive)) != before:
                raise ModError('Archive changed while building the pack: ' + archive, 'source_changed')
        publish(stage, output)
    return dict(output=str(output), textures=count, png_files=sum(p is not None for p in pngs.values()),
                archives=len(replacements), oct_files=len(changed), metadata=meta)
