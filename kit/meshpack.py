"""Same-topology rigid mesh workspaces. Writes data-only packs, never the game."""
from collections import Counter
import copy
import hashlib
import json
import re
from pathlib import Path
import tempfile
import uuid

import numpy as np
import paths  # noqa: F401
from about import CREDIT
from explorer import Browser, directory, signature
import gltf
from gltflib import Scene
from modfile import ModError, game_path, inside, json_bytes, relative, validate
from octlib import Oct
import texpack as TP
import ts3model as T
from viewer import GameModel, ELEMENT, PIECES, _texture

MAX_VERTICES = 250000


def fail(message, code='invalid_data'):
    raise ModError(message, code)


def source(game, archive, member):
    browser = Browser(game)
    archive, member = game_path(archive), relative(member)
    if not archive.lower().endswith('.zip') or not member.lower().endswith('.oct'):
        fail('Choose a game ZIP and one OCT member.', 'unsupported_format')
    file = browser.source(archive); before = signature(file)
    if file.stat().st_size > TP.MAX_ARCHIVE: fail('Mesh archive exceeds 512 MiB.', 'size_limit')
    digest = TP.fingerprints(file)[0]
    members = {e['member'].casefold(): e['member'] for e in directory(file)}
    member = members.get(member.casefold(), member)
    raw = browser.read(archive, member); f = Oct.parse(raw); buffers = {}
    folder = member.rpartition('/')[0]
    def read(name):
        if name is None: return None
        wanted = relative((folder+'/' if folder else '') + relative(name))
        actual = members.get(wanted.casefold())
        if actual is None: return None
        if actual not in buffers:
            buffers[actual] = browser.read(archive, actual)
            if sum(map(len, buffers.values())) > 512*1024*1024:
                fail('Model buffers exceed 512 MiB.', 'size_limit')
        return buffers[actual]
    model = GameModel(raw, read, textures=False, provenance=True)
    if len(model.P0) > MAX_VERTICES: fail('Editable mesh limit is 250000 vertices per OCT.', 'size_limit')
    model.source_blocks = [b for b in model.source_blocks if b['nodes']]
    if model.skin_mask.any() or any(b['bare'] for b in model.source_blocks):
        fail('This workspace supports visible rigid meshes only; use character identity mode for skins.', 'unsupported_format')
    if any(not np.isfinite(b['matrix']).all() or abs(np.linalg.det(b['matrix']))<1e-12
           or not np.allclose(b['matrix'][:, 3], [0, 0, 0, 1], atol=1e-8, rtol=0)
           for b in model.source_blocks):
        fail('Collapsed or non-affine transforms cannot be edited.', 'unsupported_format')
    if signature(file) != before: fail('Source archive changed during reading.', 'source_changed')
    names = []
    for i in T.pool(f, 'VertexBufferPool'):
        name = T.field(f, i, 'FileName', [None])[0]
        names.append(members.get(relative((folder+'/' if folder else '')+relative(name)).casefold()) if name else None)
    return dict(browser=browser, archive=archive, member=member, file=file, signature=before, sha256=digest,
                raw=raw, oct=f, buffers=buffers, names=names, model=model)


