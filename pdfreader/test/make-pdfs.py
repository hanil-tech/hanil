# 시험용 PDF 폴더 만들기 — python3 make-pdfs.py <폴더>
#  · 한글(글꼴 안 품은 CID 글꼴 → 글꼴 표 CMap 이 있어야 읽힘) · 표 안 도면 번호 · 번호가 두 조각으로 갈린 것
#  · 전각 숫자 · 암호 걸린 것 · 글자 없는(그림만) 것 · 깨진 파일 · 하위 폴더 · 책갈피·고리 있는 여러 쪽 문서
import os, sys
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import pdfencrypt

out = sys.argv[1]
os.makedirs(os.path.join(out, '하위 폴더', '더 아래'), exist_ok=True)
pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
K = 'HYSMyeongJo-Medium'

def table(c, y, rows):
    for r in rows:
        x = 60
        for cell in r:
            c.rect(x, y - 4, 150, 18)
            c.drawString(x + 4, y, cell)
            x += 150
        y -= 18
    return y

def bom(path, n, parts, extra=None, size=A4, enc=None):
    c = canvas.Canvas(path, pagesize=size, encrypt=enc)
    c.setTitle('부품표 ' + os.path.basename(path)); c.setAuthor('한일특장 설계팀'); c.setSubject('시험')
    for pg in range(n):
        c.setFont(K, 16); c.drawString(60, size[1] - 60, '부품 목록 (BOM) — %d / %d 쪽' % (pg + 1, n))
        c.setFont(K, 10)
        rows = [['품번', '품명', '수량']] + [[p, '브래킷 %d' % i, str(i)] for i, p in enumerate(parts.get(pg, []))]
        table(c, size[1] - 100, rows)
        if extra: extra(c, pg)
        c.showPage()
    c.save()

os.chdir(out)
bom('A-001 섀시 부품표.pdf', 3, {0: ['40396607-5', '40396607-6'], 2: ['50000001-1', '40396607-5']})
bom('A-002 적재함.pdf', 2, {1: ['11112222-3']})
def split(c, pg):  # 같은 번호가 두 조각으로(표 칸 경계) · 띄어쓰기 들어간 것
    if pg == 0:
        c.drawString(60, 300, '40396607'); c.drawString(108, 300, '-5')
        c.drawString(60, 280, '품번: 4039 6607-5 (띄어 씀)')
bom('A-003 조각난 번호.pdf', 1, {0: []}, extra=split)
def wide(c, pg):
    c.drawString(60, 300, '전각: ４０３９６６０７－５')
bom('A-004 전각.pdf', 1, {0: []}, extra=wide)
bom('A3 가로 도면.pdf', 1, {0: ['40396607-5']}, size=landscape(A3))
bom('B-100 암호.pdf', 1, {0: ['40396607-5']}, enc=pdfencrypt.StandardEncryption('1234', canPrint=1))
# 그림만(글자 없음)
c = canvas.Canvas('스캔본.pdf', pagesize=A4)
for i in range(40): c.line(50 + i * 10, 100, 300, 700)
c.showPage(); c.save()
open('깨진 파일.pdf', 'wb').write(b'%PDF-1.4\nthis is not really a pdf')
open('메모.txt', 'w').write('pdf 아님')
for i in range(20):
    bom(os.path.join('하위 폴더', 'C-%03d.pdf' % i), 1, {0: ['77777777-%d' % i] + (['40396607-5'] if i == 7 else [])})
bom(os.path.join('하위 폴더', '더 아래', 'D-깊은 곳.pdf'), 1, {0: ['40396607-5']})

# 여러 쪽 + 책갈피 + 문서 안 고리
c = canvas.Canvas('설명서 50쪽.pdf', pagesize=A4)
c.setTitle('설명서'); 
for p in range(50):
    c.setFont(K, 20); c.drawString(60, 780, '제 %d 장' % (p + 1))
    c.setFont(K, 11)
    for l in range(30):
        c.drawString(60, 740 - l * 20, '%d쪽 %d줄: 유압 실린더 점검 순서와 볼트 체결 토크(N·m)를 확인합니다.' % (p + 1, l + 1))
    if p == 33: c.drawString(60, 100, '교체 부품 40396607-5 를 쓰십시오.')
    c.bookmarkPage('p%d' % p); c.addOutlineEntry('제 %d 장' % (p + 1), 'p%d' % p, level=0)
    if p == 0:
        c.drawString(60, 60, '→ 34쪽으로 가기'); c.linkAbsolute('', 'p33', (55, 55, 200, 75))
    c.showPage()
c.save()
print('ok')
