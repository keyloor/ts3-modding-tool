"""Read-only game browser. Index ZIP directories, inspect assets, export to new folders.

No converter/installer code runs here. Cache entries are hints only: reads and exports
always reopen the source and validate its current directory, paths, sizes and CRCs.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import zipfile
import zlib

import paths
from modfile import ModError, inside, relative

MAX_FILE = 512 * 1024 * 1024
MAX_EXPORT = 2 * 1024 * 1024 * 1024
KINDS = ('archive', 'oct', 'texture', 'sound', 'mesh', 'text', 'other')


class FrontZip:
    """Some TS3 archives have only a leading EOCD/directory, not a trailing one."""
    def __init__(self, path):
        self.file = open(path, 'rb')
        try:
            size = os.fstat(self.file.fileno()).st_size
            header = self.file.read(22)
            magic, disk, cd_disk, count_disk, count, length, offset, comment = struct.unpack('<IHHHHIIH', header)
            if (magic != 0x06054B50 or disk or cd_disk or count != count_disk or offset != 22
                    or comment or length > size - 22):
                raise zipfile.BadZipFile('Not a supported front-directory ZIP')
            self.entries = []
            end = 22 + length
            for _ in range(count):
                row = self.file.read(46)
                (sig, vm, vn, flag, method, tm, dt, crc, cs, us, nl, xl, cl, d, ia, ea, off) = struct.unpack('<IHHHHHHIIIHHHHHII', row)
                if sig != 0x02014B50 or d or self.file.tell() + nl + xl + cl > end:
                    raise zipfile.BadZipFile('Damaged front directory')
                name = self.file.read(nl).decode('utf-8' if flag & 0x800 else 'latin1')
                info = zipfile.ZipInfo(name)
                info.flag_bits, info.compress_type = flag, method
                info.CRC, info.compress_size, info.file_size, info.header_offset = crc, cs, us, off
                info.extra = self.file.read(xl)
                self.file.read(cl)
                if off < end or off + 30 + cs > size:
                    raise zipfile.BadZipFile('Invalid local file offset')
                self.entries.append(info)
            if self.file.tell() != end:
                raise zipfile.BadZipFile('Invalid front directory length')
        except BaseException:
            self.file.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.file.close()

    def infolist(self):
        return self.entries

    def read(self, info):
        self.file.seek(info.header_offset)
        h = self.file.read(30)
        sig, ver, flag, method, tm, dt, crc, cs, us, nl, xl = struct.unpack('<IHHHHHIIIHH', h)
        if sig != 0x04034B50 or method != info.compress_type or flag & 1:
            raise zipfile.BadZipFile('Invalid local file header')
        name = self.file.read(nl).decode('utf-8' if flag & 0x800 else 'latin1')
        if name != info.filename:
            raise zipfile.BadZipFile('Local file name differs from directory')
        self.file.seek(xl, 1)
        packed = self.file.read(info.compress_size)
        if method == 8:
            decoder = zlib.decompressobj(-15)
            data = decoder.decompress(packed, min(MAX_FILE, info.file_size) + 1)
            if not decoder.eof or decoder.unused_data:
                raise zipfile.BadZipFile('Incomplete or oversized compressed file')
        elif method == 0:
            data = packed
        else:
            raise zipfile.BadZipFile('Unsupported compression')
        # Early startup archives use zero as a missing CRC. Nonzero CRCs are checked.
        if len(data) != info.file_size or (info.CRC and zlib.crc32(data) != info.CRC):
            raise zipfile.BadZipFile('File size or CRC does not match')
        return data


def open_zip(path):
    try:
        return zipfile.ZipFile(path, metadata_encoding='latin1')
    except zipfile.BadZipFile:
        return FrontZip(path)


def kind(name):
    suffix = Path(name).suffix.lower()
    return {'.zip': 'archive', '.oct': 'oct', '.dds': 'texture', '.png': 'texture',
            '.tga': 'texture', '.bank': 'sound', '.fsb': 'sound', '.vbuf': 'mesh', '.ibuf': 'mesh',
            '.txt': 'text', '.xml': 'text', '.json': 'text', '.ini': 'text',
            '.csv': 'text'}.get(suffix, 'other')


def cache_root():
    if os.environ.get('TS3TOOL_SETTINGS'):
        return Path(os.environ['TS3TOOL_SETTINGS']).resolve().parent / 'explorer-cache'
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / '.cache')) / 'TS3 Modding Tool' / 'explorer'


def signature(path):
    s = path.stat()
    return [s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def directory(path):
    """zipfile seeks to the final directory, including the game's duplicate-directory ZIPs."""
    with open_zip(path) as z:
        result, seen = [], set()
        for entry in z.infolist():
            if entry.is_dir():
                continue
            name = relative(entry.filename)
            if name.casefold() in seen:
                raise ModError('Duplicate archive member: ' + name, 'invalid_data')
            seen.add(name.casefold())
            if entry.flag_bits & 1 or entry.compress_type not in (0, 8):
                raise ModError('Unsupported ZIP compression/encryption: ' + name, 'unsupported_format')
            result.append(dict(member=name, size=entry.file_size, compressed_size=entry.compress_size,
                               kind=kind(name)))
        # A file cannot also be a directory (including case aliases on Windows).
        for entry in result:
            if any(str(p).replace('\\', '/').casefold() in seen for p in Path(entry['member']).parents if str(p) != '.'):
                raise ModError('Archive file/directory collision: ' + entry['member'], 'invalid_data')
        return result


