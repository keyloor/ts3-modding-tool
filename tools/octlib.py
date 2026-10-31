"""Octane tuple files (.oct/.bent) used by Toy Story 3 -- read and write, byte-exact when unedited.

Header (0x3c bytes): u32 magic 0x45017629, f32 1.1, u32 0, u32 name table size, u32 record data size,
u32 record count, zeros. Then the name table (NUL-terminated Latin-1 strings), then the records.
Record: u16 flag (type = flag & 0x3ff, level = flag >> 10), u16 name index, payload.
Type bits (format as documented by the Disney Infinity community, FORMATS.md):
  0-1 shape (1 node, 2 list, 3 scalar)   2 keyed (payload starts with a u16 name)
  3-5 kind (1 name u16, 2 float32, 3 int, 4 byte)   6-7 count width - 1   8-9 int width - 1
"""
import struct

MAGIC = 0x45017629
HDR = 0x3C
NODE, LIST, SCALAR = 1, 2, 3
NAME, FLOAT, INT, BYTE = 1, 2, 3, 4


def spec(t):
    shape, keyed, kind = t & 3, (t >> 2) & 1, (t >> 3) & 7
    cw, iw = ((t >> 6) & 3) + 1, ((t >> 8) & 3) + 1
    return shape, keyed, kind, cw, iw


def elem_size(kind, iw):
    return {NAME: 2, FLOAT: 4, BYTE: 1, INT: iw}.get(kind, 0)


def paylen(t, b, q):
    shape, keyed, kind, cw, iw = spec(t)
    n = 2 if keyed else 0
    if shape == NODE:
        return n
    es = elem_size(kind, iw)
    if shape == LIST or kind == BYTE:
        cnt = int.from_bytes(b[q + n:q + n + cw], 'little')
        return n + cw + cnt * es
    return n + es


class Rec:
    __slots__ = ('type', 'level', 'name', 'pay')

    def __init__(self, type_, level, name, pay):
        self.type, self.level, self.name, self.pay = type_, level, name, pay

    @property
    def spec(self):
        return spec(self.type)

    def key(self):
        return struct.unpack_from('<H', self.pay, 0)[0] if self.spec[1] else None

    def items(self):
        shape, keyed, kind, cw, iw = self.spec
        q = 2 if keyed else 0
        if shape == NODE:
            return kind, []
        es = elem_size(kind, iw)
        if shape == LIST or kind == BYTE:
            cnt = int.from_bytes(self.pay[q:q + cw], 'little'); q += cw
        else:
            cnt = 1
        raw = self.pay[q:q + cnt * es]
        if kind == BYTE:
            return kind, raw
        if kind == FLOAT:
            return kind, list(struct.unpack('<%df' % cnt, raw))
        if kind == NAME:
            return kind, list(struct.unpack('<%dH' % cnt, raw))
        return kind, [int.from_bytes(raw[i * es:(i + 1) * es], 'little', signed=True) for i in range(cnt)]

    def set_items(self, vals):
        """rewrite the values (same kind); widths grow as needed"""
        shape, keyed, kind, cw, iw = self.spec
        head = self.pay[:2] if keyed else b''
        t = self.type
        if kind == INT:
            need = 1
            for v in vals:
                while not (-(1 << (8 * need - 1)) <= v < (1 << (8 * need - 1))) and need < 4:
                    need += 1
            iw = max(iw, need)
            t = (t & ~0x300) | ((iw - 1) << 8)
            body = b''.join(int(v).to_bytes(iw, 'little', signed=True) if v < (1 << (8 * iw - 1)) else
                            int(v).to_bytes(iw, 'little') for v in vals)
        elif kind == FLOAT:
            body = struct.pack('<%df' % len(vals), *vals)
        elif kind == NAME:
            body = struct.pack('<%dH' % len(vals), *vals)
        else:
            body = bytes(vals)
        if shape == LIST or kind == BYTE:
            while len(vals) >= (1 << (8 * cw)):
                cw += 1
            t = (t & ~0xC0) | ((cw - 1) << 6)
            head += len(vals).to_bytes(cw, 'little')
        elif len(vals) != 1:
            raise ValueError('scalar takes one value')
        self.type, self.pay = t, head + body


class Oct:
    def __init__(self, names, recs, count_field):
        self.names, self.recs, self.count_field = names, recs, count_field
        self._index = {s: i for i, s in enumerate(names)}

    @classmethod
    def parse(cls, b):
        magic, ver, z, nts, rds, cnt = struct.unpack_from('<IfIIII', b, 0)
        if magic != MAGIC:
            raise ValueError('not an Octane tuple file')
        names = b[HDR:HDR + nts].split(b'\0')[:-1]
        names = [s.decode('latin1') for s in names]
        recs = []
        q, end = HDR + nts, HDR + nts + rds
        while q < end:
            flag, ni = struct.unpack_from('<HH', b, q)
            t = flag & 0x3FF
            n = paylen(t, b, q + 4)
            recs.append(Rec(t, flag >> 10, ni, b[q + 4:q + 4 + n]))
            q += 4 + n
        if q != end:
            raise ValueError('records overrun')
        o = cls(names, recs, cnt)
        o._tail = b[end:]
        return o

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as f:
            return cls.parse(f.read())

    def nm(self, i):
        return self.names[i]

    def add_name(self, s):
        if s not in self._index:
            self._index[s] = len(self.names)
            self.names.append(s)
        return self._index[s]

    def to_bytes(self):
        nt = b''.join(s.encode('latin1') + b'\0' for s in self.names)
        rd = b''.join(struct.pack('<HH', (r.level << 10) | r.type, r.name) + r.pay for r in self.recs)
        cnt = len(self.recs) if self.count_field else 0
        hdr = struct.pack('<IfIIII', MAGIC, 1.1, 0, len(nt), len(rd), cnt) + b'\0' * (HDR - 24)
        return hdr + nt + rd + self._tail

    def save(self, path):
        with open(path, 'wb') as f:
            f.write(self.to_bytes())

    # tree helpers
    def end_of(self, i):
        """index just past the subtree of record i"""
        lv = self.recs[i].level
        j = i + 1
        while j < len(self.recs) and self.recs[j].level > lv:
            j += 1
        return j

    def children(self, i):
        lv = self.recs[i].level
        j, end = i + 1, self.end_of(i)
        out = []
        while j < end:
            if self.recs[j].level == lv + 1:
                out.append(j)
            j += 1
        return out

    def child(self, i, name):
        for j in self.children(i):
            if self.nm(self.recs[j].name) == name:
                return j
        return None

    def find(self, name, start=0, end=None):
        end = len(self.recs) if end is None else end
        return [i for i in range(start, end) if self.nm(self.recs[i].name) == name]

    def value(self, i):
        kind, v = self.recs[i].items()
        if kind == NAME:
            return [self.nm(x) for x in v]
        return v

    def describe(self, i):
        r = self.recs[i]
        k = r.key()
        s = '  ' * r.level + self.nm(r.name)
        if k is not None:
            s += '[%s]' % self.nm(k)
        kind, v = r.items()
        if kind == BYTE:
            s += ' <%d bytes>' % len(v)
        elif v:
            vv = [self.nm(x) for x in v] if kind == NAME else v
            s += ' = ' + (repr(vv[:12]) + ('...(%d)' % len(vv) if len(vv) > 12 else ''))
        return s
