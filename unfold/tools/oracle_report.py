"""정답 대조 시험 결과표 docs/oracle.md 만들기:  python tools/oracle_report.py"""
import datetime as _dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, ".."), os.path.join(HERE, "..", "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import oracle_cases as oc  # noqa: E402

from hanil_unfold import __version__  # noqa: E402


def main():
    rows = oc.run_all()
    ok = sum(r[10] for r in rows)
    lines = ["# 정답 대조 시험 (oracle)", "",
             f"`python tools/oracle_report.py` 로 만듦 — {_dt.date.today().isoformat()}, 버전 {__version__}.",
             "사례는 [tests/oracle_cases.py](../tests/oracle_cases.py), 통과 여부는 `tests/test_oracle.py` 가 CI 에서 확인한다.",
             "정답은 손으로 계산한 해석식이나 문헌의 계산 예제이고, 프로그램 결과를 거기에 견준다 "
             "(SolidCraft 의 reference tests 방식).", "",
             f"**{ok} / {len(rows)} 사례 통과**", "",
             "| 번호 | 묶음 | 사례 | 정답 출처 | 식 | 정답 | 프로그램 | 오차 | 허용 | 결과 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        no, grp, name, src, how, exp, _, tol, got, err, passed = r
        lines.append(f"| {no} | {grp} | {name} | {src} | {how} | {exp:,.4f} | {got:,.4f} | {err:.2e} | {tol:.0e} | "
                     f"{'통과' if passed else '**실패**'} |")
    lines += ["", "- 판금 전개 (K 직접 · DIN 6935) 와 원통 말기는 식 그대로라 오차가 계산 정밀도 (1e-15) 수준.",
              "- 원뿔 말기 2e-4: 부채꼴 원호를 꺾은선으로 잰 넓이 몫.",
              "- 성형품 (원스텝) 은 근사 — 체적 일정 원판 지름과 1~2 % (원스텝은 두께 변화를 넓이 가중으로 풂). "
              "실제 컵 시험값과의 차는 [실적 보정] 으로 맞춘다.",
              "- 금형 설계 문헌 예제의 정답은 문헌에 반올림된 값 (1.16, 1.41) 이라 허용을 0.5~1 % 로 둠."]
    path = os.path.join(HERE, "..", "docs", "oracle.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{ok}/{len(rows)} → {os.path.normpath(path)}")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
