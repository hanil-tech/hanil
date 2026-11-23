# 큰 PDF 만들기 — python3 make-big.py <폴더>
#  글자 300쪽 · 그림(스캔 같은) 300쪽 · 글자 1000쪽
import os, sys, io, random
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from PIL import Image, ImageDraw
out = sys.argv[1]
pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
def text_pdf(name, n):
    c = canvas.Canvas(os.path.join(out, name), pagesize=A4)
    for p in range(n):
        c.setFont('HYSMyeongJo-Medium', 16); c.drawString(50, 790, '정비 지침서 %d / %d 쪽' % (p + 1, n))
        c.setFont('HYSMyeongJo-Medium', 9)
        for l in range(60):
            c.drawString(50, 760 - l * 12, '%d-%d 유압 펌프 점검: 압력 %d bar, 볼트 M%d 토크 %d N·m, 품번 %08d-%d' % (p + 1, l + 1, 150 + l, 8 + l % 6, 20 + l, 40000000 + p * 100 + l, l % 9))
        if p == n - 3: c.drawString(50, 40, '마지막 근처 표시 MARK-LAST-%d' % n)
        c.bookmarkPage('p%d' % p); c.addOutlineEntry('%d쪽' % (p + 1), 'p%d' % p)
        c.showPage()
    c.save()
def image_pdf(name, n):
    c = canvas.Canvas(os.path.join(out, name), pagesize=A4)
    random.seed(1)
    for p in range(n):
        im = Image.new('L', (1240, 1754), 245); d = ImageDraw.Draw(im)
        for k in range(120): d.line([(random.randint(0, 1240), random.randint(0, 1754)), (random.randint(0, 1240), random.randint(0, 1754))], fill=random.randint(0, 120), width=2)
        d.rectangle([60, 60, 1180, 160], outline=0, width=4)
        b = io.BytesIO(); im.save(b, 'JPEG', quality=60); b.seek(0)
        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(b), 0, 0, width=A4[0], height=A4[1])
        c.showPage()
    c.save()
text_pdf('글자300쪽.pdf', 300)
image_pdf('스캔300쪽.pdf', 300)
text_pdf('글자1000쪽.pdf', 1000)
print('ok')
