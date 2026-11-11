"""Parse MS-OFORMS user form layouts out of a .dvb/.otm VBA storage -> JSON."""
import olefile, struct, sys, json, os

CLS = {7: 'Form', 12: 'Image', 14: 'Frame', 15: 'MorphData', 16: 'SpinButton', 17: 'CommandButton',
       18: 'TabStrip', 21: 'Label', 23: 'TextBox', 24: 'ListBox', 25: 'ComboBox', 26: 'CheckBox',
       27: 'OptionButton', 28: 'ToggleButton', 47: 'ScrollBar', 57: 'MultiPage'}
DISPLAY = {1: 'TextBox', 2: 'ListBox', 3: 'ComboBox', 4: 'CheckBox', 5: 'OptionButton', 6: 'ToggleButton', 7: 'ComboBox'}


class R:
    def __init__(self, b, pos=0):
        self.b, self.p = b, pos

    def u(self, fmt):
        n = struct.calcsize(fmt)
        v = struct.unpack_from('<' + fmt, self.b, self.p)
        self.p += n
        return v[0] if len(v) == 1 else v

    def raw(self, n):
        v = self.b[self.p:self.p + n]
        self.p += n
        return v


class Block:
    """Aligned data block reader: every field aligned to its own size from block start."""
    def __init__(self, r):
        self.r, self.start = r, r.p

    def get(self, n):
        off = (self.r.p - self.start) % n
        if off:
            self.r.p += n - off
        return self.r.u({1: 'B', 2: 'H', 4: 'I'}[n])

    def end(self):
        off = (self.r.p - self.start) % 4
        if off:
            self.r.p += 4 - off


def counted_str(r, cnt, start):
    n = cnt & 0x7FFFFFFF
    comp = cnt & 0x80000000
    raw = r.raw(n)
    off = (r.p - start) % 4
    if off:
        r.p += 4 - off
    if comp:
        return raw.decode('cp949', 'replace')
    return raw.decode('utf-16le', 'replace')


def bits(mask, i):
    return (mask >> i) & 1


def text_props(r):
    ver = r.u('BB')
    cb = r.u('H')
    end = r.p + cb
    mask = r.u('I')
    b = Block(r)
    name_len = b.get(4) if bits(mask, 0) else 0
    effects = b.get(4) if bits(mask, 1) else 0
    height = b.get(4) if bits(mask, 2) else 160
    if bits(mask, 4): b.get(1)
    if bits(mask, 5): b.get(1)
    align = b.get(1) if bits(mask, 6) else 1
    weight = b.get(2) if bits(mask, 7) else 400
    b.end()
    st = r.p
    name = counted_str(r, name_len, st) if name_len else None
    r.p = end
    return {'font': name, 'size_twips': height, 'bold': bool(effects & 1) or weight >= 700,
            'italic': bool(effects & 2), 'align': align}


def guid_and_picture(r):
    r.raw(16)
    pre = r.u('I')
    size = r.u('I')
    return r.raw(size)


def guid_and_font(r):
    g = r.raw(16)
    if g.hex().startswith('0352e30b'):  # StdFont
        r.u('B'); cs = r.u('H'); flags = r.u('B'); weight = r.u('H'); height = r.u('I')
        n = r.u('B'); face = r.raw(n).decode('cp949', 'replace')
        return {'font': face, 'size_twips': height * 20 // 10000 if height > 1000 else height, 'bold': weight >= 700,
                'stdfont_height': height}
    return text_props(r)


