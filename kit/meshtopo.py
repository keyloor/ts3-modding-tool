"""Explicit topology replacement for one rigid piece. Original buffers and other nodes stay intact."""
import numpy as np
import paths  # noqa: F401
import convert as C
from gltflib import Scene
from modfile import ModError, relative
from octlib import Oct
import ts3model as T
from viewer import ELEMENT, GameModel

MAX_VERTICES = 65535
MAX_TRIANGLES = 1000000
ROLES = {'Position': (2,), 'Normal': (2, 45), 'Tangent': (2, 45), 'Binormal': (2, 45),
         'Uv1': (3, 44), 'BaseUV': (3, 44)}


def fail(message, code='unsupported_format'):
    raise ModError(message, code)


def world(f, nodes, k):
    m, seen = np.eye(4), set()
    while k is not None and 0 <= k < len(nodes) and k not in seen:
        seen.add(k); value = T.field(f, nodes[k], 'LocalToParentMatrix')
        if value is not None: m = m@np.asarray(value).reshape(4, 4)
        k = (T.field(f, nodes[k], 'ParentNodeReferences') or [None])[0]
    if not np.isfinite(m).all() or abs(np.linalg.det(m)) < 1e-12:
        fail('Invalid geometry bounds transform.')
    return m


def expand_bounds(f, moved):
    """Expand AABB, OBB and sphere conservatively; retaining centers also protects omitted original geometry."""
    nodes = T.pool(f, 'SceneTreeNodePool'); changed = set()
    for child, points in moved.items():
        k, seen = child, set()
        while k is not None and 0 <= k < len(nodes) and k not in seen:
            seen.add(k); node = nodes[k]
            inv = np.linalg.inv(world(f, nodes, k)); p = points@inv[:3, :3]+inv[3, :3]
            if f.child(node, 'BoundingSphere') is not None: fail('Unsupported combined BoundingSphere record.')
            def value(name, size):
                index = f.child(node, name)
                if index is None: return None
                data = np.asarray(f.value(index), float)
                if data.shape != (size,) or not np.isfinite(data).all(): fail('Invalid bound: '+name)
                return data
            def grow(name, new, old):
                if not np.array_equal(new, old):
                    with np.errstate(over='ignore'):
                        stored = np.asarray(new, '<f4')
                        # Round outwards so stored bounds contain the requested points.
                        stored = np.nextafter(stored, np.float32(np.inf))
                    if not np.isfinite(stored).all(): fail('Bounds exceed float32 storage.', 'invalid_data')
                    f.recs[f.child(node, name)].set_items(stored.tolist()); changed.add(k)
            box = value('BoundingBox', 6)
            if box is not None:
                if (box[:3]>box[3:]).any(): fail('Invalid bounding box extents.')
                lo, hi = np.minimum(box[:3], p.min(0)), np.maximum(box[3:], p.max(0))
                if not np.array_equal(np.r_[lo, hi], box):
                    stored = np.r_[np.nextafter(lo.astype('<f4'), np.float32(-np.inf)),
                                   np.nextafter(hi.astype('<f4'), np.float32(np.inf))]
                    if not np.isfinite(stored).all(): fail('Bounds exceed float32 storage.', 'invalid_data')
                    f.recs[f.child(node, 'BoundingBox')].set_items(stored.tolist()); changed.add(k)
            center, radius = value('BoundingSphereCenter', 3), value('BoundingSphereRadius', 1)
            if (center is None) != (radius is None): fail('Incomplete sphere bounds.')
            if radius is not None:
                if radius[0] < 0: fail('Negative sphere radius.')
                grow('BoundingSphereRadius', np.maximum(radius, np.linalg.norm(p-center, axis=1).max()), radius)
            center, extents = value('BoundingOBBCenter', 3), value('BoundingOBBExtents', 3)
            if (center is None) != (extents is None): fail('Incomplete oriented bounds.')
            if extents is not None:
                rotation = value('BoundingOBBOrientation', 9)
                rotation = rotation.reshape(3, 3) if rotation is not None else np.eye(3)
                if (extents < 0).any() or not np.allclose(rotation@rotation.T, np.eye(3), atol=1e-5, rtol=0):
                    fail('Unsupported oriented bound axes.')
                # Both matrix conventions are enclosed, without assuming undocumented engine axis order.
                needed = np.maximum(abs((p-center)@rotation).max(0), abs((p-center)@rotation.T).max(0))
                grow('BoundingOBBExtents', np.maximum(extents, needed), extents)
            k = (T.field(f, node, 'ParentNodeReferences') or [None])[0]
    return len(changed)


