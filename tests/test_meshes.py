"""Rigid mesh packs: transforms, correspondence, unchanged regions and transactional restoration."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'kit'), str(ROOT/'tests')]
ENTRY = [sys.executable, '-I', str(ROOT/'kit/cli.py')]
if '--exe' in sys.argv:
    at=sys.argv.index('--exe'); ENTRY=[str(Path(sys.argv[at+1]).resolve())]; del sys.argv[at:at+2]
import meshpack as M
import install
import modstore
import ts3model as T
from modfile import ModError
from octlib import Oct
import test_explorer as F
import test_gltf as G
from test_gltflib import container
import numpy as np


class Meshes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ts3-meshes-'); self.root=Path(self.temp.name)
        self.game=self.root/'game'; (self.game/'assets').mkdir(parents=True); (self.game/'data_dx').mkdir()
        self.archive=self.game/'assets/object.zip'; self.workspace=self.root/'workspace'; self.pack=self.root/'pack'
        self.items,self.tree=F.scene([F.rigid_piece()])
        self.tree[0][1][1][1].append(('BoundingBox', [-.5, -.5, -.5, 1.5, 1.5, .5]))
        self.items['scene.oct']=F.build_oct(self.tree)
        self.items['collision.bin']=b'unchanged collision data'
        self.write()
        self.closed=patch.object(install,'game_running',return_value=False); self.closed.start()

    def tearDown(self): self.closed.stop(); self.temp.cleanup()
    def write(self):
        self.archive.write_bytes(install.write_zip([install.entry(k.encode(),v) for k,v in self.items.items()]))
    def dump(self): return M.dump(self.game,'assets/object.zip','scene.oct',self.workspace)
    def build(self):
        return M.build(self.game,self.workspace,self.pack,mod_id='test.rigid',name='Rigid test',author='keyloor')
    def mutate(self, fn):
        path=self.workspace/'model.glb'; d,b=G.parse(path.read_bytes()); b=bytearray(b); fn(d,b)
        path.write_bytes(container(d,b))
    def attribute(self,d,b,name):
        return G.accessor(d,b,d['meshes'][0]['primitives'][0]['attributes'][name])
    def edit(self): self.mutate(lambda d,b:self.attribute(d,b,'POSITION').__setitem__((1,0),2.0))

    def test_no_edit_is_not_a_pack_and_export_is_read_only(self):
        before=self.archive.read_bytes(); result=self.dump()
        self.assertEqual(result['vertices'],3); self.assertEqual(self.archive.read_bytes(),before)
        with self.assertRaises(ModError) as e:self.build()
        self.assertEqual(e.exception.code,'nothing_changed'); self.assertFalse(self.pack.exists())

    def test_position_pack_preserves_indices_collisions_materials_and_restores_exactly(self):
        before=self.archive.read_bytes(); self.dump(); self.edit(); result=self.build()
        self.assertEqual(result['vertices_changed'],1); self.assertEqual(result['bounds_expanded'],1)
        store=modstore.Store(self.game); store.install(str(self.pack))
        self.assertTrue(store.verify('test.rigid')['valid'])
        changed={e['name'].decode():install.unpack(e) for e in install.read_zip(self.archive.read_bytes())}
        self.assertEqual(changed['collision.bin'],self.items['collision.bin'])
        self.assertEqual(changed['scene_0.ibuf'],self.items['scene_0.ibuf'])
        original=Oct.parse(self.items['scene.oct']); edited=Oct.parse(changed['scene.oct'])
        self.assertEqual(len(original.recs),len(edited.recs))
        for a,b in zip(original.recs,edited.recs):
            if original.nm(a.name)!='BoundingBox':self.assertEqual(a.pay,b.pay)
        positions=np.frombuffer(changed['scene_0.vbuf'],np.dtype([('p','<f4',3),('uv','<f2',2)]),3)['p']
        self.assertEqual(positions[1,0],2)
        store.remove('test.rigid'); self.assertEqual(self.archive.read_bytes(),before)

    def test_uv_and_normals_update_in_the_original_layout(self):
        self.dump()
        def mutate(d,b):
            self.attribute(d,b,'TEXCOORD_0')[1]=[.75,.125]
            self.attribute(d,b,'NORMAL')[1]=[1,0,0]
        self.mutate(mutate); s=M.source(self.game,'assets/object.zip','scene.oct')
        edits,_=M.rewrite(s,self.workspace/'model.glb'); raw=edits['scene_0.vbuf']
        uv=np.frombuffer(raw,np.dtype([('p','<f4',3),('uv','<f2',2)]),3)['uv']
        normal=np.frombuffer(raw,'<f2',12,48).reshape(3,4)
        np.testing.assert_array_equal(uv[1],[.75,.125]);np.testing.assert_array_equal(normal[1,:3],[1,0,0])
        self.assertNotIn('scene.oct',edits)

    def test_nonuniform_transformed_piece_maps_back_to_local_coordinates(self):
        matrix=F.IDENTITY.copy();matrix[0]=2.;matrix[5]=3.;matrix[12]=10.
        node=self.tree[0][1][1][1]
        for i,(name,value) in enumerate(node):
            if name=='LocalToParentMatrix':node[i]=(name,matrix)
        self.items['scene.oct']=F.build_oct(self.tree);self.write();self.dump()
        with self.assertRaises(ModError) as e:self.build()
        self.assertEqual(e.exception.code,'nothing_changed')
        self.mutate(lambda d,b:self.attribute(d,b,'POSITION').__setitem__((1,0),14.))
        s=M.source(self.game,'assets/object.zip','scene.oct');edits,_=M.rewrite(s,self.workspace/'model.glb')
        positions=np.frombuffer(edits['scene_0.vbuf'],np.dtype([('p','<f4',3),('uv','<f2',2)]),3)['p']
        self.assertEqual(positions[1,0],2.)

    def test_missing_or_unknown_ids_are_not_guessed_by_vertex_order(self):
        self.dump(); original=(self.workspace/'model.glb').read_bytes()
        self.mutate(lambda d,b:d['meshes'][0]['primitives'][0]['attributes'].pop('_TS3_VERTEX'))
        with self.assertRaises(ModError) as e:self.build()
        self.assertEqual(e.exception.code,'missing_correspondence')
        (self.workspace/'model.glb').write_bytes(original)
        self.mutate(lambda d,b:self.attribute(d,b,'_TS3_VERTEX').__setitem__((0,0),99))
        with self.assertRaises(ModError) as e:self.build()
        self.assertEqual(e.exception.code,'topology_changed')

    def test_topology_changes_are_refused_before_output(self):
        self.dump()
        def mutate(d,b):
            index=d['meshes'][0]['primitives'][0]['indices'];G.accessor(d,b,index)[0,0]=1
        self.mutate(mutate)
        with self.assertRaises(ModError) as e:self.build()
        self.assertEqual(e.exception.code,'topology_changed'); self.assertFalse(self.pack.exists())

    def test_duplicate_faces_and_split_vertex_conflicts_are_refused(self):
        self.dump()
        self.mutate(lambda d,b:d['meshes'][0]['primitives'].append(copy.deepcopy(d['meshes'][0]['primitives'][0])))
        with self.assertRaises(ModError) as e:self.build()
        self.assertEqual(e.exception.code,'topology_changed')

    def test_shared_buffer_instances_cannot_disagree(self):
        second=F.rigid_piece(geometry_at=(4,0,0)); _,tree=F.scene([F.rigid_piece(),second])
        # Make the second piece reference the first piece's streams/indices (an actual instance).
        node=tree[0][1][-1][1]
        for i,(key,value) in enumerate(node):
            if key=='VertexStreamReferences':node[i]=(key,[0,1])
            if key=='IndexStreamReference':node[i]=(key,[0])
        self.items['scene.oct']=F.build_oct(tree);self.write();self.dump()
        self.mutate(lambda d,b:self.attribute(d,b,'POSITION').__setitem__((1,0),2.))
        with self.assertRaises(ModError) as e:self.build()
        self.assertEqual(e.exception.code,'shared_vertex_conflict')

    def test_hidden_shared_stream_is_protected(self):
        _,tree=F.scene([F.rigid_piece(),F.rigid_piece(hidden=True)])
        node=tree[0][1][-1][1]
        for i,(key,value) in enumerate(node):
            if key=='VertexStreamReferences':node[i]=(key,[0,1])
        self.items['scene.oct']=F.build_oct(tree);self.write();self.dump();self.edit()
        with self.assertRaises(ModError) as e:self.build()
        self.assertEqual(e.exception.code,'shared_vertex_conflict')

    def test_changed_source_and_workspace_traversal_are_refused(self):
        self.dump();self.edit();self.items['new.bin']=b'changed';self.write()
        with self.assertRaises(ModError) as e:self.build()
        self.assertEqual(e.exception.code,'source_changed')
        index=self.workspace/'mesh.json';d=json.loads(index.read_text());d['model']='../outside.glb';index.write_text(json.dumps(d))
        with self.assertRaises(ModError):M.workspace(self.workspace)

    def test_existing_and_in_game_destinations_are_refused(self):
        self.dump()
        with self.assertRaises(ModError):M.dump(self.game,'assets/object.zip','scene.oct',self.workspace)
        with self.assertRaises(ModError):M.dump(self.game,'assets/object.zip','scene.oct',self.game/'new')
        with self.assertRaises(ModError):M.build(self.game,self.workspace,self.workspace/'pack',mod_id='x.y',name='X',author='Y')

    def test_skin_and_position_only_collision_are_refused(self):
        for piece,bones,remaps in [(F.skinned_piece(),[('Bone',10,None)],[[10]]),(F.rigid_piece(bare=True),[],[])]:
            self.items,_=F.scene([piece],bones,remaps);self.write()
            with self.assertRaises(ModError) as e:self.dump()
            self.assertEqual(e.exception.code,'unsupported_format')

    def test_source_race_never_publishes_a_partial_workspace(self):
        actual=M.signature;calls=[]
        def changed(path):
            calls.append(path);value=actual(path);return value if len(calls)<3 else [value[0]+1,*value[1:]]
        with patch.object(M,'signature',side_effect=changed),self.assertRaises(ModError):self.dump()
        self.assertFalse(self.workspace.exists())

    def test_shared_instances_accept_the_same_local_edit(self):
        _,tree=F.scene([F.rigid_piece(),F.rigid_piece(geometry_at=(4,0,0))])
        node=tree[0][1][-1][1]
        for i,(key,value) in enumerate(node):
            if key=='VertexStreamReferences':node[i]=(key,[0,1])
            if key=='IndexStreamReference':node[i]=(key,[0])
        self.items['scene.oct']=F.build_oct(tree);self.write();self.dump()
        self.mutate(lambda d,b:self.attribute(d,b,'POSITION').__setitem__((slice(None),1),
                    self.attribute(d,b,'POSITION')[:,1]+.25))
        result=self.build();self.assertEqual(result['vertices_changed'],6)

    def test_mirrored_source_transform_stays_in_local_space(self):
        node=self.tree[0][1][1][1];matrix=F.IDENTITY.copy();matrix[0]=-2.
        for i,(key,value) in enumerate(node):
            if key=='LocalToParentMatrix':node[i]=(key,matrix)
        self.items['scene.oct']=F.build_oct(self.tree);self.write();self.dump()
        self.mutate(lambda d,b:self.attribute(d,b,'POSITION').__setitem__((1,0),-4.))
        s=M.source(self.game,'assets/object.zip','scene.oct');edits,_=M.rewrite(s,self.workspace/'model.glb')
        pos=np.frombuffer(edits['scene_0.vbuf'],np.dtype([('p','<f4',3),('uv','<f2',2)]),3)['p']
        self.assertEqual(pos[1,0],2.)

    def test_storage_overflow_is_refused_without_pack(self):
        self.dump();self.mutate(lambda d,b:self.attribute(d,b,'TEXCOORD_0').__setitem__((1,0),1e20))
        with self.assertRaises(ModError):self.build()
        self.assertFalse(self.pack.exists())

    def test_cli_dump_build_and_json_errors(self):
        env=dict(os.environ,TS3TOOL_SETTINGS=str(self.root/'settings.json'))
        def cli(*args):
            p=subprocess.run(ENTRY+['meshes',*map(str,args),'--game',str(self.game),'--json'],capture_output=True,text=True,env=env)
            return p,json.loads(p.stdout)
        p,r=cli('dump','assets/object.zip','--member','scene.oct','--out',self.workspace)
        self.assertEqual(p.returncode,0,r);self.assertEqual(r['command'],'meshes.dump')
        self.edit();p,r=cli('build',self.workspace,'--out',self.pack,'--id','test.rigid','--name','Rigid','--author','keyloor')
        self.assertEqual(p.returncode,0,r);self.assertEqual(r['data']['vertices_changed'],1)
        p,r=cli('dump','assets/object.zip','--member','scene.oct','--out',self.workspace)
        self.assertEqual(p.returncode,3);self.assertEqual(r['error']['code'],'destination_exists')

    def test_preserve_mode_expands_sphere_and_oriented_bounds_too(self):
        self.tree[0][1][1][1].extend([('BoundingSphereCenter',[0.,0.,0.]),('BoundingSphereRadius',[1.]),
            ('BoundingOBBCenter',[0.,0.,0.]),('BoundingOBBExtents',[1.,1.,1.]),
            ('BoundingOBBOrientation',[1.,0.,0.,0.,1.,0.,0.,0.,1.])])
        self.items['scene.oct']=F.build_oct(self.tree);self.write();self.dump();self.edit()
        s=M.source(self.game,'assets/object.zip','scene.oct');edits,_=M.rewrite(s,self.workspace/'model.glb')
        f=Oct.parse(edits['scene.oct']);node=T.pool(f,'SceneTreeNodePool')[1]
        self.assertGreaterEqual(T.field(f,node,'BoundingSphereRadius')[0],2)
        self.assertGreaterEqual(T.field(f,node,'BoundingOBBExtents')[0],2)


if __name__=='__main__':unittest.main()
