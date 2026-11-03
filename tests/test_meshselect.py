"""Explicit rigid piece selection: compound sources, shared streams, scoped export and CLI."""
import json,os,sys,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'kit'),str(ROOT/'tests')]
ENTRY=[sys.executable,'-I',str(ROOT/'kit/cli.py')]
if '--exe' in sys.argv:
    at=sys.argv.index('--exe');ENTRY=[str(Path(sys.argv[at+1]).resolve())];del sys.argv[at:at+2]
import test_meshtopo as F
import test_explorer as E
import meshpack as M
import meshtopo as MT
from modfile import ModError
from gltflib import Scene
from octlib import Oct
import ts3model as T
import numpy as np


class Selection(unittest.TestCase):
    setUp=F.Topology.setUp
    tearDown=F.Topology.tearDown
    write=F.Topology.write
    source=F.Topology.source
    view=F.Topology.view

    def compound(self,shared=False):
        self.items,self.tree=E.scene([E.rigid_piece(),E.rigid_piece(geometry_at=(0,0,0) if shared else (3,0,0))])
        for key,value in self.tree[0][1][-1][1]:
            if key=='MaterialReference':value[0]=7
            if shared and key=='VertexStreamReferences':value[:]=[0,1]
            if shared and key=='IndexStreamReference':value[0]=0
        self.write();self.workspace=self.root/'compound';M.dump(self.game,'assets/object.zip','scene.oct',self.workspace)

    def replace(self,piece):
        s=self.source();edits,report=MT.rewrite(s,self.model,piece)
        return s,edits,report

    def test_list_uses_stable_node_ids_even_with_duplicate_names(self):
        self.compound();rows=M.pieces(self.game,self.workspace)['pieces']
        self.assertEqual([r['node'] for r in rows],[2,4]);self.assertEqual([r['material'] for r in rows],[0,7])
        self.assertEqual([r['name'] for r in rows],['piece','piece'])
        self.assertTrue(all(r['supported_layout'] for r in rows))
        self.assertEqual([r['vertices'] for r in rows],[3,3])

    def test_explicit_second_piece_preserves_first_geometry_and_materials(self):
        self.compound();s,edits,report=self.replace(4);after=Oct.parse(edits['scene.oct'])
        nodes=T.pool(after,'SceneTreeNodePool')
        self.assertEqual(T.field(after,nodes[2],'VertexStreamReferences'),[0,1])
        self.assertEqual(T.field(after,nodes[2],'IndexStreamReference'),[0])
        self.assertEqual(T.field(after,nodes[4],'MaterialReference'),[7])
        self.assertEqual(T.field(after,nodes[4],'VertexStreamReferences'),[4,5])
        self.assertEqual((report['piece_node'],report['pieces_preserved']),(4,1))
        self.assertEqual((report['vertices_before'],report['vertices_after']),(3,4))
        self.assertEqual((report['model_triangles_before'],report['model_triangles_after']),(2,3))
        old=s['model'].source_pieces[2]['tri'];checked=M.GameModel(edits['scene.oct'],
            lambda n:edits.get(n,self.items.get(n)),textures=False,provenance=True)
        np.testing.assert_array_equal(s['model'].P0[old],checked.P0[checked.source_pieces[2]['tri']])

    def test_shared_visible_instances_are_detached_only_for_selected_piece(self):
        self.compound(shared=True);s,edits,report=self.replace(2)
        self.assertEqual(len(s['model'].source_blocks),1)
        self.assertEqual(report['model_vertices_after'],7)
        checked=M.GameModel(edits['scene.oct'],lambda n:edits.get(n,self.items.get(n)),textures=False,provenance=True)
        np.testing.assert_array_equal(checked.P0[checked.source_pieces[4]['tri']],s['model'].P0[s['model'].source_pieces[4]['tri']])
        for file in ('scene_0.vbuf','scene_0.ibuf'):self.assertTrue(edits[file].startswith(self.items[file]))

    def test_scoped_export_contains_only_selected_piece_and_records_default(self):
        self.compound();folder=self.root/'selected';result=M.dump(self.game,'assets/object.zip','scene.oct',folder,piece=4)
        self.assertEqual((result['piece'],result['vertices'],result['triangles']),(4,3,1))
        scene=Scene(folder/'model.glb');self.assertEqual(scene.summary()['triangles'],1)
        mesh=next(scene.meshes());self.assertGreaterEqual(mesh['pos'][:,0].min(),3)
        report=M.build(self.game,folder,self.pack,mod_id='test.selected',name='Selected',author='keyloor',
                       topology='replace',model=self.model)
        self.assertEqual(report['piece_node'],4)
        with self.assertRaises(ModError) as e:
            M.build(self.game,folder,self.root/'invalid',mod_id='test.x',name='X',author='Y')
        self.assertEqual(e.exception.code,'invalid_arguments')

    def test_invalid_hidden_and_non_piece_selectors_are_refused(self):
        self.compound()
        for node,code in [(-1,'invalid_arguments'),('2','invalid_arguments'),(999,'piece_not_found'),(1,'piece_not_found')]:
            with self.subTest(node=node),self.assertRaises(ModError) as e:self.replace(node)
            self.assertEqual(e.exception.code,code)
        for key,value in self.tree[0][1][3][1]:
            if key=='Visible':value[0]=0
        self.write()
        with self.assertRaises(ModError) as e:self.replace(4)
        self.assertEqual(e.exception.code,'piece_not_found')

    def test_other_piece_unsupported_layout_is_retained(self):
        self.compound();record=self.tree[1][1][2][1]
        elements=next(v for k,v in record if k=='Elements')
        elements.append(('Element',[('Type',[25]),('Name','Color'),('Offset',[12])]))
        self.write();rows=MT.pieces(self.source())
        self.assertTrue(rows[0]['supported_layout']);self.assertFalse(rows[1]['supported_layout'])
        self.replace(2)
        with self.assertRaisesRegex(ModError,'Color'):self.replace(4)

    def test_piece_with_preserve_and_stale_workspace_are_refused(self):
        self.compound()
        with self.assertRaises(ModError) as e:
            M.build(self.game,self.workspace,self.pack,mod_id='test.x',name='X',author='Y',piece=4)
        self.assertEqual(e.exception.code,'invalid_arguments')
        self.items['new.bin']=b'stale';self.write()
        with self.assertRaises(ModError) as e:M.pieces(self.game,self.workspace)
        self.assertEqual(e.exception.code,'source_changed')

    def test_cli_discovers_exports_and_replaces_selected_piece(self):
        self.compound();env=dict(os.environ,TS3TOOL_SETTINGS=str(self.root/'settings.json'))
        def cli(*args):
            p=subprocess.run(ENTRY+['meshes',*map(str,args),'--game',str(self.game),'--json'],capture_output=True,text=True,env=env)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr);return json.loads(p.stdout)['data']
        rows=cli('pieces','assets/object.zip','--member','scene.oct')['pieces']
        self.assertEqual([r['node'] for r in rows],[2,4])
        self.assertEqual(cli('pieces',self.workspace)['pieces'],rows)
        folder=self.root/'cli-selected';cli('dump','assets/object.zip','--member','scene.oct','--piece',4,'--out',folder)
        report=cli('build',folder,'--topology','replace','--model',self.model,'--out',self.pack,
                   '--id','test.cli-select','--name','Selected','--author','keyloor')
        self.assertEqual(report['piece_node'],4)


if __name__=='__main__':unittest.main()