def target_index(s):
    cached=s.get('_topology_index')
    if cached is None or cached['records']!=len(s['oct'].recs):
        cached=dict(records=len(s['oct'].recs),nodes=T.pool(s['oct'],'SceneTreeNodePool'),
                    streams=T.pool(s['oct'],'VertexStreamPool'),
                    blocks={node:b for b in s['model'].source_blocks for node in b['nodes']})
        s['_topology_index']=cached
    return cached


def target(s, piece=None):
    model, f = s['model'], s['oct']
    visible=model.source_pieces
    if piece is None:
        if len(visible)!=1: fail('Select a visible rigid piece with --piece NODE. List it with meshes pieces.', 'ambiguous_target')
        piece=next(iter(visible))
    if type(piece) is not int or piece<0: fail('Piece must be a nonnegative OCT node index.', 'invalid_arguments')
    if piece not in visible: fail('Selected piece is not visible/exported: %s'%piece, 'piece_not_found')
    indexed=target_index(s);block=indexed['blocks'][piece]
    block=dict(block,nodes=[piece])
    node = indexed['nodes'][piece]
    if T.field(f, node, 'Type', [''])[0] != 'SubGeometryLit': fail('Choose a lit rigid piece.')
    if T.field(f, node, 'SceneComponentReferences', []): fail('Scene-component geometry cannot be replaced yet.')
    streams = indexed['streams']; refs = T.field(f, node, 'VertexStreamReferences', [])
    names = []
    for ref in refs:
        record = streams[ref]; box = f.child(record, 'Elements')
        for element in f.children(box) if box is not None else []:
            name, kind = T.field(f, element, 'Name')[0], T.field(f, element, 'Type')[0]
            if name not in ROLES or kind not in ROLES[name]: fail('Unsupported replacement attribute: '+name)
            names.append(name)
    if len(names) != len(set(names)) or 'Position' not in names or len(set(names)&{'Uv1','BaseUV'})>1:
        fail('Replacement needs a single position/first-UV layout.')
    if set(names) != set(block['have']): fail('Missing replacement stream data.')
    return block, node, refs


def pieces(s):
    result=[]
    for node,info in sorted(s['model'].source_pieces.items()):
        row=dict(node=node,name=info['name'],material=int(info['material']),
                 vertices=len(np.unique(info['tri'])),triangles=len(info['tri']),supported_layout=True,reason=None)
        try: target(s,node)
        except ModError as e: row.update(supported_layout=False,reason=str(e))
        result.append(row)
    return result


def frames(p, n, uv, tri):
    a,b,c = tri.T; e1,e2 = p[b]-p[a],p[c]-p[a]; d1,d2 = uv[b]-uv[a],uv[c]-uv[a]
    det = d1[:,0]*d2[:,1]-d2[:,0]*d1[:,1]; det = np.where(abs(det)<1e-12,1e-12,det)
    tt=(e1*d2[:,1:2]-e2*d1[:,1:2])/det[:,None]
    bb=(e2*d1[:,0:1]-e1*d2[:,0:1])/det[:,None]
    tangent,bitangent=np.zeros_like(p),np.zeros_like(p)
    for col in range(3): np.add.at(tangent,tri[:,col],tt);np.add.at(bitangent,tri[:,col],bb)
    tangent=C.unit(tangent-n*(tangent*n).sum(1,keepdims=True))
    bad=np.linalg.norm(tangent,axis=1)<.5;tangent[bad]=C.unit(np.cross(n[bad],[0,0,1])+1e-6)
    binormal=np.cross(tangent,n);binormal[(binormal*bitangent).sum(1)<0]*=-1
    return tangent,binormal


