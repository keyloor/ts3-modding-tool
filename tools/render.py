"""Preview a Toy Story 3 character file (.oct + buffers): front and side views, game skeleton pivots as red dots.

  python render.py <dir> <base name> <out.png> [texture.png | oct] [--compare <orig dir>]

'oct' takes each piece's diffuse map from the .oct itself (for characters with several materials).
"""
import io, os, sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ts3model as T

W = 520


def load_mesh(d, base):
    f, bones, subs, remaps, ist, vst = T.load(os.path.join(d, base + '.oct'))
    vb = open(os.path.join(d, base + '_0.vbuf'), 'rb').read()
    ib = np.frombuffer(open(os.path.join(d, base + '_0.ibuf'), 'rb').read(), '<u2')
    P, N, UV, tris = [], [], [], []
    base_i = 0
    done = set()
    for s in subs:
        a, b = s['vs'][0], s['vs'][1]
        if (a, b) not in done:
            done.add((a, b))
        st = ist[s['ist']]
        tris.append((ib[st['off'] // 2: st['off'] // 2 + st['len']].reshape(-1, 3).astype(np.int64), a, b, s['mat']))
    # all vertices of every stream pair
    out = []
    for tri, a, b, mat in tris:
        sa, sb = vst[a], vst[b]
        v0 = np.frombuffer(vb, T.S0, sa['len'], sa['off'])
        if sb['width'] == 24:
            n = np.frombuffer(vb, T.S1, sb['len'], sb['off'])['n'][:, :3].astype(np.float32)
        else:
            n = np.zeros((sb['len'], 3), np.float32); n[:, 2] = 1
            raw = np.frombuffer(vb, 'u1', sb['len'] * sb['width'], sb['off']).reshape(sb['len'], sb['width'])
            noff = 0 if sb['width'] == 8 else 4
            n = raw[:, noff:noff + 8].copy().view('<f2')[:, :3].astype(np.float32)
        out.append((v0['p'].astype(np.float32), n, v0['uv'].astype(np.float32), tri, mat))
    return out, bones, f


def oct_textures(f):
    """material index -> its diffuse map (from the .oct's TexturePool) as an array"""
    texs = T.pool(f, 'TexturePool')
    out = {}
    for k, i in enumerate(T.pool(f, 'MaterialPool')):
        for j in range(i, f.end_of(i)):
            if f.nm(f.recs[j].name) == 'TextureEntry' and f.nm(f.recs[j + 2].items()[1][0]) == 'diffuseMapA1':
                data = bytes(f.recs[f.child(texs[f.recs[j + 1].items()[1][0]], 'Data')].items()[1])
                try:
                    out[k] = np.asarray(Image.open(io.BytesIO(data)).convert('RGB')).astype(np.float32)
                except Exception:
                    pass
    return out


def raster(parts, view, tex=None, size=W, bounds=None):
    img = np.full((size, size, 3), 235, np.float32)
    zb = np.full((size, size), -1e9, np.float32)
    lo, hi = bounds
    sc = (size - 20) / max(hi - lo)
    light = np.array([0.4, 0.5, 0.75]); light /= np.linalg.norm(light)
    for P, N, UV, tri, mat in parts:
        ptex = tex.get(mat) if isinstance(tex, dict) else tex
        if view == 'side':
            X, Y, Z = P[:, 2], P[:, 1], -P[:, 0]; NN = np.c_[N[:, 2], N[:, 1], -N[:, 0]]
        else:
            X, Y, Z = P[:, 0], P[:, 1], P[:, 2]; NN = N
        sx = (X - (lo[0] + hi[0]) / 2) * sc + size / 2
        sy = size - 10 - (Y - lo[1]) * sc
        shade = np.clip(NN @ light, 0, 1) * 0.75 + 0.25
        for t in tri:
            xs, ys = sx[t], sy[t]
            x0, x1 = int(max(0, np.floor(xs.min()))), int(min(size - 1, np.ceil(xs.max())))
            y0, y1 = int(max(0, np.floor(ys.min()))), int(min(size - 1, np.ceil(ys.max())))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if abs(d) < 1e-9:
                continue
            w0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d
            w1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d
            w2 = 1 - w0 - w1
            m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not m.any():
                continue
            z = w0 * Z[t[0]] + w1 * Z[t[1]] + w2 * Z[t[2]]
            sub = zb[y0:y1 + 1, x0:x1 + 1]
            m &= z > sub
            if not m.any():
                continue
            sub[m] = z[m]
            sh = w0 * shade[t[0]] + w1 * shade[t[1]] + w2 * shade[t[2]]
            if ptex is not None:
                u = (w0 * UV[t[0], 0] + w1 * UV[t[1], 0] + w2 * UV[t[2], 0]) % 1
                v = (w0 * UV[t[0], 1] + w1 * UV[t[1], 1] + w2 * UV[t[2], 1]) % 1
                c = ptex[(v * (ptex.shape[0] - 1)).astype(int), (u * (ptex.shape[1] - 1)).astype(int)]
            else:
                c = np.full(gx.shape + (3,), 200.0)
            img[y0:y1 + 1, x0:x1 + 1][m] = c[m] * sh[m][:, None]
    return img, sc


def draw(d, base, tex, bounds):
    parts, bones, f = load_mesh(d, base)
    if isinstance(tex, str):
        tex = oct_textures(f)
    views = []
    for view in ('front', 'side'):
        img, sc = raster(parts, view, tex, bounds=bounds)
        im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
        dr = ImageDraw.Draw(im)
        lo, hi = bounds
        for b in bones:
            p = np.array(b['pivot'])
            x = (p[0] if view == 'front' else p[2]) - (lo[0] + hi[0]) / 2 if view == 'front' else p[2] - (lo[0] + hi[0]) / 2
            sx = x * sc + W / 2; sy = W - 10 - (p[1] - lo[1]) * sc
            dr.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(220, 0, 0))
        views.append(im)
    return views


def main():
    d, base, out = sys.argv[1:4]
    tex = None
    rest = sys.argv[4:]
    cmp_dir = None
    if '--compare' in rest:
        cmp_dir = rest[rest.index('--compare') + 1]
        rest = rest[:rest.index('--compare')]
    bounds = (np.array([-1.3, 0.0]), np.array([1.3, 2.0]))
    if '--box' in rest:                                  # --box x0 y0 x1 y1: a close-up
        k = rest.index('--box')
        x0, y0, x1, y1 = map(float, rest[k + 1:k + 5])
        bounds = (np.array([x0, y0]), np.array([x1, y1]))
        rest = rest[:k] + rest[k + 5:]
    if rest and rest[0] == 'oct':
        tex = 'oct'
    elif rest:
        tex = np.asarray(Image.open(rest[0]).convert('RGB').resize((2048, 2048))).astype(np.float32)
    row = draw(d, base, tex, bounds)
    if cmp_dir:
        row = draw(cmp_dir, base, None, bounds) + row
    canvas = Image.new('RGB', (W * len(row), W), 'white')
    for k, im in enumerate(row):
        canvas.paste(im, (k * W, 0))
    canvas.save(out)
    print('saved', out)


if __name__ == '__main__':
    main()
