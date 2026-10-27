"""한일 판금 전개: 3D 판금 도면(STEP)을 펼쳐 DXF 전개도로 만든다."""

__version__ = "1.45.0"

# 빌드 정보는 GitHub Actions 가 _build.py 로 만들어 넣는다 (직접 실행하면 "개발판").
try:
    from ._build import BUILD_NUMBER, BUILD_COMMIT, BUILD_DATE
except ImportError:
    BUILD_NUMBER, BUILD_COMMIT, BUILD_DATE = "", "", ""


def version_text(long=False) -> str:
    """'1.5.0 (빌드 12)'  /  long=True: '1.5.0 (빌드 12 · e4b8ede · 2026-10-23)'."""
    if not BUILD_NUMBER:
        return f"{__version__} (개발판)"
    if long:
        return f"{__version__} (빌드 {BUILD_NUMBER} · {BUILD_COMMIT} · {BUILD_DATE})"
    return f"{__version__} (빌드 {BUILD_NUMBER})"