def rewrite(s, path, piece=None):
    block,node,refs=target(s,piece);f=s['oct']; scene=Scene(path,correspondence=False)
    selected=block['nodes'][0];original_piece=s['model'].source_pieces[selected]
    positions,normals,uvs,triangles,materials=[],[],[],[],set();count=0;nt=0
    for mesh in scene.meshes():
        if mesh['skin'] is not None: fail('Topology replacement must be unskinned.')
        count+=len(mesh['pos']);nt+=len(mesh['tri'])
        if count>MAX_VERTICES or nt>MAX_TRIANGLES: fail('Replacement exceeds 65535 vertices or 1000000 triangles.', 'size_limit')
        materials.update(mesh['matnames'])
        if len(materials)>1: fail('One original piece supports one replacement material only.')
        triangles.append(mesh['tri']+count-len(mesh['pos']));positions.append(mesh['pos'])
        normals.append(mesh['normals'][0].reshape(-1,3));uv=mesh['uv'][0].reshape(-1,2).copy();uv[:,1]=1-uv[:,1];uvs.append(uv)
    if not count or not nt: fail('Replacement geometry is empty.', 'invalid_data')
    p,n,uv,tri=np.concatenate(positions),np.concatenate(normals),np.concatenate(uvs),np.concatenate(triangles)
    if (np.linalg.norm(n,axis=1)<.5).any(): fail('Replacement needs nonzero normals.', 'invalid_data')
    if not any(name in block['have'] for name in ('Uv1','BaseUV')) and abs(uv).max()>1e-7:
        fail('Original piece has no UV stream for the replacement.')
    tangent,binormal=frames(p,n,uv,tri);inv=np.linalg.inv(block['matrix']);linear=block['matrix'][:3,:3]
    values=dict(Position=(p-block['matrix'][3,:3])@inv[:3,:3],Normal=C.unit(n@linear.T),
                Tangent=C.unit(tangent@inv[:3,:3]),Binormal=C.unit(binormal@inv[:3,:3]),Uv1=uv,BaseUV=uv)
    # Scene already resolves glTF transform winding. Keep these world-space face orders on the game node.
    vs_pool=T.pool(f,'VertexStreamPool');is_pool=T.pool(f,'IndexStreamPool')
    vb_pool=T.pool(f,'VertexBufferPool');ib_pool=T.pool(f,'IndexBufferPool')
    buffers={};new_streams=[]
    def raw_append(file,payload,align=4):
        if file not in buffers: buffers[file]=bytearray(s['buffers'][file])
        raw=buffers[file];raw.extend(b'\0'*(-len(raw)%align));offset=len(raw);raw.extend(payload)
        if sum(map(len,buffers.values()))>512*1024*1024: fail('Replacement buffers exceed 512 MiB.', 'size_limit')
        return offset
    for ref in refs:
        record=vs_pool[ref];buf=T.field(f,record,'VertexBufferReference',[0])[0]
        file=s['names'][buf];stride=T.field(f,record,'Width')[0]+T.field(f,record,'ExtraStride',[0])[0]
        length=T.field(f,record,'Length')[0];offset=T.field(f,record,'VertexBufferOffset')[0]
        if file is None or not 1<=stride<=4096 or not length: fail('Unsupported replacement stream.')
        old=s['buffers'][file];rows=np.frombuffer(old,'u1',length*stride,offset).reshape(length,stride)
        packed=np.repeat(rows[:1],count,axis=0).copy();occupied=np.zeros(stride,bool)
        elements=f.children(f.child(record,'Elements'))
        for element in elements:
            name=T.field(f,element,'Name')[0];kind=T.field(f,element,'Type')[0];at=T.field(f,element,'Offset')[0]
            fmt,width=ELEMENT[kind];size=np.dtype(fmt).itemsize*width
            if at<0 or at+size>stride or occupied[at:at+size].any(): fail('Overlapping replacement elements.')
            occupied[at:at+size]=True
            dt=np.dtype({'names':['v'],'formats':[(fmt,(width,))],'offsets':[at],'itemsize':stride})
            dest=np.ndarray((count,),dt,buffer=packed)['v'];old_values=np.ndarray((length,),dt,buffer=rows)['v']
            columns=2 if name in ('Uv1','BaseUV') else 3
            if width>columns and not np.array_equal(old_values[:,columns:],np.repeat(old_values[:1,columns:],length,axis=0)):
                fail('Variable extra vertex components cannot be reconstructed: '+name)
            with np.errstate(over='ignore',invalid='ignore'): encoded=values[name].astype(fmt)
            if not np.isfinite(encoded).all(): fail('Replacement exceeds vertex storage precision.', 'invalid_data')
            dest[:,:columns]=encoded
        if not np.array_equal(rows[:,~occupied],np.repeat(rows[:1,~occupied],length,axis=0)):
            fail('Variable padding/unknown vertex data cannot be reconstructed.')
        stream=C.block(f,record)
        if stream[0].spec[1]: C.set_key(f,stream,str(len(vs_pool)+len(new_streams)))
        C.setv(f,stream,'Length',[count]);C.setv(f,stream,'VertexBufferOffset',[raw_append(file,packed.tobytes())])
        new_streams.append(stream)
    index_ref=T.field(f,node,'IndexStreamReference')[0];record=is_pool[index_ref]
    buf=T.field(f,record,'IndexBufferReference',[0])[0];width=T.field(f,ib_pool[buf],'Width',[2])[0]
    name=T.field(f,ib_pool[buf],'FileName',[None])[0]
    if width not in (1,2,4) or name is None: fail('Unsupported replacement index buffer.')
    if tri.max()>np.iinfo({1:'u1',2:'<u2',4:'<u4'}[width]).max: fail('Replacement exceeds original index width.', 'size_limit')
    folder=s['member'].rpartition('/')[0];wanted=((folder+'/' if folder else '')+relative(name)).casefold()
    file=next((k for k in s['buffers'] if k.casefold()==wanted),None)
    if file is None: fail('Replacement index buffer is missing.')
    stream=C.block(f,record)
    if stream[0].spec[1]: C.set_key(f,stream,str(len(is_pool)))
    C.setv(f,stream,'Length',[tri.size]);C.setv(f,stream,'IndexBufferOffset',
        [raw_append(file,tri.astype({1:'u1',2:'<u2',4:'<u4'}[width]).tobytes(),width)])
    f.recs[f.child(node,'VertexStreamReferences')].set_items(list(range(len(vs_pool),len(vs_pool)+len(new_streams))))
    f.recs[f.child(node,'IndexStreamReference')].set_items([len(is_pool)])
    center=f.child(node,'BoundingCenter')
    if center is not None: f.recs[center].set_items(((values['Position'].min(0)+values['Position'].max(0))*.5).tolist())
    stored_world=values['Position'].astype('<f4').astype(float)@linear+block['matrix'][3,:3]
    expanded=expand_bounds(f,{block['nodes'][0]:stored_world})
    for pool,children in (('VertexStreamPool',new_streams),('IndexStreamPool',[stream])):
        end=f.end_of(f.find(pool)[0]);f.recs[end:end]=[r for child in children for r in child]
    result={k:bytes(v) for k,v in buffers.items()};result[s['member']]=f.to_bytes()
    if Oct.parse(result[s['member']]).to_bytes()!=result[s['member']]: fail('Replacement OCT failed roundtrip.', 'invalid_data')
    def read(name):
        if name is None: return None
        wanted=((folder+'/' if folder else '')+relative(name)).casefold()
        key=next((k for k in s['buffers'] if k.casefold()==wanted),None)
        return result.get(key,s['buffers'].get(key))
    checked=GameModel(result[s['member']],read,textures=False,provenance=True)
    part=checked.source_pieces.get(selected)
    if part is None or len(np.unique(part['tri']))!=count or len(part['tri'])!=nt:
        fail('Replacement geometry failed its stream/count verification.', 'invalid_data')
    for other,old in s['model'].source_pieces.items():
        if other==selected: continue
        after=checked.source_pieces.get(other)
        if (after is None or after['material']!=old['material']
            or not np.array_equal(checked.P0[after['tri']],s['model'].P0[old['tri']])
            or not np.array_equal(checked.UV[after['tri']],s['model'].UV[old['tri']])):
            fail('An unselected piece changed during replacement.', 'invalid_data')
    if checked.triangles!=s['model'].triangles-len(original_piece['tri'])+nt:
        fail('Whole-model triangle verification failed.', 'invalid_data')
    return result,dict(topology='replace',piece_node=selected,piece_name=original_piece['name'],
                       pieces_preserved=len(s['model'].source_pieces)-1,vertices_changed=count,
                       vertices_before=len(np.unique(original_piece['tri'])),vertices_after=count,
                       triangles_before=len(original_piece['tri']),triangles_after=nt,
                       model_vertices_before=len(s['model'].P0),model_vertices_after=len(checked.P0),
                       model_triangles_before=s['model'].triangles,model_triangles_after=checked.triangles,
                       bounds_expanded=expanded,files=list(result))