def dump(game, archive, member, output, *, piece=None):
    s = source(game, archive, member); model, f = s['model'], s['oct']
    from meshtopo import target
    if piece is not None:
        target(s,piece)
        info=model.source_pieces[piece]; model=copy.copy(model)
        model.groups={info['material']:info['tri'].ravel()};model.pieces=1
    output = TP.output_folder(game, output)
    texs = T.pool(f, 'TexturePool') if f.find('TexturePool') else []
    mats = T.pool(f, 'MaterialPool') if f.find('MaterialPool') else []
    def texture(material):
        return _texture(f, texs, mats[material], None, {}) if 0 <= material < len(mats) else None
    payload, report = gltf.encode(model, Path(member).stem, texture, vertex_ids=True)
    index = dict(schema_version=1, workspace_id=uuid.uuid4().hex, archive=s['archive'], member=s['member'],
                 archive_sha256=s['sha256'], oct_sha256=TP.sha(s['raw']), vertices=len(model.P0),
                 triangles=model.triangles, model='model.glb')
    if piece is not None:
        info=s['model'].source_pieces[piece]
        index.update(piece=piece,vertices=len(np.unique(info['tri'])),triangles=len(info['tri']))
    with tempfile.TemporaryDirectory(prefix='.ts3-mesh-', dir=output.parent) as tmp:
        stage = Path(tmp)/'workspace'; stage.mkdir()
        (stage/'model.glb').write_bytes(payload)
        (stage/'mesh.json').write_bytes(json_bytes(index))
        (stage/'report.json').write_bytes(json_bytes(report))
        (stage/'README.txt').write_text(CREDIT + '\n\n'
            'Edit model.glb, then build a mesh pack from this workspace. Keep game exports local.\n'
            'Only rigid visible geometry, same triangles and vertex correspondence. No subdivision, remesh,\n'
            'decimation, added/deleted faces or vertices. Preserve the _TS3_VERTEX point attribute.\n'
            'Blender export: enable Data > Mesh > Attributes. Keep triangulation unchanged.\n'
            'Positions, normals and first UVs can change. Original materials/textures, indices, hidden pieces,\n'
            'collisions and gameplay stay; material edits in GLB are ignored. Collisions do not follow shape edits.\n'
            'Shared buffer instances must agree; conflicting edits are refused. Bounds expand, never shrink.\n'
            'Preserve mode refuses missing IDs/topology changes. Explicit --topology replace supports one visible\n'
            'lit rigid piece with one material, up to 65535 vertices. Use --piece NODE for compound models.\n'
            'A selected-piece workspace requires replace mode; its node is recorded in mesh.json.\n'
            'It appends separate streams, keeping original buffer data and collisions. No game writes.\n', encoding='utf-8')
        if signature(s['file']) != s['signature']: fail('Source changed during export.', 'source_changed')
        TP.publish(stage, output)
    return dict(output=str(output), **index, pieces_left_out=model.skipped)


