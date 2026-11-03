"""Replace a 2D DDS image while preserving its header, dimensions and mip count."""
import io
import struct

from PIL import Image
from modfile import ModError


def layout(raw):
    if len(raw) < 128 or raw[:4] != b'DDS ' or struct.unpack_from('<I', raw, 4)[0] != 124:
        raise ModError('Not a supported DDS texture.', 'unsupported_format')
    height, width = struct.unpack_from('<II', raw, 12)
    depth, count = struct.unpack_from('<II', raw, 24)
    pfsize, flags, fourcc, bits, r, g, b, a = struct.unpack_from('<8I', raw, 76)
    caps2 = struct.unpack_from('<I', raw, 112)[0]
    if pfsize != 32 or depth > 1 or caps2 or not 1 <= width <= 8192 or not 1 <= height <= 8192:
        raise ModError('Only 2D DDS textures up to 8192 pixels can be edited.', 'unsupported_format')
    count = max(1, count)
    if count > max(width, height).bit_length():
        raise ModError('Invalid DDS mip count.', 'invalid_data')
    masks = (r, g, b, a)
    if flags & 4 and fourcc.to_bytes(4, 'little') in (b'DXT1', b'DXT3', b'DXT5'):
        fmt = fourcc.to_bytes(4, 'little').decode('ascii')
    elif flags & 64 and not flags & 4 and bits == 32:
        byte_masks = {255 << (8 * i) for i in range(4)}
        if any(m not in byte_masks for m in masks[:3]) or len(set(masks[:3])) != 3 or (a and (a not in byte_masks or a in masks[:3])):
            raise ModError('Unsupported DDS channel masks.', 'unsupported_format')
        if struct.unpack_from('<I', raw, 20)[0] not in (0, width * 4):
            raise ModError('Padded DDS rows cannot be edited yet.', 'unsupported_format')
        fmt = 'RGBA32' if a else 'RGBX32'
    else:
        raise ModError('Editing supports DXT1, DXT3, DXT5 and 32-bit RGB(A) DDS.', 'unsupported_format')
    levels, w, h = [], width, height
    for _ in range(count):
        size = ((w + 3) // 4) * ((h + 3) // 4) * (8 if fmt == 'DXT1' else 16) if fmt.startswith('DXT') else w * h * 4
        levels.append((w, h, size))
        w, h = max(1, w // 2), max(1, h // 2)
    if len(raw) != 128 + sum(s for _, _, s in levels):
        raise ModError('DDS payload size does not match its mip levels.', 'unsupported_format')
    return dict(width=width, height=height, mipmaps=count, format=fmt, masks=masks, levels=levels)


def replace(raw, image):
    info = layout(raw)
    if image.size != (info['width'], info['height']):
        raise ModError('Keep the original texture dimensions: %d x %d.' % (info['width'], info['height']), 'size_mismatch')
    image = image.convert('RGBA')
    body = []
    for w, h, size in info['levels']:
        level = image if image.size == (w, h) else image.resize((w, h), Image.Resampling.LANCZOS)
        if info['format'].startswith('DXT'):
            buf = io.BytesIO()
            level.save(buf, 'DDS', pixel_format=info['format'])
            encoded = buf.getvalue()[128:]
        else:
            import numpy as np
            pixels = np.asarray(level)
            packed = np.zeros((h, w, 4), dtype='uint8')
            for channel, mask in enumerate(info['masks']):
                if mask:
                    packed[:, :, (mask.bit_length() - 1) // 8] = pixels[:, :, channel]
            encoded = packed.tobytes()
        if len(encoded) != size:
            raise ModError('DDS encoder produced the wrong mip size.', 'invalid_data')
        body.append(encoded)
    result = raw[:128] + b''.join(body)
    layout(result)
    return result
