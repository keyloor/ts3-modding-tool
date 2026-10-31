"""Close-up of a converted character from several angles: python angles.py <dir> <base> <texture | oct> <out.png> cx cy cz size [yaw ...]"""
import os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as RD

d, base, texp, out = sys.argv[1:5]
cx, cy, cz, size = map(float, sys.argv[5:9])
yaws = [float(a) for a in sys.argv[9:]] or [0, 35, 70]
parts, _, f = RD.load_mesh(d, base)
if texp == 'oct':
    tex = RD.oct_textures(f)
else:
    tex = np.asarray(Image.open(texp).convert('RGB').resize((2048, 2048))).astype(np.float32)
ims = []
for yaw in yaws:
    a = np.radians(yaw)
    R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    c = np.array([cx, cy, cz])
    rp = [(((P - c) @ R.T + c).astype(np.float32), (N @ R.T).astype(np.float32), UV, T, m) for P, N, UV, T, m in parts]
    img, _ = RD.raster(rp, 'front', tex, bounds=(np.array([cx - size / 2, cy - size / 2]), np.array([cx + size / 2, cy + size / 2])))
    ims.append(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)))
canvas = Image.new('RGB', (RD.W * len(ims), RD.W), 'white')
for k, im in enumerate(ims):
    canvas.paste(im, (k * RD.W, 0))
canvas.save(out); print('saved', out)