def workspace(folder):
    folder = Path(folder).resolve(); file = inside(folder, 'mesh.json')
    if file.stat().st_size > 1024*1024: fail('Oversized mesh index.', 'size_limit')
    data = json.loads(file.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or data.get('schema_version') != 1: fail('Unsupported mesh workspace.')
    if not isinstance(data.get('workspace_id'), str) or not re.fullmatch('[0-9a-f]{32}', data['workspace_id']):
        fail('Invalid mesh workspace ID.')
    for key in ('archive_sha256', 'oct_sha256'):
        if not isinstance(data.get(key), str) or len(data[key]) != 64 or any(c not in '0123456789abcdef' for c in data[key]):
            fail('Invalid source hash in mesh workspace.')
    if any(not isinstance(data.get(k), str) for k in ('archive', 'member', 'model')):
        fail('Missing mesh source/model paths.')
    if 'piece' in data and (type(data['piece']) is not int or data['piece']<0):
        fail('Invalid selected piece in mesh workspace.')
    game_path(data['archive']); relative(data['member']); relative(data['model'])
    return folder, data


def pieces(game, folder):
    folder,index=workspace(folder)
    s=source(game,index['archive'],index['member'])
    if s['sha256']!=index['archive_sha256'] or TP.sha(s['raw'])!=index['oct_sha256']:
        fail('Source changed since export. Export a fresh workspace.', 'source_changed')
    return list_pieces(game,index['archive'],index['member'],snapshot=s)


def list_pieces(game, archive, member, *, snapshot=None):
    from meshtopo import pieces as rows
    s=snapshot if snapshot is not None else source(game,archive,member)
    return dict(archive=s['archive'],member=s['member'],pieces=rows(s))


def faces(tri):
    return Counter(map(tuple, np.sort(np.asarray(tri).reshape(-1, 3), axis=1).tolist()))


def imported(path, model):
    scene = Scene(path); n = len(model.P0)
    p, normal, uv = np.zeros((n, 3)), np.zeros((n, 3)), np.zeros((n, 2))
    seen, triangles = np.zeros(n, bool), []
    for mesh in scene.meshes():
        if mesh['skin'] is not None: fail('Rigid mesh edits must not have a skin.', 'unsupported_format')
        ids = mesh.get('ts3_vertices')
        if ids is None: fail('Missing _TS3_VERTEX. Preserve mesh Attributes when exporting.', 'missing_correspondence')
        if (ids >= n).any(): fail('Vertex correspondence is outside the original mesh.', 'topology_changed')
        nn = mesh['normals'][0].reshape(-1, 3); uu = mesh['uv'][0].reshape(-1, 2).copy(); uu[:, 1] = 1-uu[:, 1]
        # An editor may split vertices at seams. Duplicates must still describe the same original vertex.
        for j, i in enumerate(ids):
            if seen[i] and (not np.allclose(p[i], mesh['pos'][j], atol=1e-6, rtol=0)
                           or not np.allclose(normal[i], nn[j], atol=2e-6, rtol=0)
                           or not np.allclose(uv[i], uu[j], atol=2e-7, rtol=0)):
                fail('A split/shared vertex has conflicting edits: %d' % i, 'shared_vertex_conflict')
            p[i], normal[i], uv[i], seen[i] = mesh['pos'][j], nn[j], uu[j], True
        triangles.append(ids[mesh['tri']])
    original_tri = np.concatenate(list(model.groups.values())).reshape(-1, 3)
    if not seen.all() or not triangles or faces(np.concatenate(triangles)) != faces(original_tri):
        fail('Triangle topology or vertex correspondence changed. Keep the original triangulation.', 'topology_changed')
    return p, normal, uv, original_tri


def unit(values):
    return values/np.maximum(np.linalg.norm(values, axis=1, keepdims=True), 1e-12)


def rewrite(s, path):
    model, f = s['model'], s['oct']
    p, normal, uv, tri = imported(path, model)
    dp = np.max(np.abs(p-model.P0), axis=1)>1e-6
    dn = np.max(np.abs(normal-model.N0), axis=1)>2e-6
    du = np.max(np.abs(uv-model.UV), axis=1)>2e-7
    changed = dp | dn | du
    if not changed.any(): fail('No geometry, normal or UV edits were found.', 'nothing_changed')
    # Rebuild tangent frames on incident faces; all other stored fields stay byte-identical.
    a, b, c = tri.T; e1, e2 = p[b]-p[a], p[c]-p[a]; d1, d2 = uv[b]-uv[a], uv[c]-uv[a]
    det = d1[:, 0]*d2[:, 1]-d2[:, 0]*d1[:, 1]; det = np.where(abs(det)<1e-12, 1e-12, det)
    tt = (e1*d2[:, 1:2]-e2*d1[:, 1:2])/det[:, None]
    bb = (e2*d1[:, 0:1]-e1*d2[:, 0:1])/det[:, None]
    tangent, bitangent = np.zeros_like(p), np.zeros_like(p)
    for col in range(3): np.add.at(tangent, tri[:, col], tt); np.add.at(bitangent, tri[:, col], bb)
    tangent = unit(tangent-normal*(tangent*normal).sum(1, keepdims=True))
    bad = np.linalg.norm(tangent, axis=1)<.5
    tangent[bad] = unit(np.cross(normal[bad], [0, 0, 1])+1e-6)
    binormal = np.cross(tangent, normal); binormal[(binormal*bitangent).sum(1)<0] *= -1
    frame = np.zeros(len(p), bool); frame[np.unique(tri[changed[tri].any(1)])] = True
    claims, moved = {}, {}
    nodes = T.pool(f, 'SceneTreeNodePool')
    exported = {k for block in model.source_blocks for k in block['nodes']}
    for block in model.source_blocks:
        ids = np.flatnonzero((model.source_vertices>=block['start']) &
                             (model.source_vertices<block['start']+block['count']))
        local_ids = model.source_vertices[ids]-block['start']
        matrix = block['matrix']; inv = np.linalg.inv(matrix)
        if not np.isfinite(inv).all(): fail('Invalid source transform.')
        values = dict(Position=(p[ids]-matrix[3, :3])@inv[:3, :3], Normal=unit(normal[ids]@matrix[:3, :3].T),
                      Tangent=unit(tangent[ids]@inv[:3, :3]), Binormal=unit(binormal[ids]@inv[:3, :3]),
                      Uv1=uv[ids], BaseUV=uv[ids])
        masks = dict(Position=dp[ids], Normal=dn[ids], Tangent=frame[ids], Binormal=frame[ids],
                     Uv1=du[ids], BaseUV=du[ids] if 'Uv1' not in block['have'] else np.zeros(len(ids), bool))
        if dn[ids].any() and 'Normal' not in block['have']: fail('This source has no writable normals.', 'unsupported_format')
        if du[ids].any() and not any(k in block['have'] for k in ('Uv1', 'BaseUV')):
            fail('This source has no writable first UV set.', 'unsupported_format')
        for name, stream in block['have'].items():
            if name not in values: continue
            kind, offset = stream['els'][name]; fmt, width = ELEMENT[kind]
            allowed = (2,) if name == 'Position' else (3, 44) if name in ('Uv1', 'BaseUV') else (2, 45)
            if masks[name].any() and kind not in allowed:
                fail('Unsupported editable element format: '+name, 'unsupported_format')
            columns = 2 if name in ('Uv1', 'BaseUV') else 3
            if width < columns or offset<0 or offset+np.dtype(fmt).itemsize*width>stream['stride']:
                fail('Unsupported editable vertex layout.', 'unsupported_format')
            file = s['names'][stream['buf']]
            if file is None: fail('Missing external vertex buffer.', 'unsupported_format')
            raw = s['buffers'][file]; size = np.dtype(fmt).itemsize*columns
            if masks[name].any():
                for other, (other_kind, other_offset) in stream['els'].items():
                    if other != name:
                        if other_kind not in ELEMENT: fail('Unknown aliased element layout.', 'unsupported_format')
                        other_fmt, other_width = ELEMENT[other_kind]
                        if offset < other_offset+np.dtype(other_fmt).itemsize*other_width and other_offset < offset+size:
                            fail('Overlapping stream elements are not editable.', 'unsupported_format')
                # Do not change buffer regions also consumed by unsupported/hidden pieces.
                for k, node in enumerate(nodes):
                    if k not in exported and T.field(f, node, 'Type', [''])[0] in PIECES:
                        refs = T.field(f, node, 'VertexStreamReferences', [])
                        streams = T.pool(f, 'VertexStreamPool')
                        for ref in refs:
                            record = streams[ref]
                            start = T.field(f, record, 'VertexBufferOffset', [0])[0]
                            stop = start+T.field(f, record, 'Length', [0])[0]*(T.field(f, record, 'Width', [0])[0]
                                         +T.field(f, record, 'ExtraStride', [0])[0])
                            if (T.field(f, record, 'VertexBufferReference', [0])[0] == stream['buf']
                                and start < stream['off']+stream['stride']*stream['len'] and stream['off'] < stop):
                                fail('An unexported piece shares this vertex stream.', 'shared_vertex_conflict')
            for j, local in enumerate(local_ids):
                at = int(stream['off']+int(local)*stream['stride']+offset)
                if at<0 or at+size>len(raw): fail('Vertex write exceeds the source buffer.')
                payload = raw[at:at+size]
                if masks[name][j]:
                    with np.errstate(over='ignore', invalid='ignore'):
                        encoded = np.asarray(values[name][j], dtype=fmt)
                    if not np.isfinite(encoded).all(): fail('Edited vertex exceeds game storage precision.')
                    payload = encoded.tobytes()
                key = (file, at, size)
                if key in claims and claims[key] != payload:
                    fail('Shared buffer instances need the same local-space edit.', 'shared_vertex_conflict')
                claims[key] = payload
        if dp[ids].any():
            stored=values['Position'][dp[ids]].astype('<f4').astype(float)
            for k in block['nodes']: moved[k]=stored@matrix[:3,:3]+matrix[3,:3]
    edits, ends = {}, {}
    for (file, at, size), payload in sorted(claims.items()):
        if at < ends.get(file, 0): fail('Overlapping vertex layouts are not supported.', 'unsupported_format')
        ends[file] = at+size
        if payload != s['buffers'][file][at:at+size]:
            if file not in edits: edits[file] = bytearray(s['buffers'][file])
            edits[file][at:at+size] = payload
    result = {name: bytes(data) for name, data in edits.items()}
    from meshtopo import expand_bounds
    expanded=expand_bounds(f,moved)
    oct_bytes = f.to_bytes()
    if Oct.parse(oct_bytes).to_bytes() != oct_bytes: fail('Edited OCT failed its roundtrip.')
    if oct_bytes != s['raw']: result[s['member']] = oct_bytes
    if not result: fail('Edits round to the original game values.', 'nothing_changed')
    return result, dict(vertices_changed=int(changed.sum()), bounds_expanded=expanded, files=list(result))


def build(game, folder, output, *, mod_id, name, author, version='1.0.0', model=None, topology='preserve', piece=None):
    if topology not in ('preserve', 'replace'): fail('Topology mode must be preserve or replace.', 'invalid_arguments')
    folder, index = workspace(folder)
    if topology!='replace' and (piece is not None or index.get('piece') is not None):
        fail('Selected-piece workspaces/--piece require --topology replace.', 'invalid_arguments')
    output = TP.output_folder(game, output)
    if output.resolve().is_relative_to(folder): fail('Build the pack outside the mesh workspace.', 'invalid_path')
    meta = validate(dict(schema_version=1, id=mod_id, name=name, author=author, version=version,
                         description='Rigid mesh edits for Toy Story 3.', credits=[CREDIT],
                         game='ts3-pc', patches=[{'manifest':'patches/manifest.txt'}]))
    if any('\n' in value or '\r' in value for value in (name, author)):
        fail('Use single-line names and credits.', 'invalid_arguments')
    s = source(game, index['archive'], index['member'])
    if s['sha256'] != index['archive_sha256'] or TP.sha(s['raw']) != index['oct_sha256']:
        fail('Source changed since export. Export a fresh workspace.', 'source_changed')
    path = Path(model).absolute() if model else inside(folder, index['model'])
    if topology == 'replace':
        from meshtopo import rewrite as replace_topology
        replacements, report = replace_topology(s, path, piece if piece is not None else index.get('piece'))
    else:
        replacements, report = rewrite(s, path)
        report['topology'] = 'preserve'
    original = s['file'].read_bytes()
    if TP.sha(original) != s['sha256']: fail('Source changed while building.', 'source_changed')
    blob, lines, after = TP.patch_archive(original, replacements)
    with tempfile.TemporaryDirectory(prefix='.ts3-meshpack-', dir=output.parent) as tmp:
        stage = Path(tmp)/'pack'; (stage/'patches').mkdir(parents=True)
        (stage/'patches/mesh.bin').write_bytes(blob)
        (stage/'patches/mesh.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
        (stage/'patches/manifest.txt').write_text('%s|mesh|%s|%s\n' %
            (s['archive'], hashlib.md5(original).hexdigest(), hashlib.md5(after).hexdigest()), encoding='utf-8')
        (stage/'mod.json').write_bytes(json_bytes(meta))
        (stage/'report.json').write_bytes(json_bytes(report))
        (stage/'README.txt').write_text(name+'\nby '+author+'\n\n'+CREDIT+
            '\n\nRigid geometry edit. Original collisions and materials stay.\n'
            'Install/remove this folder with the Mod Loader or Modding Tool.\n', encoding='utf-8')
        if signature(s['file']) != s['signature']: fail('Source changed before publishing.', 'source_changed')
        TP.publish(stage, output)
    return dict(output=str(output), metadata=meta, **report)
