"""Bounded glTF 2.0 reader exposing the converter's Scene interface.

Reads a default scene in its default pose, not animation. Resources stay inside the model's
directory or data URIs. Reading never extracts files; project texture extraction is explicit.
"""
import base64
from collections import Counter
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import warnings
from urllib.parse import unquote, urlsplit

import numpy as np
from PIL import Image
from modfile import ModError, inside, json_bytes, relative

MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
MAX_VERTICES = 5_000_000
MAX_NODES = 20000
DTYPES = {5120: 'i1', 5121: 'u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
WIDTHS = dict(SCALAR=1, VEC2=2, VEC3=3, VEC4=4, MAT4=16)


def fail(message, code='invalid_data'):
    raise ModError('glTF: ' + message, code)


def integer(value, low=0, high=MAX_VERTICES):
    if type(value) is not int or not low <= value <= high:
        fail('invalid integer or index')
    return value


def ref(items, index):
    return items[integer(index, high=len(items) - 1)]


def numbers(value, count):
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (count,) or not np.isfinite(result).all():
        fail('invalid numeric vector')
    return result


@contextmanager
def image_open(payload):
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(payload)) as image:
                yield image
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            fail('image exceeds decoded size limits', 'size_limit')


def local_matrix(node):
    if 'matrix' in node:
        if any(k in node for k in ('translation', 'rotation', 'scale')):
            fail('a node cannot contain both matrix and TRS')
        m = numbers(node['matrix'], 16).reshape(4, 4).T
    else:
        t = numbers(node.get('translation', [0, 0, 0]), 3)
        s = numbers(node.get('scale', [1, 1, 1]), 3)
        q = numbers(node.get('rotation', [0, 0, 0, 1]), 4)
        if abs(np.linalg.norm(q) - 1) > 1e-4:
            fail('rotation quaternion must have unit length')
        x, y, z, w = q
        r = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                      [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                      [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        m = np.eye(4); m[:3, :3] = r @ np.diag(s); m[:3, 3] = t
    if not np.allclose(m[3], [0, 0, 0, 1], atol=1e-7):
        fail('node matrix is not affine')
    return m


class Scene:
    # glTF primitives may intentionally overlap with different materials/UVs.
    deduplicate_meshes = False

    def __init__(self, path, *, correspondence=True):
        self.correspondence = correspondence
        try:
            with np.errstate(all='ignore'):
                self._load(Path(path).resolve())
        except ModError:
            raise
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, struct.error, OverflowError) as e:
            fail(str(e) or 'malformed model')

    def _load(self, path):
        self.path, self.settings, self.objects, self.conn = path, {}, {}, []
        self.total, self.hash = 0, hashlib.sha256()
        raw = self._file(path)
        binary = None
        if path.suffix.lower() == '.glb':
            if len(raw) < 20 or struct.unpack_from('<4sII', raw) != (b'glTF', 2, len(raw)):
                fail('invalid GLB header')
            at, chunks = 12, []
            while at < len(raw):
                size, kind = struct.unpack_from('<II', raw, at); at += 8
                if size % 4 or at + size > len(raw): fail('invalid GLB chunk bounds')
                chunks.append((kind, raw[at:at + size])); at += size
            if not chunks or chunks[0][0] != 0x4E4F534A or sum(k == 0x4E4F534A for k, _ in chunks) != 1:
                fail('GLB requires one first JSON chunk')
            bins = [b for k, b in chunks if k == 0x004E4942]
            if len(bins) > 1: fail('multiple GLB binary chunks')
            binary = bins[0] if bins else None
            js = chunks[0][1]
        elif path.suffix.lower() == '.gltf':
            js = raw
        else:
            fail('expected a .glb or .gltf file', 'unsupported_format')
        if len(js) > 32 * 1024 * 1024: fail('JSON exceeds 32 MiB', 'size_limit')
        self.doc = json.loads(js.decode('utf-8-sig'))
        d = self.doc
        if not isinstance(d, dict) or d.get('asset', {}).get('version') != '2.0': fail('expected glTF 2.0')
        if d['asset'].get('minVersion', '2.0') != '2.0': fail('unsupported minimum version', 'unsupported_format')
        if set(d.get('extensionsRequired', [])) - {'KHR_materials_unlit'}:
            fail('required extensions are not supported: ' + ', '.join(d['extensionsRequired']), 'unsupported_format')
        for key in ('buffers', 'bufferViews', 'accessors', 'nodes', 'meshes', 'skins', 'materials', 'images', 'textures', 'scenes'):
            if not isinstance(d.setdefault(key, []), list) or any(not isinstance(x, dict) for x in d[key]):
                fail('invalid ' + key + ' list')
        if len(d['images']) > 4096 or len(d['materials']) > 4096 or len(d['accessors']) > 100000:
            fail('too many images, materials or accessors', 'size_limit')
        self.buffers = []
        for i, b in enumerate(d['buffers']):
            size = integer(b['byteLength'], 1, MAX_FILE)
            if 'uri' in b:
                payload = self._uri(b['uri'])
            elif i == 0 and binary is not None:
                payload = binary
                if not size <= len(payload) <= size + 3: fail('invalid GLB binary length')
            else:
                fail('buffer has no resource')
            if len(payload) < size: fail('buffer is shorter than byteLength')
            self.buffers.append(memoryview(payload)[:size])
        self.image_data = []
        for image in d['images']:
            if ('uri' in image) == ('bufferView' in image): fail('image needs one resource')
            if 'uri' in image:
                payload = self._uri(image['uri'])
            else:
                view, _ = self._view(image['bufferView']); self.total += len(view)
                if self.total > MAX_TOTAL: fail('resources exceed 1 GiB', 'size_limit')
                payload = bytes(view)
            self.image_data.append(payload)
        self.warnings = ['Conversion uses the default pose; animations and full PBR/game shaders are not imported.']
        if d.get('animations'): self.warnings.append('Animation clips were ignored.')
        self._graph()
        self._materials()
        self._meshes, self._bones = [], {}
        self.joint_nodes, self.used_skins = set(), set()
        for node in self.active:
            n = d['nodes'][node]
            if 'mesh' in n and 'skin' in n:
                skin = ref(d['skins'], n['skin']); self.used_skins.add(n['skin'])
                joints = skin.get('joints')
                if not isinstance(joints, list) or not 1 <= len(joints) <= 65535: fail('invalid skin joints')
                checked = [integer(j, high=len(d['nodes'])-1) for j in joints]
                if len(set(checked)) != len(checked) or any(j not in self.active for j in checked):
                    fail('skin joints must be unique nodes in the selected scene')
                self.joint_nodes.update(checked)
        bone_nodes = set(self.joint_nodes)
        for j in list(bone_nodes):
            while self.parents[j] != -1:
                j = self.parents[j]; bone_nodes.add(j)
        for j in sorted(bone_nodes):
            self._bones[j] = dict(name=self.names[j], parent=self.parents[j] if self.parents[j] in bone_nodes else None,
                                  props={}, kind='LimbNode' if j in self.joint_nodes else 'Null')
        vertices = 0
        for node in sorted(self.active):
            n = d['nodes'][node]
            if 'mesh' not in n: continue
            mesh = ref(d['meshes'], n['mesh'])
            if not isinstance(mesh.get('primitives'), list): fail('invalid primitive list')
            for pi, primitive in enumerate(mesh['primitives']):
                part = self._primitive(node, primitive, pi)
                vertices += len(part['pos'])
                if vertices > MAX_VERTICES: fail('model exceeds 5 million imported vertices', 'size_limit')
                self._meshes.append(part)
        if not self._meshes: fail('no triangle meshes in the selected scene', 'unsupported_format')
        self.fingerprint = self.hash.hexdigest()

    def _file(self, path):
        size = path.stat().st_size
        if not path.is_file() or size > MAX_FILE: fail('resource exceeds 512 MiB', 'size_limit')
        self.total += size
        if self.total > MAX_TOTAL: fail('resources exceed 1 GiB', 'size_limit')
        data = path.read_bytes(); self.hash.update(data)
        return data

    def _uri(self, uri):
        if not isinstance(uri, str): fail('invalid resource URI')
        if uri.startswith('data:'):
            header, sep, data = uri.partition(',')
            if not sep or not header.endswith(';base64'): fail('only base64 data URIs are supported', 'unsupported_format')
            if len(data) > (MAX_FILE + 2) // 3 * 4: fail('data URI is too large', 'size_limit')
            payload = base64.b64decode(data, validate=True)
            self.total += len(payload)
            if self.total > MAX_TOTAL: fail('resources exceed 1 GiB', 'size_limit')
            self.hash.update(payload); return payload
        parsed = urlsplit(uri)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            fail('remote/absolute resource URIs are not supported', 'invalid_path')
        return self._file(inside(self.path.parent, relative(unquote(parsed.path))))

    def _view(self, index):
        view = ref(self.doc['bufferViews'], index)
        buf = ref(self.buffers, view['buffer'])
        start = integer(view.get('byteOffset', 0), high=MAX_FILE); size = integer(view['byteLength'], 1, MAX_FILE)
        if start + size > len(buf): fail('bufferView exceeds its buffer')
        return buf[start:start+size], view

    def _values(self, view_index, offset, count, width, dtype, sparse=False):
        data, view = self._view(view_index)
        dt = np.dtype(dtype); size = dt.itemsize * width
        stride = integer(view.get('byteStride', size), size, max(252, size))
        offset = integer(offset, high=MAX_FILE)
        if stride % dt.itemsize or offset % dt.itemsize or offset + (count-1)*stride + size > len(data):
            fail('accessor exceeds or misaligns its bufferView')
        if sparse and 'byteStride' in view: fail('sparse accessors cannot have a byte stride')
        return np.ndarray((count, width), dtype=dt, buffer=data, offset=offset, strides=(stride, dt.itemsize)).copy()

    def accessor(self, index):
        acc = ref(self.doc['accessors'], index)
        count = integer(acc['count'], 1, MAX_VERTICES)
        if acc.get('componentType') not in DTYPES or acc.get('type') not in WIDTHS:
            fail('unsupported accessor layout', 'unsupported_format')
        component, kind = acc['componentType'], acc['type']
        if 'normalized' in acc and type(acc['normalized']) is not bool: fail('normalized must be boolean')
        dtype, width = DTYPES[component], WIDTHS[kind]
        if kind == 'MAT4' and component != 5126: fail('only floating MAT4 accessors are supported', 'unsupported_format')
        result = (self._values(acc['bufferView'], acc.get('byteOffset', 0), count, width, dtype)
                  if 'bufferView' in acc else np.zeros((count, width), dtype=dtype))
        if 'sparse' in acc:
            sparse = acc['sparse']; n = integer(sparse['count'], 1, count)
            si, sv = sparse['indices'], sparse['values']; comp = si['componentType']
            if comp not in (5121, 5123, 5125): fail('invalid sparse indices')
            ix = self._values(si['bufferView'], si.get('byteOffset', 0), n, 1, DTYPES[comp], True).ravel()
            if (ix >= count).any() or (ix[1:].astype(np.int64) <= ix[:-1]).any(): fail('invalid sparse index order')
            result[ix] = self._values(sv['bufferView'], sv.get('byteOffset', 0), n, width, dtype, True)
        if acc.get('normalized', False):
            if component not in (5120, 5121, 5122, 5123): fail('invalid normalized accessor')
            info = np.iinfo(dtype)
            result = np.maximum(result.astype(np.float64) / info.max, -1) if info.min < 0 else result.astype(np.float64) / info.max
        if not np.isfinite(result).all(): fail('accessor contains nonfinite values')
        return result

    def _graph(self):
        nodes = self.doc['nodes']
        if not 1 <= len(nodes) <= MAX_NODES: fail('invalid node count', 'size_limit')
        self.parents = [-1] * len(nodes)
        for i, n in enumerate(nodes):
            for j in n.get('children', []):
                integer(j, high=len(nodes)-1)
                if self.parents[j] != -1: fail('node has multiple parents')
                self.parents[j] = i
        self.world, pending = {}, [i for i, p in enumerate(self.parents) if p == -1]
        while pending:
            i = pending.pop(); parent = self.parents[i]
            self.world[i] = (self.world[parent] if parent != -1 else np.eye(4)) @ local_matrix(nodes[i])
            if not np.isfinite(self.world[i]).all(): fail('node transform exceeds numeric limits')
            pending.extend(nodes[i].get('children', []))
        if len(self.world) != len(nodes): fail('cyclic node hierarchy')
        scenes = self.doc['scenes']
        roots = ref(scenes, self.doc.get('scene', 0)).get('nodes', []) if scenes else [i for i, p in enumerate(self.parents) if p == -1]
        self.active, pending = set(), list(roots)
        for root in roots:
            integer(root, high=len(nodes)-1)
            if self.parents[root] != -1: fail('scene roots cannot have parents')
        while pending:
            i = pending.pop()
            if i in self.active: fail('duplicate scene node')
            self.active.add(i); pending.extend(nodes[i].get('children', []))
        self.names = [str(n.get('name') or 'Node%d' % i) for i, n in enumerate(nodes)]
        counts = Counter(self.names)
        self.names = [name + '__node%d' % i if counts[name] > 1 else name for i, name in enumerate(self.names)]
        used = set()
        for i, name in enumerate(self.names):
            while name in used: name += '__node%d' % i
            self.names[i] = name; used.add(name)

    def _materials(self):
        self.matnames, self.colours, self.links, self.pngs, png_bytes = [], {}, {}, {}, 0
        for i, mat in enumerate(self.doc['materials']):
            name = str(mat.get('name') or 'Material') + '__mat%d' % i
            self.matnames.append(name)
            pbr = mat.get('pbrMetallicRoughness', {})
            factor = numbers(pbr.get('baseColorFactor', [1, 1, 1, 1]), 4)
            if ((factor < 0) | (factor > 1)).any(): fail('invalid baseColorFactor')
            self.colours[name] = factor[:3].tolist()
            for slot, info in (('d', pbr.get('baseColorTexture')), ('n', mat.get('normalTexture'))):
                if info is None: continue
                if info.get('texCoord', 0) != 0 or info.get('extensions') or (slot == 'n' and info.get('scale', 1) != 1):
                    fail('texture transforms, extra UV sets and normal scale are not supported', 'unsupported_format')
                tex = ref(self.doc['textures'], info['index'])
                payload = ref(self.image_data, tex['source'])
                with image_open(payload) as image:
                    if image.format not in ('PNG', 'JPEG'): fail('only PNG/JPEG images are supported', 'unsupported_format')
                    if max(image.size) > 8192: fail('image exceeds 8192 pixels', 'size_limit')
                    image = image.convert('RGBA')
                    if slot == 'd' and not np.array_equal(factor, [1, 1, 1, 1]):
                        values = np.asarray(image).astype(np.float64) / 255
                        rgb = values[:, :, :3]
                        linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055)**2.4) * factor[:3]
                        rgb = np.where(linear <= .0031308, linear * 12.92, 1.055 * linear**(1/2.4) - .055)
                        values[:, :, :3] = rgb; values[:, :, 3] *= factor[3]
                        image = Image.fromarray(np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8))
                    out = io.BytesIO(); image.save(out, 'PNG')
                filename = 'material_%04d_%s.png' % (i, slot)
                png_bytes += len(out.getvalue())
                if png_bytes > MAX_FILE: fail('generated textures exceed 512 MiB', 'size_limit')
                self.pngs[filename] = out.getvalue(); self.links.setdefault(name, {})[slot] = filename
        self.matnames.append('Default__mat%d' % len(self.matnames))
        self.colours[self.matnames[-1]] = [1, 1, 1]

    def _attribute(self, attributes, name, width, count=None):
        values = self.accessor(attributes[name])
        if values.shape[1] != width or (count is not None and len(values) != count): fail('attribute size mismatch: ' + name)
        return values

    def _primitive(self, node, primitive, number):
        if primitive.get('targets') or primitive.get('extensions'):
            fail('morph targets and compressed primitives are not supported', 'unsupported_format')
        attributes = primitive['attributes']
        pos = self._attribute(attributes, 'POSITION', 3)
        if ref(self.doc['accessors'], attributes['POSITION'])['componentType'] != 5126: fail('positions must be floating point')
        count = len(pos)
        if 'indices' in primitive:
            acc = ref(self.doc['accessors'], primitive['indices'])
            if acc['type'] != 'SCALAR' or acc['componentType'] not in (5121, 5123, 5125) or acc.get('normalized'):
                fail('invalid triangle indices')
            indices = self.accessor(primitive['indices']).ravel().astype(np.int64)
        else: indices = np.arange(count)
        if (indices >= count).any(): fail('triangle index out of range')
        mode = primitive.get('mode', 4)
        if mode == 4 and len(indices) % 3 == 0: tri = indices.reshape(-1, 3)
        elif mode == 5 and len(indices) >= 3:
            tri = np.stack([indices[:-2], indices[1:-1], indices[2:]], 1); tri[1::2] = tri[1::2, [1, 0, 2]]
        elif mode == 6 and len(indices) >= 3:
            tri = np.stack([np.full(len(indices)-2, indices[0]), indices[1:-1], indices[2:]], 1)
        else: fail('only triangle meshes are supported', 'unsupported_format')
        if not len(tri): fail('empty primitive')
        uv = self._attribute(attributes, 'TEXCOORD_0', 2, count) if 'TEXCOORD_0' in attributes else np.zeros((count, 2))
        normal = self._attribute(attributes, 'NORMAL', 3, count) if 'NORMAL' in attributes else None
        if 'COLOR_0' in attributes and not np.allclose(self.accessor(attributes['COLOR_0']), 1):
            fail('vertex colours are not supported', 'unsupported_format')
        used, local = np.unique(tri.ravel(), return_inverse=True); tri = local.reshape(-1, 3)
        pos, uv = pos[used].astype(np.float64), uv[used].astype(np.float64)
        normal = normal[used].astype(np.float64) if normal is not None else None
        n = self.doc['nodes'][node]
        clusters = None
        if 'skin' in n:
            if not all(k in attributes for k in ('JOINTS_0', 'WEIGHTS_0')): fail('skinned mesh needs JOINTS_0 and WEIGHTS_0')
            if any(k.startswith(('JOINTS_', 'WEIGHTS_')) and k.rsplit('_', 1)[-1] not in ('0', '1') for k in attributes):
                fail('more than eight skin influences are not supported', 'unsupported_format')
            skin = ref(self.doc['skins'], n['skin']); joints = skin['joints']
            weights, joint_indices = [], []
            for suffix in ('0', '1'):
                j, w = 'JOINTS_' + suffix, 'WEIGHTS_' + suffix
                if (j in attributes) != (w in attributes): fail('incomplete skin attributes')
                if j in attributes:
                    ja = ref(self.doc['accessors'], attributes[j]); wa = ref(self.doc['accessors'], attributes[w])
                    if ja['componentType'] not in (5121, 5123) or ja.get('normalized'): fail('invalid joint attribute')
                    if wa['componentType'] != 5126 and (wa['componentType'] not in (5121, 5123) or not wa.get('normalized')):
                        fail('integer weights must be normalized unsigned bytes or shorts')
                    joint_indices.append(self._attribute(attributes, j, 4, count)[used].astype(np.int64))
                    weights.append(self._attribute(attributes, w, 4, count)[used].astype(np.float64))
            if not weights: fail('skinned mesh has no weights')
            ji, bw = np.concatenate(joint_indices, 1), np.concatenate(weights, 1)
            if (ji >= len(joints)).any() or ((bw < 0) | (bw > 1)).any() or (bw.sum(1) <= 0).any(): fail('invalid skin influences')
            bw /= bw.sum(1, keepdims=True)
            if 'inverseBindMatrices' in skin:
                inv = self.accessor(skin['inverseBindMatrices'])
                acc = ref(self.doc['accessors'], skin['inverseBindMatrices'])
                if acc['type'] != 'MAT4' or acc['componentType'] != 5126 or len(inv) < len(joints): fail('invalid inverse bind matrices')
                inv = inv[:len(joints)].reshape(-1, 4, 4).transpose(0, 2, 1)
            else: inv = np.repeat(np.eye(4)[None], len(joints), 0)
            if not np.allclose(inv[:, 3], [0, 0, 0, 1], atol=1e-6): fail('inverse bind matrices must be affine')
            bind = np.stack([self.world[j] @ inv[i] for i, j in enumerate(joints)])
            out, norm, signs = np.empty_like(pos), np.empty_like(pos) if normal is not None else None, np.empty(len(pos))
            for start in range(0, len(pos), 65536):
                stop = min(start+65536, len(pos))
                blend = (bind[ji[start:stop]] * bw[start:stop, :, None, None]).sum(1)
                out[start:stop] = np.einsum('nij,nj->ni', blend[:, :3, :3], pos[start:stop]) + blend[:, :3, 3]
                signs[start:stop] = np.linalg.det(blend[:, :3, :3])
                if norm is not None: norm[start:stop] = np.einsum('nji,nj->ni', np.linalg.inv(blend[:, :3, :3]), normal[start:stop])
            pos, normal = out, norm
            clusters = []
            for bone in self._bones:
                slots = [i for i, joint in enumerate(joints) if joint == bone]
                w = np.where(np.isin(ji, slots), bw, 0).sum(1) if slots else np.zeros(len(pos))
                ids = np.flatnonzero(w > 0); link = self.world[bone].T
                clusters.append(dict(bone=self.names[bone], bone_id=bone, idx=ids, w=w[ids], xf=np.linalg.inv(link), xlink=link))
        else:
            matrix = self.world[node]; pos = pos @ matrix[:3, :3].T + matrix[:3, 3]
            if normal is not None: normal = normal @ np.linalg.inv(matrix[:3, :3])
            signs = np.full(len(pos), np.linalg.det(matrix[:3, :3]))
        if (not np.isfinite(pos).all() or not np.isfinite(signs).all() or (np.abs(signs) < 1e-12).any()
                or (np.abs(pos) > np.finfo(np.float32).max).any()): fail('singular or invalid mesh transform')
        negative = signs[tri] < 0
        if (negative.any(1) != negative.all(1)).any(): fail('skin flips orientation within a triangle', 'unsupported_format')
        tri[negative.all(1)] = tri[negative.all(1)][:, [0, 2, 1]]
        if normal is None or (np.linalg.norm(normal, axis=1) < 1e-9).any():
            if 'Missing/zero normals were regenerated from triangle geometry.' not in self.warnings:
                self.warnings.append('Missing/zero normals were regenerated from triangle geometry.')
            normal = np.zeros_like(pos); a, b, c = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
            face = np.cross(b-a, c-a)
            for col in range(3): np.add.at(normal, tri[:, col], face)
        normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
        if not np.isfinite(normal).all(): fail('invalid transformed normals')
        uv[:, 1] = 1 - uv[:, 1]  # converter's Scene contract is FBX/OBJ bottom-left; it flips back for TS3.
        material = integer(primitive['material'], high=len(self.matnames)-2) if 'material' in primitive else len(self.matnames)-1
        name = self.names[node] + '__primitive%d' % number
        result = dict(name=name, pos=pos, cp=np.arange(len(pos)), tri=tri, normals=(normal.ravel(), np.arange(len(pos))),
                    uv=(uv.ravel(), np.arange(len(pos))), mat=np.zeros(len(tri), int), matnames=[self.matnames[material]],
                    model=None, skin=clusters)
        if self.correspondence and '_TS3_VERTEX' in attributes:
            ids = self._attribute(attributes, '_TS3_VERTEX', 1, count)[used, 0]
            if (ids < 0).any() or (ids >= 5000000).any() or not np.array_equal(ids, np.rint(ids)):
                fail('invalid _TS3_VERTEX correspondence')
            result['ts3_vertices'] = ids.astype(np.int64)
        return result

    def to_yup(self): return np.eye(3)
    def meshes(self): yield from self._meshes
    def bones(self): return self._bones
    def linked_textures(self): return self.links
    def material_colours(self): return self.colours

    def identity_joints(self):
        rows = []
        for node in sorted(self.joint_nodes):
            parent = self.parents[node]
            while parent != -1 and parent not in self.joint_nodes: parent = self.parents[parent]
            extras = self.doc['nodes'][node].get('extras', {})
            if not isinstance(extras, dict): extras = {}
            rows.append(dict(node=node, name=self.names[node], parent=parent if parent != -1 else None,
                             id=extras.get('ts3BoneId'),
                             pivot=self.world[node][:3, 3].tolist()))
        return rows

    def summary(self):
        return dict(path=str(self.path), format=self.path.suffix.lower()[1:], fingerprint=self.fingerprint,
                    meshes=len(self._meshes), vertices=sum(len(m['pos']) for m in self._meshes),
                    triangles=sum(len(m['tri']) for m in self._meshes), joints=len(self.joint_nodes),
                    skins=len(self.used_skins), static_meshes=sum(m['skin'] is None for m in self._meshes),
                    materials=len(self.matnames)-1, images=len(self.image_data), warnings=self.warnings)

    def extract_textures(self, output):
        """Populate or validate a project-owned content-addressed PNG cache; preserve user edits."""
        output = Path(output).absolute()
        if output.is_symlink() or output.is_junction(): fail('texture output cannot be a link', 'invalid_path')
        if output.exists():
            if not output.is_dir(): fail('texture output already exists', 'destination_exists')
            for name, data in self.pngs.items():
                path = inside(output, name)
                if not path.is_file() or path.read_bytes() != data:
                    fail('generated textures changed; select your edited texture folder explicitly', 'source_changed')
            return str(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.gltf-textures-', dir=output.parent) as temp:
            stage = Path(temp) / 'textures'; stage.mkdir()
            for name, data in self.pngs.items(): (stage / name).write_bytes(data)
            (stage / 'source.json').write_bytes(json_bytes(dict(fingerprint=self.fingerprint)))
            stage.rename(output)
        return str(output)
