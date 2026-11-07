# 버그 고침 시험용 PDF — python3 make-fix.py <폴더>
#  비밀3쪽.pdf: 2쪽에만 SECRET-PAGE-TWO (Helvetica, 날 글자)
#  표TJ.pdf: 한 TJ 안에 두 칸 [(Qty) -9000 (Price)]
#  검토주석.pdf: 다른 사람이 단 사각형 주석(메모·작성자) + 그 답글(IRT)
import os, sys
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, ArrayObject, FloatObject, TextStringObject, NumberObject
out = sys.argv[1]
c = canvas.Canvas(os.path.join(out, '비밀3쪽.pdf'))
for p in range(3):
    c.setFont('Helvetica', 20); c.drawString(72, 700, 'PAGE %d' % (p + 1))
    if p == 1: c.drawString(72, 650, 'SECRET-PAGE-TWO')
    c.showPage()
c.save()
def raw_pdf(path, content):
    objs = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
            None, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    b = bytearray(b'%PDF-1.4\n'); offs = []
    for k, o in enumerate(objs):
        offs.append(len(b))
        if o is None: b += b'%d 0 obj\n<< /Length %d >>\nstream\n' % (k + 1, len(content)) + content + b'\nendstream\nendobj\n'
        else: b += ('%d 0 obj\n%s\nendobj\n' % (k + 1, o)).encode()
    x = len(b)
    b += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    for o in offs: b += b'%010d 00000 n \n' % o
    b += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, x)
    open(path, 'wb').write(b)
raw_pdf(os.path.join(out, '표TJ.pdf'), b'BT /F1 14 Tf 72 700 Td [(Qty) -9000 (Price)] TJ ET\nBT /F1 14 Tf 72 660 Td (Other line) Tj ET')
r = PdfReader(os.path.join(out, '비밀3쪽.pdf')); w = PdfWriter(); w.append(r)
sq = DictionaryObject({NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Square'),
    NameObject('/Rect'): ArrayObject([FloatObject(100), FloatObject(400), FloatObject(250), FloatObject(500)]),
    NameObject('/C'): ArrayObject([FloatObject(1), FloatObject(0), FloatObject(0)]), NameObject('/Contents'): TextStringObject('reviewer comment KIM'),
    NameObject('/T'): TextStringObject('Kim Reviewer'), NameObject('/NM'): TextStringObject('sq-1')})
ref = w._add_object(sq)
rep = DictionaryObject({NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Text'),
    NameObject('/Rect'): ArrayObject([FloatObject(260), FloatObject(480), FloatObject(280), FloatObject(500)]),
    NameObject('/Contents'): TextStringObject('reply LEE'), NameObject('/T'): TextStringObject('Lee'), NameObject('/IRT'): ref})
ref2 = w._add_object(rep)
w.pages[0][NameObject('/Annots')] = ArrayObject([ref, ref2])
w.write(os.path.join(out, '검토주석.pdf'))
print('ok')
