"""glTF input, scene transforms, skinning, resources and project-owned texture extraction."""
import base64
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'kit'), str(ROOT / 'tests')]
ENTRY = [sys.executable, '-I', str(ROOT / 'kit/cli.py')]
if '--exe' in sys.argv:
    at = sys.argv.index('--exe'); ENTRY = [str(Path(sys.argv[at+1]).resolve())]; del sys.argv[at:at+2]
import gltf
from gltflib import Scene
import objlib
import kit as K
import convert as CV
from modfile import ModError
import test_gltf as F
import numpy as np
from PIL import Image


def container(doc, binary):
    js = json.dumps(doc).encode(); js += b' ' * (-len(js) % 4)
    binary += b'\0' * (-len(binary) % 4)
    return (struct.pack('<4sII', b'glTF', 2, 28 + len(js) + len(binary)) + struct.pack('<II', len(js), 0x4e4f534a)
            + js + struct.pack('<II', len(binary), 0x004e4942) + binary)


class GLTFInput(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ts3-gltf-input-'); self.root = Path(self.tmp.name)
        self.path = self.root / 'model.glb'
        self.raw, _ = gltf.encode(F.model(skinned=True), 'Source')
        self.path.write_bytes(self.raw)

    def tearDown(self): self.tmp.cleanup()

    def rewrite(self, mutate):
        doc, binary = F.parse(self.raw); mutate(doc)
        self.path.write_bytes(container(doc, binary))

    def test_exported_glb_preserves_bind_geometry_uv_weights_and_scene_contract(self):
        obj = F.model(skinned=True)
        scene = objlib.open_scene(str(self.path)); meshes = list(scene.meshes())
        self.assertEqual((scene.summary()['joints'], len(meshes)), (2, 1))
        mesh = meshes[0]
        np.testing.assert_allclose(mesh['pos'], obj.P0)
        np.testing.assert_allclose(mesh['uv'][0].reshape(-1, 2)[:, 1], 1-obj.UV[:, 1])
        for cluster in mesh['skin']:
            np.testing.assert_allclose(cluster['xf'] @ cluster['xlink'], np.eye(4), atol=1e-6)
        real = [c for c in mesh['skin'] if len(c['idx'])]
        self.assertEqual(len(real), 2)
        np.testing.assert_allclose(real[0]['w'], .5)
        merged = CV.merge_meshes(scene, type('Map', (), {'SKIP_MATERIALS': []}), lambda *a: None)
        np.testing.assert_allclose(merged['pos'], obj.P0)
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_skin_uses_joint_pose_and_ignores_mesh_node_transform(self):
        def mutate(d):
            joints = d['skins'][0]['joints']
            d['nodes'][joints[1]]['translation'] = [0, 2, 0]
            next(n for n in d['nodes'] if 'skin' in n)['translation'] = [100, 0, 0]
        self.rewrite(mutate)
        mesh = next(Scene(self.path).meshes())
        np.testing.assert_allclose(mesh['pos'], F.model(skinned=True).P0 + [0, .5, 0])

    def test_eight_source_weight_slots_combine_duplicate_joint_influences(self):
        def mutate(d):
            attrs=d['meshes'][0]['primitives'][0]['attributes']
            attrs['JOINTS_1']=attrs['JOINTS_0'];attrs['WEIGHTS_1']=attrs['WEIGHTS_0']
        self.rewrite(mutate);mesh=next(Scene(self.path).meshes())
        real=[c for c in mesh['skin'] if len(c['idx'])]
        self.assertEqual(len(real),2)
        for c in real:np.testing.assert_allclose(c['w'],.5)

    def test_nonuniform_skin_transform_uses_inverse_transpose_normals(self):
        obj=F.model(skinned=True);obj.N0=np.tile([1,1,1],(3,1))
        raw,_=gltf.encode(obj);d,binary=F.parse(raw)
        d['nodes'][d['skins'][0]['joints'][0]]['scale']=[2,1,1]
        self.path.write_bytes(container(d,binary));mesh=next(Scene(self.path).meshes())
        expected=np.array([.5,1,1]);expected/=np.linalg.norm(expected)
        np.testing.assert_allclose(mesh['normals'][0].reshape(-1,3),np.tile(expected,(3,1)),atol=1e-7)

    def test_converter_fit_and_vertex_builder_keep_adapter_geometry_and_top_left_uv(self):
        obj=F.model(skinned=True)
        names=['Hips','Spine','Chest','Head']
        obj.names=names;obj.parent=np.array([-1,0,1,2]);obj.pivots=np.array([[0,i,0] for i in range(4)])
        obj.BI=np.tile([0,1,2,3],(3,1));obj.BW=np.full((3,4),.25);obj.bone_ids=list(range(4))
        raw,_=gltf.encode(obj);self.path.write_bytes(raw)
        scene=Scene(self.path)
        mp=SimpleNamespace(SKIP_MATERIALS=[],SCALE_JOINTS=[(n,n) for n in names],
                           LANDMARKS=[(n,n) for n in names],TORSO=names,
                           DRIVE={},WEIGHTS={n:n for n in names},FACE=False,FACE_BONES=set())
        mesh=CV.merge_meshes(scene,mp,lambda *a:None)
        bones=[dict(name=n,id=i,pivot=[0,i,0]) for i,n in enumerate(names)]
        pos,rot,r0,weights=CV.fit(scene,mesh,bones,mp,lambda *a:None)
        vertices,indices=CV.build_vertices(mesh,pos,rot,r0,weights,{n:i for i,n in enumerate(names)})
        np.testing.assert_allclose(vertices['p'],F.model(skinned=True).P0,atol=1e-7)
        np.testing.assert_allclose(vertices['uv'],F.model(skinned=True).UV)
        self.assertEqual(indices.shape,(1,3))

    def test_static_transforms_inverse_transpose_normals_and_mirrored_winding(self):
        raw, _ = gltf.encode(F.model()); d, binary = F.parse(raw)
        node = next(n for n in d['nodes'] if 'mesh' in n)
        node.update(translation=[3, 4, 5], scale=[-2, 3, 1])
        self.path.write_bytes(container(d, binary)); mesh = next(Scene(self.path).meshes())
        np.testing.assert_allclose(mesh['pos'], [[3, 4, 5], [1, 4, 5], [3, 7, 5]])
        a, b, c = mesh['pos'][mesh['tri'][0]]
        self.assertGreater(np.cross(b-a, c-a)[2], 0)
        np.testing.assert_allclose(mesh['normals'][0].reshape(-1, 3), [[0, 0, 1]]*3)
        self.assertEqual(Scene(self.path).summary()['static_meshes'], 1)

    def test_external_gltf_resources_and_data_uris_match_glb(self):
        doc, binary = F.parse(self.raw)
        (self.root / 'nested').mkdir(); (self.root / 'nested/data file.bin').write_bytes(binary)
        doc['buffers'][0]['uri'] = 'nested/data%20file.bin'
        path = self.root / 'model.gltf'; path.write_text(json.dumps(doc), encoding='utf-8')
        scene = Scene(path)
        np.testing.assert_allclose(next(scene.meshes())['pos'], next(Scene(self.path).meshes())['pos'])
        doc['buffers'][0]['uri'] = 'data:application/octet-stream;base64,' + base64.b64encode(binary).decode()
        path.write_text(json.dumps(doc), encoding='utf-8')
        np.testing.assert_allclose(next(Scene(path).meshes())['pos'], F.model(skinned=True).P0)

    def test_external_jpeg_image_is_extracted_as_a_project_png(self):
        doc,binary=F.parse(self.raw)
        doc['buffers'][0]['uri']='data:application/octet-stream;base64,'+base64.b64encode(binary).decode()
        Image.new('RGB',(16,8),(40,100,160)).save(self.root/'body image.jpg')
        doc['images'][0]=dict(uri='body%20image.jpg')
        path=self.root/'model.gltf';path.write_text(json.dumps(doc),encoding='utf-8')
        scene=Scene(path);folder=self.root/'textures';scene.extract_textures(folder)
        with Image.open(next(folder.glob('*.png'))) as image:self.assertEqual(image.size,(16,8))

    def test_resources_cannot_escape_model_folder_or_request_remote_files(self):
        for uri in ('../private.bin', 'https://example.invalid/data.bin', 'file:///C:/secret.bin', '/absolute.bin', 'nested/%2e%2e/%2e%2e/private.bin'):
            doc, _ = F.parse(self.raw); doc['buffers'][0]['uri'] = uri
            path = self.root / 'bad.gltf'; path.write_text(json.dumps(doc), encoding='utf-8')
            with self.subTest(uri=uri), self.assertRaises(ModError): Scene(path)

    def test_sparse_interleaved_and_normalized_accessors(self):
        positions = np.array([[0,0,0],[1,0,0],[0,1,0]], '<f4').tobytes()
        uv = bytes([0,0,0,0,255,0,0,0,0,255,0,0])
        binary = positions + uv + bytes([1,0,0,0]) + np.array([[2,0,0]], '<f4').tobytes()
        doc = dict(asset=dict(version='2.0'), buffers=[dict(byteLength=len(binary))],
            bufferViews=[dict(buffer=0,byteOffset=0,byteLength=36), dict(buffer=0,byteOffset=36,byteLength=12,byteStride=4),
                         dict(buffer=0,byteOffset=48,byteLength=1),dict(buffer=0,byteOffset=52,byteLength=12)],
            accessors=[dict(bufferView=0,componentType=5126,count=3,type='VEC3',sparse=dict(count=1,
                           indices=dict(bufferView=2,componentType=5121),values=dict(bufferView=3))),
                       dict(bufferView=1,componentType=5121,count=3,type='VEC2',normalized=True)],
            nodes=[dict(mesh=0)], meshes=[dict(primitives=[dict(attributes=dict(POSITION=0,TEXCOORD_0=1))])])
        self.path.write_bytes(container(doc,binary)); scene=Scene(self.path); mesh=next(scene.meshes())
        np.testing.assert_allclose(mesh['pos'], [[0,0,0],[2,0,0],[0,1,0]])
        np.testing.assert_allclose(mesh['uv'][0].reshape(-1,2), [[0,1],[1,1],[0,0]])
        doc['accessors'][0]['sparse']['indices']['byteOffset']=100
        self.path.write_bytes(container(doc,binary))
        with self.assertRaises(ModError): Scene(self.path)

    def test_malformed_bounds_cycles_morphs_and_required_extensions_fail_cleanly(self):
        changes = [lambda d:d['accessors'][0].update(count=1000000000),
                   lambda d:d['bufferViews'][0].update(byteLength=1000000000),
                   lambda d:d['nodes'][0].update(children=[0]),
                   lambda d:d.update(extensionsRequired=['KHR_draco_mesh_compression']),
                   lambda d:d['meshes'][0]['primitives'][0].update(targets=[{}]),
                   lambda d:d.update(asset=[])]
        for i, change in enumerate(changes):
            self.rewrite(change)
            with self.subTest(case=i), self.assertRaises(ModError): Scene(self.path)

    def test_base_colour_factor_is_baked_in_linear_space_and_cache_preserves_edits(self):
        obj=F.model(skinned=True); obj.textures[0][:] = [255,255,255,255]
        raw,_=gltf.encode(obj); d,binary=F.parse(raw)
        d['materials'][0]['pbrMetallicRoughness']['baseColorFactor']=[.5,.5,.5,.5]
        self.path.write_bytes(container(d,binary)); scene=Scene(self.path)
        output=self.root/'textures'; scene.extract_textures(output)
        filename=next(iter(scene.pngs))
        with Image.open(output/filename) as image: self.assertEqual(image.getpixel((0,0)),(188,188,188,128))
        scene.extract_textures(output)
        (output/filename).write_bytes(b'user edit')
        with self.assertRaises(ModError): scene.extract_textures(output)
        self.assertEqual((output/filename).read_bytes(),b'user edit')

    def test_prepare_refreshes_generated_textures_but_keeps_explicit_texture_folder(self):
        game=self.root/'game'; (game/'assets/characters').mkdir(parents=True)
        work=self.root/'project'; proj=dict(character='woody',fbx=str(self.path),game=str(game))
        with patch.object(K,'needs_extract',return_value=False):
            K.prepare(str(work),proj,log=lambda *a:None)
            first=proj['textures']; self.assertTrue(Path(first).is_dir())
            self.rewrite(lambda d:d['materials'][0]['pbrMetallicRoughness'].update(baseColorFactor=[.5,1,1,1]))
            K.prepare(str(work),proj,log=lambda *a:None)
            self.assertNotEqual(first,proj['textures'])
            explicit=self.root/'chosen'; explicit.mkdir(); proj['textures']=str(explicit)
            K.prepare(str(work),proj,log=lambda *a:None)
            self.assertEqual(proj['textures'],str(explicit))

    def test_static_gltf_cannot_silently_lose_meshes_during_character_conversion(self):
        raw,_=gltf.encode(F.model(skinned=True,mixed=True)); self.path.write_bytes(raw)
        game=self.root/'game'; (game/'assets/characters').mkdir(parents=True)
        with self.assertRaises(K.KitError) as caught:
            K.prepare(str(self.root/'project'),dict(character='woody',fbx=str(self.path),game=str(game)))
        self.assertEqual(caught.exception.code,'invalid_model')
        self.assertFalse((self.root/'project').exists())

    def test_overlapping_primitives_keep_both_materials(self):
        from autotex import autotex
        obj=F.model(skinned=True);obj.groups[1]=obj.groups[0].copy();obj.textures[1]=obj.textures[0].copy()
        obj.textures[1][:,:,:3]=[0,255,0]
        raw,_=gltf.encode(obj);self.path.write_bytes(raw)
        scene=Scene(self.path);folder=self.root/'textures';scene.extract_textures(folder)
        sets,materials,skip,_,_=autotex(str(self.path),str(folder),lambda *a:None)
        self.assertEqual(len(sets),2);self.assertEqual(len(materials),2);self.assertEqual(skip,[])

    def test_explicit_cli_texture_selection_can_use_an_edited_generated_folder(self):
        game=self.root/'game';(game/'assets/characters').mkdir(parents=True)
        work=self.root/'project';proj=dict(character='woody',fbx=str(self.path),game=str(game))
        with patch.object(K,'needs_extract',return_value=False):
            K.prepare(str(work),proj,log=lambda *a:None)
            folder=Path(proj['textures']);png=next(folder.glob('*.png'))
            Image.new('RGB',(16,8),(0,0,255)).save(png)
            def prepare_only(work,project,*args):
                K.prepare(work,project,log=lambda *a:None)
                return []
            args=SimpleNamespace(project=str(work),character=None,fbx=None,textures=str(folder),game=None,
                                 remap=False,force=False,json=True,install=False)
            with patch.object(K,'build',side_effect=prepare_only):K.make(args)
        self.assertNotIn('gltf_textures',K.load_project(str(work)))
        with Image.open(png) as image:self.assertEqual(image.getpixel((0,0)),(0,0,255))

    def test_cli_model_info_without_game_or_settings_writes(self):
        env=dict(os.environ,TS3TOOL_SETTINGS=str(self.root/'settings.json'))
        args=ENTRY+['model-info',str(self.path),'--json']
        result=subprocess.run(args,capture_output=True,encoding='utf-8',timeout=60,env=env,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr); self.assertEqual(result.stderr,'')
        data=json.loads(result.stdout); self.assertEqual(data['command'],'kit.model-info')
        self.assertEqual((data['data']['joints'],data['data']['triangles']),(2,1))
        self.assertFalse((self.root/'settings.json').exists())
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),['model.glb'])

    def test_cli_rejects_remote_resources_with_a_stable_error_and_no_traceback(self):
        doc,_=F.parse(self.raw);doc['buffers'][0]['uri']='https://example.invalid/private.bin'
        path=self.root/'remote.gltf';path.write_text(json.dumps(doc),encoding='utf-8')
        result=subprocess.run(ENTRY+['model-info',str(path),'--json'],capture_output=True,encoding='utf-8',timeout=60,
                              env=dict(os.environ,TS3TOOL_SETTINGS=str(self.root/'settings.json')),
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.assertEqual(result.returncode,3);self.assertEqual(result.stderr,'')
        self.assertEqual(json.loads(result.stdout)['error']['code'],'invalid_path')


if __name__=='__main__': unittest.main()