def morph(r):
    ver = r.u('BB'); cb = r.u('H'); end = r.p + cb
    mask = r.u('Q')
    b = Block(r)
    d = {}
    vpb = b.get(4) if bits(mask, 0) else 0x2C80081B
    d['bits'] = vpb
    d['backcolor'] = b.get(4) if bits(mask, 1) else 0x80000005
    d['forecolor'] = b.get(4) if bits(mask, 2) else 0x80000008
    d['maxlength'] = b.get(4) if bits(mask, 3) else 0
    d['borderstyle'] = b.get(1) if bits(mask, 4) else 0
    d['scrollbars'] = b.get(1) if bits(mask, 5) else 0
    d['displaystyle'] = b.get(1) if bits(mask, 6) else 1
    if bits(mask, 7): b.get(1)
    if bits(mask, 9): b.get(2)
    if bits(mask, 10): b.get(4)
    if bits(mask, 11): b.get(2)
    if bits(mask, 12): b.get(2)
    if bits(mask, 13): b.get(2)
    if bits(mask, 14): b.get(2)
    if bits(mask, 15): b.get(2)
    if bits(mask, 16): b.get(1)
    d['liststyle'] = b.get(1) if bits(mask, 17) else 0
    if bits(mask, 18): b.get(1)
    if bits(mask, 20): b.get(1)
    if bits(mask, 21): b.get(1)
    vlen = b.get(4) if bits(mask, 22) else 0
    clen = b.get(4) if bits(mask, 23) else 0
    if bits(mask, 24): b.get(4)
    if bits(mask, 25): b.get(4)
    d['specialeffect'] = b.get(4) if bits(mask, 26) else 2
    if bits(mask, 27): b.get(2)
    if bits(mask, 28): b.get(2)
    if bits(mask, 29): b.get(2)
    glen = b.get(4) if bits(mask, 32) else 0
    b.end()
    st = r.p
    if bits(mask, 8):
        d['w'], d['h'] = r.u('II')
    d['value'] = counted_str(r, vlen, st) if vlen else ''
    d['caption'] = counted_str(r, clen, st) if clen else ''
    d['group'] = counted_str(r, glen, st) if glen else ''
    r.p = end
    if bits(mask, 27): guid_and_picture(r)
    if bits(mask, 28): d['picture'] = guid_and_picture(r)
    d.update(text_props(r))
    d['kind'] = DISPLAY.get(d['displaystyle'], 'TextBox')
    d['enabled'] = bool(vpb & 2)
    d['locked'] = bool(vpb & 4)
    d['multiline'] = bool(vpb & (1 << 26))
    d['wordwrap'] = bool(vpb & (1 << 23))
    d['autosize'] = bool(vpb & (1 << 28))
    return d


def label(r):
    ver = r.u('BB'); cb = r.u('H'); end = r.p + cb
    mask = r.u('I')
    b = Block(r); d = {}
    d['forecolor'] = b.get(4) if bits(mask, 0) else 0x80000012
    d['backcolor'] = b.get(4) if bits(mask, 1) else 0x8000000F
    vpb = b.get(4) if bits(mask, 2) else 0x0080001B
    clen = b.get(4) if bits(mask, 3) else 0
    if bits(mask, 4): b.get(4)
    if bits(mask, 6): b.get(1)
    if bits(mask, 7): b.get(4)
    d['borderstyle'] = b.get(2) if bits(mask, 8) else 0
    d['specialeffect'] = b.get(2) if bits(mask, 9) else 0
    if bits(mask, 10): b.get(2)
    if bits(mask, 11): b.get(2)
    if bits(mask, 12): b.get(2)
    b.end(); st = r.p
    d['caption'] = counted_str(r, clen, st) if clen else ''
    if bits(mask, 5): d['w'], d['h'] = r.u('II')
    r.p = end
    if bits(mask, 10): d['picture'] = guid_and_picture(r)
    if bits(mask, 12): guid_and_picture(r)
    d.update(text_props(r))
    d['enabled'] = bool(vpb & 2)
    d['wordwrap'] = bool(vpb & (1 << 23))
    d['autosize'] = bool(vpb & (1 << 28))
    d['backstyle_opaque'] = bool(vpb & 8)
    return d


def cmdbutton(r):
    ver = r.u('BB'); cb = r.u('H'); end = r.p + cb
    mask = r.u('I')
    b = Block(r); d = {}
    d['forecolor'] = b.get(4) if bits(mask, 0) else 0x80000012
    d['backcolor'] = b.get(4) if bits(mask, 1) else 0x8000000F
    vpb = b.get(4) if bits(mask, 2) else 0x0000001B
    clen = b.get(4) if bits(mask, 3) else 0
    if bits(mask, 4): b.get(4)
    if bits(mask, 6): b.get(1)
    if bits(mask, 7): b.get(2)
    if bits(mask, 8): b.get(2)
    if bits(mask, 10): b.get(2)
    b.end(); st = r.p
    d['caption'] = counted_str(r, clen, st) if clen else ''
    if bits(mask, 5): d['w'], d['h'] = r.u('II')
    r.p = end
    if bits(mask, 7): d['picture'] = guid_and_picture(r)
    if bits(mask, 10): guid_and_picture(r)
    d.update(text_props(r))
    d['enabled'] = bool(vpb & 2)
    return d


