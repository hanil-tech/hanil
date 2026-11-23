# 아이콘 만들기(크롬 확장·윈도우 프로그램) — python3 make-icons.py
#  빨간 둥근 네모 + 흰 「PDF」 + 아래 「한일」 띠
import os
from PIL import Image, ImageDraw, ImageFont
here = os.path.dirname(os.path.abspath(__file__))
def font(size, bold=True):
    for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf']:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()
def icon(n):
    s = 4 * n
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = s * 0.18
    d.rounded_rectangle([s * 0.04, s * 0.04, s * 0.96, s * 0.96], radius=r, fill=(200, 16, 46, 255))
    # 접힌 귀퉁이
    d.polygon([(s * 0.70, s * 0.04), (s * 0.96, s * 0.04), (s * 0.96, s * 0.30)], fill=(150, 10, 32, 255))
    f = font(int(s * 0.36))
    t = 'PDF'
    w = d.textlength(t, font=f)
    d.text(((s - w) / 2, s * 0.22), t, font=f, fill='white')
    if n >= 32:
        d.rounded_rectangle([s * 0.16, s * 0.68, s * 0.84, s * 0.88], radius=s * 0.04, fill=(255, 255, 255, 240))
        f2 = font(int(s * 0.15)); t2 = 'HANIL'; w2 = d.textlength(t2, font=f2)
        d.text(((s - w2) / 2, s * 0.695), t2, font=f2, fill=(200, 16, 46, 255))
    return im.resize((n, n), Image.LANCZOS)
for n in (16, 32, 48, 128, 256):
    icon(n).save(os.path.join(here, 'icon-%d.png' % n))
icon(256).save(os.path.join(here, 'icon.ico'), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('ok')
