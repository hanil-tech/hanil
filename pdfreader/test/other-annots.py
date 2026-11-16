# 「다른 프로그램이 넣은 주석」 흉내 — pypdf 로 사각형·원·선·글상자 주석을 넣는다
#   python3 other-annots.py <원본.pdf> <결과.pdf>
import sys
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Rectangle, Ellipse, Line, FreeText
r = PdfReader(sys.argv[1]); w = PdfWriter(); w.append(r)
w.add_annotation(0, Rectangle(rect=(100, 500, 250, 600)))
w.add_annotation(0, Ellipse(rect=(300, 500, 400, 580)))
w.add_annotation(0, Line(p1=(100, 450), p2=(300, 420), rect=(95, 415, 305, 455)))
w.add_annotation(0, FreeText(text="other app note", rect=(100, 380, 300, 410), font_size="14pt", font_color="0000ff", border_color=None, background_color=None))
w.write(sys.argv[2])
