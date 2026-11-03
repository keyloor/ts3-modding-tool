"""Optional reinsertion onto a verified original game skeleton, without humanoid fitting."""
import ast
import os
from types import SimpleNamespace

import numpy as np
import paths  # noqa: F401
import automap as AM
import objlib
import ts3model as T
from identityfit import IdentityError, mapping


def mode(proj):
    value = proj.get('fit_mode', 'normal')
    if value not in ('normal', 'identity'):
        raise IdentityError('fit_mode must be normal or identity.')
    if value == 'identity' and not proj.get('fbx', '').lower().endswith(('.glb', '.gltf')):
        raise IdentityError('Original-skeleton mode requires a GLB/glTF source.')
    return value == 'identity'


def check_map(path, expected):
    """Read the mode without executing an advanced map; runtime validation checks the loaded map too."""
    with open(path, encoding='utf-8-sig') as stream:
        tree = ast.parse(stream.read(), filename=path)
    flags = [node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == 'IDENTITY'
             and isinstance(node.ctx, ast.Store)]
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == 'IDENTITY']
    value = False
    if flags:
        if len(flags) != 1 or len(assignments) != 1 or not isinstance(assignments[0].value, ast.Constant) \
                or type(assignments[0].value.value) is not bool:
            raise IdentityError('Map IDENTITY must be a single top-level True/False literal.')
        value = assignments[0].value.value
    if value != expected:
        raise IdentityError('Map fitting mode differs from the project. Regenerate the map with --remap.')


def detect(proj, game_dir, log=print):
    scene = objlib.open_scene(proj['fbx'])
    f, bones, subs, *_ = T.load(os.path.join(game_dir, proj['character'] + '.oct'))
    names, result = mapping(scene, bones)
    joints = scene.identity_joints()
    bynode = {j['node']: j['name'] for j in joints}
    skeleton = SimpleNamespace(pos={j['name']: np.array(j['pivot']) for j in joints},
                               parent={j['name']: bynode.get(j['parent']) for j in joints},
                               skinned=set(names))
    tables = dict(IDENTITY=True, PREFIX='kit', KEEP_PIECES=[], MATERIAL_EFFECT=AM.material_effect(f, subs),
                  TORSO={}, LANDMARKS=[], SCALE_JOINTS=[], FACE_ALIGN=[], DRIVE={}, WEIGHTS=names,
                  FACE_BONES=set(), FACE=False)
    info = dict(identity=result, skeleton=skeleton, body={}, notes={n: 'original game bone' for n in names},
                roles=[], follows={}, neck=None, torso=None, extras=[], eyes={}, face={}, moved={})
    log('original skeleton: %d joints verified (%d by BoneID, %d by name); max pivot error %.7g m' %
        (result['joints'], result['matched_by_id'], result['matched_by_name'], result['max_pivot_error']))
    return tables, info
