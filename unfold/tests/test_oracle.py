"""정답 대조 시험: tests/oracle_cases.py 의 모든 사례가 허용 오차 안 (docs/oracle.md 표와 같은 사례)."""
import pytest

import oracle_cases as oc

CASES = oc.cases()


@pytest.mark.parametrize("case", CASES, ids=[f"{c[0]:02d}-{c[2]}" for c in CASES])
def test_oracle_case(case):
    no, grp, name, src, how, expected, run, tol = case
    got = run()
    assert got == pytest.approx(expected, rel=tol), f"{grp} · {name}: 정답 {expected} ({src}) ≠ {got}"
