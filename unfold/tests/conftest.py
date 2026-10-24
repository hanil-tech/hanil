import os
import sys

# 어느 폴더에서 pytest 를 돌려도 hanil_unfold 를 찾게 한다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 화면 없이 돌릴 때도 창(QDialog)을 만들 수 있게, 처음에 QApplication 하나를 만든다.
# (보고서 그리기용 QGuiApplication 이 먼저 생기면 그 뒤로는 창을 만들 수 없다)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])
