"""New rigid topology: append-only buffers, target isolation, source bounds and normal-mode regression."""
import copy,json,os
from pathlib import Path
import subprocess,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'kit'),str(ROOT/'tests')]
ENTRY=[sys.executable,'-I',str(ROOT/'kit/cli.py')]
if '--exe' in sys.argv:
    at=sys.argv.index('--exe');ENTRY=[str(Path(sys.argv[at+1]).resolve())];del sys.argv[at:at+2]
import meshpack as M
import meshtopo as MT
import gltf,install,modstore
import ts3model as T
from octlib import Oct
from modfile import ModError
from viewer import GameModel
from gltflib import Scene
import test_explorer as F
import test_gltf as G
from test_gltflib import container
import numpy as np


def replacement():
    obj=G.model();obj.P0=np.array([[0,0,0],[2,0,0],[0,1,0],[2,1,0]],'<f4')
    obj.N0=np.tile([0,0,1],(4,1));obj.UV=np.array([[0,0],[1,0],[0,1],[1,1]],'<f4')
    obj.skin_mask=np.zeros(4,bool);obj.groups={0:np.array([0,1,2,1,3,2],np.uint32)};obj.textures={}
    return obj


class Topology(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ts3-topology-');self.root=Path(self.temp.name)
        self.game=self.root/'game';(self.game/'assets').mkdir(parents=True);(self.game/'data_dx').mkdir()
        self.archive=self.game/'assets/object.zip';self.workspace=self.root/'workspace';self.pack=self.root/'pack'
        self.items,self.tree=F.scene([F.rigid_piece()]);self.items['collision.bin']=b'original collision bytes'
        self.tree[0][1][1][1].append(('BoundingBox',[-.5,-.5,-.5,1.5,1.5,.5]))
        self.write();M.dump(self.game,'assets/object.zip','scene.oct',self.workspace)
        self.model=self.root/'replacement.glb';self.model.write_bytes(gltf.encode(replacement())[0])

    def tearDown(self):self.temp.cleanup()
    def write(self):
        self.items['scene.oct']=F.build_oct(self.tree)
        self.archive.write_bytes(install.write_zip([install.entry(n.encode(),b) for n,b in self.items.items()]))
    def source(self):return M.source(self.game,'assets/object.zip','scene.oct')
    def rewrite(self):
        s=self.source();edits,report=MT.rewrite(s,self.model)
        return s,edits,report
    def view(self,edits):
        return GameModel(edits['scene.oct'],lambda n:edits.get(n,self.items.get(n)),textures=False)
    def build(self):
        return M.build(self.game,self.workspace,self.pack,mod_id='test.topology',name='Topology',author='keyloor',
                       model=self.model,topology='replace')

    def test_more_vertices_and_triangles_without_correspondence(self):
        s,edits,report=self.rewrite();model=self.view(edits)
        self.assertEqual((len(model.P0),model.triangles),(4,2))
        np.testing.assert_array_equal(model.P0,replacement().P0)
        np.testing.assert_array_equal(np.concatenate(list(model.groups.values())),replacement().groups[0])
        np.testing.assert_array_equal(model.UV,replacement().UV)
        self.assertEqual(report['vertices_before'],3);self.assertEqual(report['triangles_after'],2)
        for name in ('scene_0.vbuf','scene_0.ibuf'):self.assertTrue(edits[name].startswith(self.items[name]))
        f=Oct.parse(edits['scene.oct']);node=T.pool(f,'SceneTreeNodePool')[-1]
        self.assertEqual(T.field(f,node,'VertexStreamReferences'),[2,3])
        self.assertEqual(T.field(f,node,'IndexStreamReference'),[1])
        self.assertEqual(len(T.pool(f,'SceneTreeNodePool')),3)
        self.assertEqual(T.field(f,node,'MaterialReference'),[0])
        for a,b in zip(T.pool(s['oct'],'VertexStreamPool')[:2],T.pool(f,'VertexStreamPool')[:2]):
            self.assertEqual(s['oct'].recs[a].pay,f.recs[b].pay)

    def test_fewer_vertices_and_faces(self):
        # Source is first rebuilt to a four-vertex quad, so replacing it with a triangle reduces both counts.
        _,edits,_=self.rewrite();self.items.update(edits)
        obj=G.model();obj.P0*=.5;self.model.write_bytes(gltf.encode(obj)[0])
        self.tree=None
        self.archive.write_bytes(install.write_zip([install.entry(n.encode(),b) for n,b in self.items.items()]))
        _,edits,report=self.rewrite();self.assertEqual(report['vertices_before'],4)
        self.assertEqual(report['vertices_after'],3)
        self.assertEqual(self.view(edits).triangles,1)

    def test_preserve_default_still_refuses_new_topology(self):
        with self.assertRaises(ModError) as e:
            M.build(self.game,self.workspace,self.pack,mod_id='test.x',name='X',author='Y',model=self.model)
        self.assertEqual(e.exception.code,'missing_correspondence');self.assertFalse(self.pack.exists())

    def test_interpolated_old_correspondence_is_ignored_only_in_replace_mode(self):
        raw,_=gltf.encode(replacement(),vertex_ids=True);d,b=G.parse(raw);b=bytearray(b)
        G.accessor(d,b,d['meshes'][0]['primitives'][0]['attributes']['_TS3_VERTEX'])[0,0]=.5
        self.model.write_bytes(container(d,b))
        with self.assertRaises(ModError):Scene(self.model)
        _,edits,_=self.rewrite();self.assertEqual(self.view(edits).triangles,2)

    def test_multiple_visible_pieces_are_not_guessed(self):
        self.items,self.tree=F.scene([F.rigid_piece(),F.rigid_piece(geometry_at=(3,0,0))]);self.write()
        with self.assertRaises(ModError) as e:self.rewrite()
        self.assertEqual(e.exception.code,'ambiguous_target')

    def test_hidden_shared_piece_stays_on_original_bytes(self):
        self.items,self.tree=F.scene([F.rigid_piece(),F.rigid_piece(hidden=True)])
        node=self.tree[0][1][-1][1]
        for i,(key,value) in enumerate(node):
            if key=='VertexStreamReferences':node[i]=(key,[0,1])
            if key=='IndexStreamReference':node[i]=(key,[0])
        self.write();_,edits,_=self.rewrite();f=Oct.parse(edits['scene.oct'])
        hidden=T.pool(f,'SceneTreeNodePool')[-1]
        self.assertEqual(T.field(f,hidden,'VertexStreamReferences'),[0,1])
        self.assertEqual(T.field(f,hidden,'IndexStreamReference'),[0])
        self.assertTrue(edits['scene_0.vbuf'].startswith(self.items['scene_0.vbuf']))

    def test_nonuniform_mirrored_target_preserves_world_geometry_and_winding(self):
        node=self.tree[0][1][1][1];matrix=F.IDENTITY.copy();matrix[0]=-2.;matrix[5]=3.;matrix[12]=10.
        for i,(key,value) in enumerate(node):
            if key=='LocalToParentMatrix':node[i]=(key,matrix)
        self.write();_,edits,_=self.rewrite();model=self.view(edits)
        np.testing.assert_allclose(model.P0,replacement().P0,atol=1e-6)
        np.testing.assert_array_equal(np.concatenate(list(model.groups.values())),replacement().groups[0])
        np.testing.assert_allclose(model.N0,replacement().N0,atol=.001)

    def test_bounds_box_sphere_and_oriented_box_all_expand(self):
        node=self.tree[0][1][1][1]
        node += [('BoundingSphereCenter',[0.,0.,0.]),('BoundingSphereRadius',[.1]),
                 ('BoundingOBBOrientation',[1.,0.,0.,0.,1.,0.,0.,0.,1.]),('BoundingOBBCenter',[0.,0.,0.]),
                 ('BoundingOBBExtents',[.1,.1,.1])]
        self.write();_,edits,_=self.rewrite();f=Oct.parse(edits['scene.oct']);geo=T.pool(f,'SceneTreeNodePool')[1]
        self.assertGreaterEqual(T.field(f,geo,'BoundingBox')[3],2)
        self.assertGreaterEqual(T.field(f,geo,'BoundingSphereRadius')[0],np.sqrt(5))
        self.assertGreaterEqual(T.field(f,geo,'BoundingOBBExtents')[0],2)
        self.assertGreaterEqual(T.field(f,geo,'BoundingOBBExtents')[1],1)

    def test_variable_unknown_vertex_data_is_refused(self):
        stream=self.tree[1][1][0][1]
        elements=next(v for k,v in stream if k=='Elements')
        elements.append(('Element',[('Type',[25]),('Name','Color'),('Offset',[12])]))
        self.write()
        with self.assertRaisesRegex(ModError,'Color'):self.rewrite()

    def test_multiple_replacement_materials_are_refused(self):
        obj=replacement();obj.groups={0:np.array([0,1,2]),1:np.array([1,3,2])}
        self.model.write_bytes(gltf.encode(obj)[0])
        with self.assertRaisesRegex(ModError,'material'):self.rewrite()

    def test_vertex_limit_and_storage_overflow_do_not_publish(self):
        with patch.object(MT,'MAX_VERTICES',3),self.assertRaises(ModError) as e:self.build()
        self.assertEqual(e.exception.code,'size_limit');self.assertFalse(self.pack.exists())
        obj=replacement();obj.UV[:,0]=1e10;self.model.write_bytes(gltf.encode(obj)[0])
        with self.assertRaisesRegex(ModError,'precision'):self.build()
        self.assertFalse(self.pack.exists())

    def test_byte_index_source_keeps_its_narrower_limit(self):
        for key,value in self.tree[4][1][0][1]:
            if key=='Width':value[0]=1
        self.items['scene_0.ibuf']=np.arange(3,dtype='u1').tobytes();self.write()
        obj=G.model();obj.P0=np.tile(obj.P0,(88,1));obj.N0=np.tile([0,0,1],(264,1))
        obj.UV=np.zeros((264,2));obj.skin_mask=np.zeros(264,bool);obj.groups={0:np.arange(264,dtype=np.uint32)}
        self.model.write_bytes(gltf.encode(obj)[0])
        with self.assertRaises(ModError) as e:self.rewrite()
        self.assertEqual(e.exception.code,'size_limit')

    def test_install_verify_remove_restores_all_original_bytes(self):
        before=self.archive.read_bytes();self.build()
        with patch.object(install,'game_running',return_value=False):
            store=modstore.Store(self.game);store.install(str(self.pack));self.assertTrue(store.verify('test.topology')['valid'])
            rows={e['name'].decode():install.unpack(e) for e in install.read_zip(self.archive.read_bytes())}
            self.assertEqual(rows['collision.bin'],self.items['collision.bin'])
            self.assertEqual(self.view(rows).triangles,2)
            store.remove('test.topology');self.assertEqual(self.archive.read_bytes(),before)

    def test_cli_explicit_topology_mode(self):
        r=subprocess.run(ENTRY+['meshes','build',str(self.workspace),'--model',str(self.model),'--topology','replace',
            '--out',str(self.pack),'--id','test.topology','--name','Topology','--author','keyloor','--game',str(self.game),'--json'],
            capture_output=True,text=True,env=dict(os.environ,TS3TOOL_SETTINGS=str(self.root/'settings.json')))
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);data=json.loads(r.stdout)['data']
        self.assertEqual(data['topology'],'replace');self.assertEqual(data['triangles_after'],2)


if __name__=='__main__':unittest.main()
