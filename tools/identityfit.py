"""Explicit original-skeleton fitting. The normal converter path never calls this module."""
import numpy as np


class IdentityError(ValueError):
    pass


def mapping(scene, bones, tolerance=1e-5):
    """Match source joints to target BoneIDs or exact names, then validate pivots and hierarchy."""
    if not hasattr(scene, 'identity_joints'):
        raise IdentityError('Original-skeleton mode requires a GLB/glTF source.')
    source = scene.identity_joints()
    if not source or not bones:
        raise IdentityError('Original-skeleton mode needs source and target joints.')
    byid = {b['id']: b for b in bones}
    byname = {b['name']: b for b in bones}
    bynode = {b['node']: b for b in bones}
    if len(byid) != len(bones) or len(byname) != len(bones):
        raise IdentityError('Target bone names and BoneIDs must be unique.')
    matched, used, error, by_id = {}, set(), 0.0, 0
    for joint in source:
        if joint['id'] is not None:
            if type(joint['id']) is not int:
                raise IdentityError('Source ts3BoneId must be an integer: ' + joint['name'])
            target = byid.get(joint['id']); by_id += 1
        else:
            target = byname.get(joint['name'])
        if target is None:
            raise IdentityError('Source joint has no original game bone: ' + joint['name'])
        if target['id'] in used:
            raise IdentityError('More than one source joint maps to ' + target['name'])
        used.add(target['id'])
        delta = float(np.linalg.norm(np.asarray(joint['pivot']) - np.asarray(target['pivot'])))
        if not np.isfinite(delta) or delta > tolerance:
            raise IdentityError('Source joint moved away from its original pivot: %s (%.7g m)' % (joint['name'], delta))
        error = max(error, delta); matched[joint['node']] = (joint, target)
    for joint, target in matched.values():
        source_parent = matched.get(joint['parent'])
        source_parent = source_parent[1]['id'] if source_parent else None
        parent = bynode.get(target['parent']); seen = set()
        while parent is not None and parent['id'] not in used:
            if parent['id'] in seen:
                raise IdentityError('Target bone hierarchy is cyclic.')
            seen.add(parent['id']); parent = bynode.get(parent['parent'])
        if source_parent != (parent['id'] if parent else None):
            raise IdentityError('Source joint hierarchy changed: ' + joint['name'])
    names = {j['name']: b['name'] for j, b in matched.values()}
    return names, dict(joints=len(names), matched_by_id=by_id, matched_by_name=len(names)-by_id,
                      max_pivot_error=error, tolerance=tolerance)


def fit(scene, mesh, bones, options, log):
    names, report = mapping(scene, bones)
    if getattr(options, 'WEIGHTS', None) != names:
        raise IdentityError('Identity map does not match the original skeleton. Regenerate it with --remap.')
    p = np.asarray(mesh['pos'], dtype=np.float64).copy()
    if not np.isfinite(p).all():
        raise IdentityError('Source geometry contains nonfinite positions.')
    mg = mesh.get('mg', np.eye(4))
    if not np.allclose(mg, np.eye(4), atol=1e-8):
        raise IdentityError('Identity source geometry must already be in world space.')
    n = len(p); weights = {}
    for cluster in mesh['skin'] or []:
        if not len(cluster['idx']):
            continue
        target = names.get(cluster['bone'])
        if target is None:
            raise IdentityError('Weighted source bone has no original mapping: ' + cluster['bone'])
        indices, values = np.asarray(cluster['idx']), np.asarray(cluster['w'])
        if (not np.issubdtype(indices.dtype, np.integer) or (indices < 0).any() or (indices >= n).any()
                or values.shape != indices.shape or not np.isfinite(values).all() or (values < 0).any()):
            raise IdentityError('Invalid source skin weights.')
        row = weights.setdefault(target, np.zeros(n))
        np.add.at(row, indices, values)
    if not weights:
        raise IdentityError('Identity source has no skin weights.')
    total, influences = np.zeros(n), np.zeros(n, int)
    for row in weights.values():
        total += row; influences += row > 0
    if not np.allclose(total, 1, atol=1e-6, rtol=0):
        raise IdentityError('Identity weights must sum to one on every source vertex.')
    if (influences > 4).any():
        raise IdentityError('Original-skeleton mode supports at most four distinct influences per vertex.')
    for row in weights.values(): row /= total
    log('identity: %d original joints, max pivot error %.7g m; no proportion fitting' %
        (report['joints'], report['max_pivot_error']))
    return p, np.repeat(np.eye(3)[None], n, 0), np.eye(3), weights