def image(r):
    ver = r.u('BB'); cb = r.u('H'); end = r.p + cb
    mask = r.u('I')
    b = Block(r); d = {}
    if bits(mask, 3): b.get(4)
    d['backcolor'] = b.get(4) if bits(mask, 4) else 0x8000000F
    d['borderstyle'] = b.get(1) if bits(mask, 5) else 1
    if bits(mask, 6): b.get(1)
    d['sizemode'] = b.get(1) if bits(mask, 7) else 0
    d['specialeffect'] = b.get(1) if bits(mask, 8) else 0
    if bits(mask, 10): b.get(2)
    d['picalign'] = b.get(1) if bits(mask, 11) else 2
    if bits(mask, 13): b.get(4)
    if bits(mask, 14): b.get(2)
    b.end()
    if bits(mask, 9): d['w'], d['h'] = r.u('II')
    r.p = end
    if bits(mask, 10): d['picture'] = guid_and_picture(r)
    if bits(mask, 14): guid_and_picture(r)
    return d


def spin(r):
    ver = r.u('BB'); cb = r.u('H'); end = r.p + cb
    mask = r.u('I')
    b = Block(r); d = {}
    if bits(mask, 0): b.get(4)
    if bits(mask, 1): b.get(4)
    if bits(mask, 2): b.get(4)
    b.end()
    # size is first in extra block
    r2 = R(r.b, r.p)
    # Skip the rest; layout from site is enough
    r.p = end
    return d


def form_control(r):
    """FormControl (the 'f' stream). Returns (form props, sites)."""
    ver = r.u('BB'); cb = r.u('H'); end = r.p + cb
    mask = r.u('I')
    b = Block(r); d = {}
    d['backcolor'] = b.get(4) if bits(mask, 1) else 0x8000000F
    d['forecolor'] = b.get(4) if bits(mask, 2) else 0x80000012
    if bits(mask, 3): b.get(4)
    boolp = b.get(4) if bits(mask, 6) else 0x4
    d['borderstyle'] = b.get(1) if bits(mask, 7) else 0
    if bits(mask, 8): b.get(1)       # MousePointer
    if bits(mask, 9): b.get(1)       # ScrollBars
    if bits(mask, 13): b.get(4)      # GroupCnt
    if bits(mask, 15): b.get(2)      # MouseIcon
    if bits(mask, 16): b.get(1)      # Cycle
    d['specialeffect'] = b.get(1) if bits(mask, 17) else 0
    if bits(mask, 18): b.get(4)      # BorderColor
    clen = b.get(4) if bits(mask, 19) else 0
    if bits(mask, 20): b.get(2)      # Font
    if bits(mask, 21): b.get(2)      # Picture
    if bits(mask, 22): b.get(4)
    if bits(mask, 23): b.get(1)
    if bits(mask, 25): b.get(1)
    if bits(mask, 26): b.get(4)
    if bits(mask, 27): b.get(4)
    b.end(); st = r.p
    if bits(mask, 10): d['w'], d['h'] = r.u('II')
    if bits(mask, 11): r.u('II')
    if bits(mask, 12): r.u('ii')
    d['caption'] = counted_str(r, clen, st) if clen else ''
    r.p = end
    if bits(mask, 15): guid_and_picture(r)
    if bits(mask, 20): d.update(guid_and_font(r))
    if bits(mask, 21): d['picture'] = guid_and_picture(r)
    if not (boolp & (1 << 15)):
        n = r.u('H')
        for _ in range(n):
            r.u('H'); cbc = r.u('H'); r.raw(cbc)
    count, nbytes = r.u('II')
    start = r.p
    # depths and types
    left = count
    while left > 0:
        depth, typ = r.u('BB')
        if typ & 0x80:
            r.u('B'); left -= (typ & 0x7F)
        else:
            left -= 1
    off = (r.p - start) % 4
    if off: r.p += 4 - off
    sites = []
    for _ in range(count):
        sites.append(site(r))
    return d, sites


