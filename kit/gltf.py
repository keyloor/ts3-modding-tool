"""glTF 2.0 binary export in bind pose. No import, animation, or game writes.

The skeleton uses the model's absolute bone pivots, local differences and inverse translations.
Static geometry stays outside the skin even when an OCT also contains skinned pieces.
"""
import hashlib
import io
import json
import struct

import numpy as np
from PIL import Image
from about import CREDIT
from modfile import ModError

MAX_GLB = 512 * 1024 * 1024
MAX_VERTICES = 5_000_000


def array(value, shape, dtype, label):
    result = np.asarray(value)
    if result.shape != shape or not np.isfinite(result).all():
        raise ModError('Invalid model ' + label + '.', 'invalid_data')
    converted = result.astype(dtype)
    if not np.isfinite(converted).all():
        raise ModError('Model values exceed the export range: ' + label, 'invalid_data')
    return converted


class Binary:
    def __init__(self, document):
        self.document, self.data = document, bytearray()

    def view(self, data, target=None):
        self.data.extend(b'\0' * (-len(self.data) % 4))
        if len(self.data) + len(data) > MAX_GLB:
            raise ModError('GLB export exceeds 512 MiB.', 'size_limit')
        view = dict(buffer=0, byteOffset=len(self.data), byteLength=len(data))
        if target is not None:
            view['target'] = target
        self.data.extend(data)
        self.document['bufferViews'].append(view)
        return len(self.document['bufferViews']) - 1

    def accessor(self, values, kind, component=5126, target=34962, bounds=False):
        values = np.ascontiguousarray(values)
        acc = dict(bufferView=self.view(values.tobytes(), target), componentType=component,
                   count=len(values), type=kind)
        if bounds:
            acc.update(min=values.min(0).tolist(), max=values.max(0).tolist())
        self.document['accessors'].append(acc)
        return len(self.document['accessors']) - 1

    def glb(self):
        self.document['buffers'] = [dict(byteLength=len(self.data))]
        js = json.dumps(self.document, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
        js += b' ' * (-len(js) % 4)
        self.data.extend(b'\0' * (-len(self.data) % 4))
        size = 12 + 8 + len(js) + 8 + len(self.data)
        if size > MAX_GLB:
            raise ModError('GLB export exceeds 512 MiB.', 'size_limit')
        return (struct.pack('<4sII', b'glTF', 2, size) + struct.pack('<II', len(js), 0x4E4F534A) + js
                + struct.pack('<II', len(self.data), 0x004E4942) + self.data)


def encode(model, name='Model', texture_provider=None, vertex_ids=False):
    """Return a self-contained GLB and an export report from a Character/GameModel."""
    count = len(model.P0)
    if not 1 <= count <= MAX_VERTICES:
        raise ModError('Model must have 1 to 5000000 vertices.', 'size_limit')
    p = array(model.P0, (count, 3), '<f4', 'positions')
    n = array(model.N0, (count, 3), '<f4', 'normals')
    uv = array(model.UV, (count, 2), '<f4', 'UV coordinates')
    lengths = np.linalg.norm(n.astype(np.float64), axis=1)
    zero = lengths < 1e-8
    n[zero] = [0, 1, 0]; lengths[zero] = 1
    n = (n / lengths[:, None]).astype('<f4')
    mask = np.asarray(getattr(model, 'skin_mask', np.ones(count, dtype=bool)), dtype=bool)
    if mask.shape != (count,):
        raise ModError('Invalid model skin mask.', 'invalid_data')
    skinned = bool(mask.any())
    document = dict(asset=dict(version='2.0', generator=CREDIT), scene=0, scenes=[dict(nodes=[0])],
                    nodes=[dict(name=str(name), children=[])], meshes=[], materials=[], bufferViews=[], accessors=[])
    binary = Binary(document)
    warnings = ['Game lighting, shaders and animations are not exported.',
                'The rest skeleton uses bone pivots; original bone rotations/roll are not reconstructed.'] if skinned else [
                    'Game lighting, shaders and animations are not exported.']
    if zero.any():
        warnings.append('%d zero-length normals replaced with unit up vectors.' % zero.sum())
    bones = 0
    if skinned:
        bones = len(model.names)
        if not 1 <= bones <= 65535:
            raise ModError('Unsupported skeleton size.', 'size_limit')
        pivots = array(model.pivots, (bones, 3), '<f4', 'bone pivots')
        parents = array(model.parent, (bones,), '<i8', 'bone parents')
        if ((parents < -1) | (parents >= bones)).any() or not np.array_equal(parents, model.parent):
            raise ModError('Invalid bone hierarchy.', 'invalid_data')
        # Reject cycles before computing local transforms; node order need not be parent-first.
        visited = set()
        for i in range(bones):
            chain, at = set(), i
            while at != -1 and at not in visited:
                if at in chain:
                    raise ModError('Cyclic bone hierarchy.', 'invalid_data')
                chain.add(at); at = int(parents[at])
            visited.update(chain)
        rig = len(document['nodes']); document['nodes'].append(dict(name='Skeleton', children=[]))
        document['nodes'][0]['children'].append(rig)
        first = len(document['nodes'])
        bone_ids = getattr(model, 'bone_ids', [])
        for i, parent in enumerate(parents):
            local = pivots[i] - pivots[parent] if parent >= 0 else pivots[i]
            extras = dict(ts3BoneIndex=i)
            if len(bone_ids) == bones:
                extras['ts3BoneId'] = int(bone_ids[i])
            document['nodes'].append(dict(name=str(model.names[i]), translation=local.tolist(), extras=extras))
        for i, parent in enumerate(parents):
            document['nodes'][rig if parent < 0 else first + int(parent)].setdefault('children', []).append(first + i)
        matrices = np.repeat(np.eye(4, dtype='<f4')[None], bones, axis=0)
        matrices[:, :3, 3] = -pivots
        ibm = binary.accessor(matrices.transpose(0, 2, 1), 'MAT4', target=None)
        document['skins'] = [dict(name='Bind pose', joints=list(range(first, first + bones)), skeleton=rig, inverseBindMatrices=ibm)]
        weights = array(model.BW, (count, 4), '<f8', 'bone weights')
        joints_raw = array(model.BI, (count, 4), '<i8', 'bone indices')
        if not np.array_equal(joints_raw, model.BI) or ((weights < 0) | (weights > 1)).any():
            raise ModError('Invalid skin weights or joint indices.', 'invalid_data')
        if (((joints_raw < 0) | (joints_raw >= bones)) & (weights > 0) & mask[:, None]).any():
            raise ModError('Skin references a missing bone.', 'invalid_data')
        joints_raw[weights == 0] = 0
        for slot in range(4):
            for earlier in range(slot):
                same = (joints_raw[:, slot] == joints_raw[:, earlier]) & (weights[:, slot] > 0)
                weights[same, earlier] += weights[same, slot]; weights[same, slot] = 0
        joints_raw[weights == 0] = 0
        weights[~mask] = [1, 0, 0, 0]; joints_raw[~mask] = 0
        sums = weights.sum(1)
        empty = sums == 0
        if (empty & mask).any():
            warnings.append('%d vertices without weights assigned to the first bone.' % (empty & mask).sum())
        weights[empty] = [1, 0, 0, 0]; joints_raw[empty] = 0; sums[empty] = 1
        weights = (weights / sums[:, None]).astype('<f4')
        joints = joints_raw.astype('<u2')
    image_cache, material_map, primitives = {}, {}, {False: [], True: []}
    triangles, exported_vertices, untextured = 0, 0, 0
    for material, indices in model.groups.items():
        raw_indices = np.asarray(indices)
        if raw_indices.size == 0:
            continue
        if (not np.issubdtype(raw_indices.dtype, np.integer) or raw_indices.size % 3
                or (raw_indices < 0).any() or (raw_indices >= count).any()):
            raise ModError('Invalid triangle indices.', 'invalid_data')
        tri = raw_indices.reshape(-1, 3).astype(np.int64)
        skin_tri = mask[tri]
        if (skin_tri.any(1) != skin_tri.all(1)).any():
            raise ModError('Triangle mixes static and skinned vertices.', 'invalid_data')
        if material not in material_map:
            mat = dict(name='Material %s' % material,
                       pbrMetallicRoughness=dict(metallicFactor=0, roughnessFactor=1), doubleSided=True)
            image = texture_provider(material) if texture_provider else model.textures.get(material)
            if image is not None:
                image = np.asarray(image)
                if image.ndim != 3 or image.shape[2] not in (3, 4) or image.dtype != np.uint8:
                    raise ModError('Invalid material image.', 'invalid_data')
                if max(image.shape[:2]) > 8192:
                    raise ModError('Material image exceeds 8192 pixels.', 'size_limit')
                out = io.BytesIO(); Image.fromarray(image).save(out, 'PNG'); png = out.getvalue()
                key = hashlib.sha256(png).digest()
                if key not in image_cache:
                    image_id = len(document.setdefault('images', []))
                    document['images'].append(dict(bufferView=binary.view(png), mimeType='image/png'))
                    texture_id = len(document.setdefault('textures', []))
                    document['textures'].append(dict(source=image_id))
                    image_cache[key] = texture_id
                mat['pbrMetallicRoughness']['baseColorTexture'] = dict(index=image_cache[key])
                if image.shape[2] == 4 and (image[:, :, 3] < 255).any():
                    mat.update(alphaMode='MASK', alphaCutoff=0.5)
            else:
                untextured += 1
            material_map[material] = len(document['materials']); document['materials'].append(mat)
        for is_skin in (False, True):
            chosen = tri[skin_tri.all(1) == is_skin]
            if not len(chosen):
                continue
            used, local = np.unique(chosen.ravel(), return_inverse=True)
            attrs = dict(POSITION=binary.accessor(p[used], 'VEC3', bounds=True),
                         NORMAL=binary.accessor(n[used], 'VEC3'), TEXCOORD_0=binary.accessor(uv[used], 'VEC2'))
            if vertex_ids:
                attrs['_TS3_VERTEX'] = binary.accessor(used.astype('<f4'), 'SCALAR')
            if is_skin:
                attrs.update(JOINTS_0=binary.accessor(joints[used], 'VEC4', component=5123),
                             WEIGHTS_0=binary.accessor(weights[used], 'VEC4'))
            primitive = dict(attributes=attrs, indices=binary.accessor(local.astype('<u4'), 'SCALAR', component=5125, target=34963),
                             material=material_map[material], mode=4)
            primitives[is_skin].append(primitive)
            triangles += len(chosen); exported_vertices += len(used)
    if not triangles:
        raise ModError('No triangles to export.', 'unsupported_format')
    for is_skin, items in primitives.items():
        if not items:
            continue
        mesh = len(document['meshes']); document['meshes'].append(dict(name='Skinned' if is_skin else 'Static', primitives=items))
        node = dict(name='Skinned geometry' if is_skin else 'Static geometry', mesh=mesh)
        if is_skin:
            node['skin'] = 0
        if is_skin:
            document['scenes'][0]['nodes'].append(len(document['nodes']))
        else:
            document['nodes'][0]['children'].append(len(document['nodes']))
        document['nodes'].append(node)
    skipped = int(getattr(model, 'skipped', 0))
    if skipped:
        warnings.append('%d source pieces omitted by the supported geometry reader.' % skipped)
    if untextured:
        warnings.append('%d materials without a supported diffuse map exported as plain white.' % untextured)
    report = dict(vertices=exported_vertices, source_vertices=count, triangles=triangles, bones=bones,
                  materials=len(material_map), images=len(image_cache), materials_without_texture=untextured,
                  pieces_left_out=skipped, warnings=warnings)
    return binary.glb(), report
