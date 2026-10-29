"""프로그램 판 (edition): 전체판 / 전개 전용판.

  full   — 전개 + 성형 해석 · 금형 · 견적 · 원가 · 생산 · 품질 · 검사 · 네스팅 · BOM (지금 프로그램)
  unfold — 전개 전용: 3D·2D 도면 열기, 전개도 DXF, 전개 보고서 (PDF·엑셀), 조립도, 여러 파일 한꺼번에,
           전개 기록, 연신 표·밀시트 (전개 정확도)

설치 파일을 만들 때 packaging/write_build_info.py --edition unfold 가 hanil_unfold/_edition.py 를 써서
실행 파일 안에 판을 못 박는다 (그 파일이 있으면 환경 변수로 바꿀 수 없음). 개발 중에는 HANIL_EDITION=unfold.
"""
from __future__ import annotations

import os

FULL, UNFOLD = "full", "unfold"

try:
    from ._edition import EDITION as _BAKED          # 빌드 때 못 박은 판
except ImportError:
    _BAKED = None

EDITION = _BAKED or (UNFOLD if os.environ.get("HANIL_EDITION", "").lower() == UNFOLD else FULL)

NAMES = {FULL: "한일 판금 전개", UNFOLD: "한일 판금 전개 (전개 전용)"}
EXE = {FULL: "HanilUnfold", UNFOLD: "HanilUnfoldLite"}


def unfold_only() -> bool:
    return EDITION == UNFOLD


def name() -> str:
    return NAMES[EDITION]