def site(r):
    ver = r.u('H'); cb = r.u('H'); end = r.p + cb
    mask = r.u('I')
    b = Block(r); s = {}
    nlen = b.get(4) if bits(mask, 0) else 0
    tlen = b.get(4) if bits(mask, 1) else 0
    s['id'] = b.get(4) if bits(mask, 2) else 0
    if bits(mask, 3): b.get(4)
    s['bitflags'] = b.get(4) if bits(mask, 4) else 0x33
    s['osize'] = b.get(4) if bits(mask, 5) else 0
    s['tab'] = b.get(2) if bits(mask, 6) else -1
    s['cls'] = b.get(2) if bits(mask, 7) else 0x7FFF
    if bits(mask, 9): b.get(2)
    tiplen = b.get(4) if bits(mask, 11) else 0
    lic = b.get(4) if bits(mask, 12) else 0
    cs = b.get(4) if bits(mask, 13) else 0
    rs = b.get(4) if bits(mask, 14) else 0
    b.end(); st = r.p
    s['name'] = counted_str(r, nlen, st) if nlen else ''
    s['tag'] = counted_str(r, tlen, st) if tlen else ''
    s['x'], s['y'] = r.u('ii') if bits(mask, 8) else (0, 0)
    s['tip'] = counted_str(r, tiplen, st) if tiplen else ''
    s['visible'] = bool(s['bitflags'] & 2)
    s['tabstop'] = bool(s['bitflags'] & 1)
    r.p = end
    s['type'] = CLS.get(s['cls'] & 0x7FFF, 'cls%d' % s['cls'])
    return s


def parse_container(ole, path, picdir, prefix):
    f = ole.openstream(path + ['f']).read()
    props, sites = form_control(R(f))
    o = ole.openstream(path + ['o']).read() if ole.exists('/'.join(path + ['o'])) else b''
    pos = 0
    out = []
    for s in sites:
        data = o[pos:pos + s['osize']]
        pos += s['osize']
        t = s['type']
        try:
            if t in ('MorphData', 'TextBox', 'ComboBox', 'ListBox', 'CheckBox', 'OptionButton', 'ToggleButton'):
                d = morph(R(data)); s['type'] = d['kind'] if t == 'MorphData' else t
            elif t == 'Label': d = label(R(data))
            elif t == 'CommandButton': d = cmdbutton(R(data))
            elif t == 'Image': d = image(R(data))
            elif t in ('Frame', 'MultiPage'):
                sub = path + ['i%02d' % s['id']]
                fp, children = parse_container(ole, sub, picdir, prefix)
                d = fp; d['children'] = children
                if data:
                    try:
                        # Frame 'o'-data in parent holds nothing useful usually
                        pass
                    except Exception:
                        pass
            elif t == 'SpinButton': d = spin(R(data))
            else: d = {}
        except Exception as e:
            d = {'error': repr(e)}
        pic = d.pop('picture', None)
        if pic:
            ext = 'bmp' if pic[:2] == b'BM' else ('jpg' if pic[:2] == b'\xff\xd8' else ('gif' if pic[:3] == b'GIF' else 'bin'))
            fn = '%s_%s.%s' % (prefix, s['name'], ext)
            open(os.path.join(picdir, fn), 'wb').write(pic)
            d['picture_file'] = fn
        s.update(d)
        out.append(s)
    pic = props.pop('picture', None)
    if pic:
        fn = '%s_%s_bg.bin' % (prefix, path[-1])
        open(os.path.join(picdir, fn), 'wb').write(pic)
        props['picture_file'] = fn
    return props, out


def main():
    ole = olefile.OleFileIO(sys.argv[1])
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    result = {}
    for e in ole.listdir(storages=True, streams=False):
        if len(e) == 2 and e[0] == 'VBA_Project' and e[1] != 'VBA':
            name = e[1]
            frame = ole.openstream(e + ['\x03VBFrame']).read().decode('cp949')
            props, sites = parse_container(ole, e, outdir, name)
            result[name] = {'vbframe': frame, 'props': props, 'controls': sites}
    json.dump(result, open(os.path.join(outdir, 'forms.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


main()