class Browser:
    def __init__(self, game, cache=None):
        self.game = Path(game).resolve()
        if not (self.game / 'assets').is_dir() or not (self.game / 'data_dx').is_dir():
            raise ModError('Choose the Toy Story 3 game folder (assets and data_dx).', 'game_not_found')
        self.cache = Path(cache) if cache is not None else cache_root()
        key = hashlib.sha256(os.path.normcase(str(self.game)).encode()).hexdigest()[:24]
        self.cache_file = self.cache / (key + '.json')

    def source(self, path):
        path = relative(path)
        if path.split('/')[0] not in ('assets', 'data_dx'):
            raise ModError('Only assets/ and data_dx/ can be browsed.', 'invalid_path')
        target = inside(self.game, path)
        if not target.is_file():
            raise ModError('Game file not found: ' + path, 'not_found')
        return target

    def index(self, refresh=False):
        old = {}
        if not refresh:
            try:
                data = json.loads(self.cache_file.read_text(encoding='utf-8'))
                if data.get('schema_version') == 2 and data.get('game') == str(self.game):
                    old = data['files']
            except (OSError, ValueError, KeyError, TypeError):
                pass
        if not isinstance(old, dict):
            old = {}
        files, errors, reused = {}, [], 0
        for root in ('assets', 'data_dx'):
            base = inside(self.game, root)
            def walk_error(e):
                errors.append({'path': str(e.filename), 'message': str(e)})
            for folder, dirs, names in os.walk(base, onerror=walk_error):
                dirs[:] = sorted(d for d in dirs if not self._linked(Path(folder) / d))
                for name in sorted(names):
                    source = Path(folder) / name
                    path = source.relative_to(self.game).as_posix()
                    try:
                        self.source(path)
                        sig = signature(source)
                        cached = old.get(path)
                        if (isinstance(cached, dict) and cached.get('signature') == sig
                                and isinstance(cached.get('entries'), list)):
                            info = dict(cached)
                            reused += 1
                        else:
                            entries = directory(source) if kind(name) == 'archive' else []
                            info = dict(signature=sig, size=sig[0], kind=kind(name), entries=entries)
                        if info['kind'] == 'sound' and 'audio_samples' not in info:
                            from audiobank import sample_count
                            try:
                                info['audio_samples'] = sample_count(source)
                            except (OSError, ModError, struct.error) as e:
                                # Keep unknown audio visible in the technical view; never guess from its filename.
                                info.update(audio_samples=None, audio_note=str(e))
                        if signature(source) != sig:
                            raise ModError('File changed while indexing; refresh to retry.', 'source_changed')
                        files[path] = info
                    except (OSError, ValueError, zipfile.BadZipFile, struct.error) as e:
                        errors.append({'path': path, 'message': str(e)})
        data = dict(schema_version=2, game=str(self.game), files=files)
        try:
            self.cache.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.cache, delete=False) as f:
                temp = Path(f.name)
                json.dump(data, f, ensure_ascii=False)
            try:
                os.replace(temp, self.cache_file)
            finally:
                temp.unlink(missing_ok=True)
        except OSError as e:
            errors.append({'path': str(self.cache_file), 'message': str(e)})
        return dict(data, errors=errors, reused=reused)

    @staticmethod
    def _linked(path):
        return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())

    @staticmethod
    def search(index, query='', category=None, playable=False):
        result = []
        for path, info in sorted(index['files'].items()):
            rows = [dict(path=path, member=None, size=info['size'], kind=info['kind'])]
            if 'audio_samples' in info:
                rows[0]['audio_samples'] = info['audio_samples']
            rows += [dict(e, path=path) for e in info['entries']]
            result.extend(r for r in rows if (not category or r['kind'] == category)
                          and (not playable or (r['kind'] == 'sound' and (r.get('audio_samples') or 0) > 0))
                          and query.casefold() in (path + '/' + (r['member'] or '')).casefold())
        return result

    def read(self, path, member=None):
        source = self.source(path)
        sig = signature(source)
        if member is None:
            if sig[0] > MAX_FILE:
                raise ModError('File is too large to inspect (512 MiB maximum).', 'size_limit')
            data = source.read_bytes()
        else:
            member = relative(member)
            entries = directory(source)
            entry = next((e for e in entries if e['member'] == member), None)
            if entry is None:
                raise ModError('Archive member not found: ' + member, 'not_found')
            if entry['size'] > MAX_FILE:
                raise ModError('Archive member is too large (512 MiB maximum).', 'size_limit')
            with open_zip(source) as z:
                # relative() normalizes backslashes, while ZIP names retain their original spelling.
                info = next(i for i in z.infolist() if relative(i.filename.rstrip('/')) == member)
                data = z.read(info)  # zipfile validates length and CRC
        if signature(source) != sig:
            raise ModError('Source changed while reading. Refresh and try again.', 'source_changed')
        return data

    def inspect(self, path, member=None):
        source = self.source(path)
        result = dict(path=path, member=member, kind=kind(member or path))
        if member is None and kind(path) == 'archive':
            entries = directory(source)
            return dict(result, size=source.stat().st_size, entries=entries)
        data = self.read(path, member)
        result['size'] = len(data)
        if result['kind'] == 'oct':
            from octlib import Oct
            f = Oct.parse(data)
            result['pools'] = {n: len(f.children(f.find(n)[0])) for n in
                               ('TexturePool', 'MaterialPool', 'SceneTreeNodePool', 'VertexStreamPool',
                                'IndexStreamPool') if f.find(n)}
            result['textures'] = [info for info, _ in textures(f)]
            model = self.character(path, member, data, textures=False)
            if model is not None:
                lo, hi = model.full_bounds()
                result['model'] = dict(vertices=len(model.P0), triangles=model.triangles, pieces=model.pieces,
                                       pieces_left_out=model.skipped, materials=len(model.groups),
                                       bones=len(model.names) if model.names != ['Root'] else 0,
                                       size=[round(float(x), 3) for x in hi - lo])
            result['text'] = '\n'.join(f.describe(i) for i in range(min(len(f.recs), 400)))
            result['truncated'] = len(f.recs) > 400
        elif result['kind'] == 'sound':
            import audiobank
            try:
                parsed = audiobank.bank(data)
                result.update(sounds=audiobank.describe(parsed), audio_mode=parsed['mode'])
            except ModError as e:
                if e.code != 'no_audio': raise
                result['sounds'] = []
                result['note'] = str(e)
        elif result['kind'] == 'texture':
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                result.update(width=image.width, height=image.height, format=image.format)
        else:
            result['text'] = data[:4096].decode('utf-8', errors='replace') if result['kind'] == 'text' else data[:256].hex(' ')
            result['truncated'] = len(data) > (4096 if result['kind'] == 'text' else 256)
        return result

    def export(self, path, member, output, preview=False):
        """Stage a complete export, then publish a new folder. Never overwrite existing output."""
        output = Path(output).absolute()
        if output.exists() or output.is_symlink():
            raise ModError('Choose a new output folder: ' + str(output), 'destination_exists')
        if output.resolve().is_relative_to(self.game):
            raise ModError('Export outside the game folder.', 'invalid_path')
        source = self.source(path)
        sig = signature(source)
        entries = directory(source) if member is None and kind(path) == 'archive' else None
        if entries and sum(e['size'] for e in entries) > MAX_EXPORT:
            raise ModError('Archive export exceeds 2 GiB.', 'size_limit')
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.ts3-export-', dir=output.parent) as temp:
            stage = Path(temp) / 'result'
            stage.mkdir()
            if preview:
                images, _ = self.preview(path, member)
                if not images:
                    raise ModError('No supported image or model preview for this asset.', 'unsupported_format')
                for name, image in images.items():
                    image.save(stage / (name + '.png'))
            else:
                if entries is not None:
                    with open_zip(source) as z:
                        infos = {relative(i.filename): i for i in z.infolist() if not i.is_dir()}
                        for e in entries:
                            if e['size'] > MAX_FILE:
                                raise ModError('Archive member is too large (512 MiB maximum).', 'size_limit')
                            target = inside(stage, e['member'])
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(z.read(infos[e['member']]))
                else:
                    target = inside(stage, member or Path(path).name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(self.read(path, member))
            if signature(source) != sig:
                raise ModError('Source changed during export. Nothing was exported.', 'source_changed')
            written = [p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()]
            if output.exists():
                raise ModError('Output folder appeared during export.', 'destination_exists')
            stage.rename(output)
        return dict(output=str(output), files=written)

    def export_glb(self, path, member, output):
        """Export bind-pose geometry and diffuse maps into one GLB in a new folder."""
        import gltf
        import viewer
        import ts3model as T
        from octlib import Oct
        output = Path(output).absolute()
        if output.exists() or output.is_symlink():
            raise ModError('Choose a new output folder: ' + str(output), 'destination_exists')
        if output.resolve().is_relative_to(self.game):
            raise ModError('Export outside the game folder.', 'invalid_path')
        source = self.source(path)
        sources = {source: signature(source)}
        if member is None and kind(path) == 'archive':
            main = Path(path).stem + '.oct'
            member = next((e['member'] for e in directory(source) if e['member'].casefold() == main.casefold()), None)
            if member is None:
                raise ModError('Select an OCT model inside this archive.', 'not_found')
        if kind(member or path) != 'oct':
            raise ModError('Choose an OCT model or its game archive.', 'unsupported_format')
        data = self.read(path, member)
        model = self.character(path, member, data, textures=False, sources=sources)
        if model is None:
            raise ModError('No supported model geometry in this OCT.', 'unsupported_format')
        f = Oct.parse(data)
        texs = T.pool(f, 'TexturePool') if f.find('TexturePool') else []
        mats = T.pool(f, 'MaterialPool') if f.find('MaterialPool') else []
        def texture(material):
            # Decode one original-resolution diffuse map at a time; preview thumbnails are never exported.
            return viewer._texture(f, texs, mats[material], None, {}) if 0 <= material < len(mats) else None
        payload, report = gltf.encode(model, Path(member or path).stem, texture_provider=texture)
        report.update(path=path, member=member, credit=gltf.CREDIT)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.ts3-glb-', dir=output.parent) as temp:
            stage = Path(temp) / 'result'; stage.mkdir()
            (stage / 'model.glb').write_bytes(payload)
            (stage / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            (stage / 'README.txt').write_text(
                gltf.CREDIT + '\n\nOpen model.glb in Blender or a glTF 2.0 editor.\n'
                'Geometry is in bind pose, Y up, metres. Textures are embedded PNG diffuse maps.\n'
                'Bone pivots and weights are exported; original bone roll/rotation is not reconstructed.\n'
                'No game animations, lighting or shaders. Unsupported/hidden pieces may be omitted; see report.json.\n'
                'Rigged characters may use normal fitting or verified original-skeleton mode in a project.\n'
                'For rigid same-topology edits, export a separate meshes dump workspace with vertex correspondence.\n'
                'This regular GLB export has no rigid reinsertion correspondence and does not change the game.\n'
                'These are game assets from your local copy; keep them local.\n', encoding='utf-8')
            for file, before in sources.items():
                if signature(file) != before:
                    raise ModError('Source changed during GLB export.', 'source_changed')
            if output.exists() or output.is_symlink():
                raise ModError('Output folder appeared during export.', 'destination_exists')
            stage.rename(output)
        return dict(output=str(output), files=['model.glb', 'report.json', 'README.txt'], **report)

    def character(self, path, member, data=None, textures=True, sources=None):
        """the model in that .oct (viewer.GameModel: characters, objects, levels), or None if it holds no geometry that
        can be drawn; its buffers are the files it names, next to it"""
        from viewer import GameModel
        name = member or Path(path).name
        if not name.lower().endswith('.oct'):
            return None
        data = self.read(path, member) if data is None else data

        def beside(file_name):
            """a buffer named by the .oct, by case-blind name in its folder; None when absent"""
            try:
                if member:
                    folder = member.rpartition('/')[0]
                    wanted = (folder + '/' if folder else '') + file_name
                    entry = next((e['member'] for e in directory(self.source(path))
                                  if e['member'].casefold() == wanted.casefold()), None)
                    return self.read(path, entry) if entry else None
                buffer_path = path.rpartition('/')[0] + '/' + file_name
                if sources is not None:
                    source = self.source(buffer_path)
                    sources.setdefault(source, signature(source))
                return self.read(buffer_path)
            except ModError as e:
                if e.code == 'not_found':
                    return None
                raise
        try:
            return GameModel(data, beside, textures)
        except (IndexError, KeyError, ValueError, TypeError, struct.error):
            return None

    def preview(self, path, member=None):
        from PIL import Image, ImageDraw
        if member is None and kind(path) == 'archive':      # an archive shows its main model, if it has one
            main = Path(path).stem + '.oct'
            member = next((e['member'] for e in directory(self.source(path)) if e['member'].casefold() == main.casefold()), None)
            if member is None:
                return {}, None
        if kind(member or path) not in ('oct', 'texture'):
            return {}, None
        data = self.read(path, member)
        images, character = {}, None
        if kind(member or path) == 'texture':
            with Image.open(io.BytesIO(data)) as im:
                images['texture'] = im.convert('RGBA')
        elif kind(member or path) == 'oct':
            from octlib import Oct
            thumbs = []
            for info, raw in textures(Oct.parse(data)):
                try:
                    with Image.open(io.BytesIO(raw)) as im:
                        thumb = im.convert('RGBA')
                        thumb.thumbnail((176, 156))
                        thumbs.append((info['name'], thumb))
                except (OSError, ValueError):
                    continue
            # Split sheets so a large TexturePool cannot allocate one huge bitmap.
            for offset in range(0, len(thumbs), 24):
                group = thumbs[offset:offset + 24]
                sheet = Image.new('RGB', (800, ((len(group) + 3) // 4) * 194), '#eeeeee')
                draw = ImageDraw.Draw(sheet)
                for i, (name, thumb) in enumerate(group):
                    x, y = (i % 4) * 200, (i // 4) * 194
                    sheet.paste(thumb, (x + (200 - thumb.width) // 2, y + 8), thumb)
                    draw.text((x + 8, y + 169), name[:28], fill='#222222')
                images['textures-%02d' % (offset // 24 + 1)] = sheet
            character = self.character(path, member, data)
            if character is not None:
                from viewer import snapshot
                images['model'] = snapshot(character)
                lo, hi = character.bounds()
                if max(hi[0] - lo[0], hi[2] - lo[2]) > 1.5 * (hi[1] - lo[1]):    # levels read better from above
                    images['model-top'] = snapshot(character, 'top')
        return images, character


def textures(f):
    from PIL import Image
    pools = f.find('TexturePool')
    if not pools:
        return
    for i, t in enumerate(f.children(pools[0])):
        child = f.child(t, 'Data')
        if child is None:
            continue
        raw = bytes(f.recs[child].items()[1])
        name = f.child(t, 'Name')
        crc = f.child(t, 'DataCRC')
        info = dict(index=i, name=f.value(name)[0] if name is not None else str(i), size=len(raw),
                    crc=f.value(crc)[0] if crc is not None else None)
        try:
            with Image.open(io.BytesIO(raw)) as image:
                info.update(width=image.width, height=image.height, format=image.format)
        except (OSError, ValueError):
            info['format'] = 'unsupported'
        yield info, raw
