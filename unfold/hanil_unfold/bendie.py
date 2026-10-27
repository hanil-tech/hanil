"""절곡 금형 (공정별 금형 한 벌): 와이핑 (L) · U 굽힘 (양쪽 와이핑) · 각도 굽힘 (기울인 다이 면) · 기울인 펀치로 넘김
(마무리 굽힘 · 예비 헤밍) · 헤밍 (평 펀치로 눌러 접기).

좌표 (금형): 제품을 눕히는 판 (바탕 쪽) 을 수평, 접는 쪽을 +x. 절곡 접선 (판이 R 로 바뀌는 선) 이 x = 0, 다이 윗면
(제품 안쪽 면) 이 z = 0. 다 만든 뒤 하형 세트 밑면을 z = 0, 금형 가운데를 x = y = 0 으로 옮긴다.

와이핑 (Kalpakjian · Schmid 「Manufacturing Processes for Engineering Materials」 굽힘력 F = k · UTS · L · t² / W, 와이핑 k ≈ 0.33,
W = 다이 R + 틈 + 펀치 R):
  다이 블록 (모서리 R = 제품 안쪽 R, 옆면은 스프링백 각만큼 뒤로 빠짐) · 패드 (스프링으로 판을 먼저 누름) ·
  와이핑 펀치 (틈 t + 5 %, 끝 R 2t, 끝 아래쪽 스프링백 각만큼 기울임) · 힐 블록 (펀치 옆 힘을 받음, 판에 닿기 전에 물림).
  패드 힘은 굽힘력의 30 % (실무 어림) 를 판에 닿을 때부터.
"""
from __future__ import annotations

import math

import numpy as np

from . import bendcalc as bc
from . import diecalc as dc
from . import diestd as ds
from .die3d import (BOX, CYL, DENSITY, HEX_KEY, PRISM, PROF, REGRIND, DieAssy, DiePart, Hole, Prim, _pin, _up5, _uslot,
                    _volume, axi, screw)

K_WIPE = 0.33          # 와이핑 굽힘력 계수 (Kalpakjian 0.3 ~ 0.34)
PAD_K = 0.30           # 패드 힘 / 굽힘력 (실무 어림)
LEAD = 3.0             # 패드가 펀치보다 먼저 닿는 길이 (열림 → 펀치 닿기 전)


# ---------------------------------------------------------------- 옮기기

def shift_prim(pr: Prim, dx, dy, dz):
    if pr.kind == BOX:
        x0, y0, z0, a, b, c = pr.p
        pr.p = (x0 + dx, y0 + dy, z0 + dz, a, b, c)
    elif pr.kind == CYL:
        x, y, z0, r, h = pr.p
        pr.p = (x + dx, y + dy, z0 + dz, r, h)
        pr.stack = [(z + dz, h_, r0, r1) for z, h_, r0, r1 in pr.stack]
        if pr.socket:
            z, d, s, sg = pr.socket
            pr.socket = (z + dz, d, s, sg)
    elif pr.kind == PRISM:
        pr.poly = np.asarray(pr.poly, float) + (dx, dy)
        pr.p = (pr.p[0] + dz, pr.p[1])
    else:
        P = np.asarray(pr.poly, float).copy()
        if pr.ax == "x":
            P[:, 0] += dy
            pr.p = (pr.p[0] + dx, pr.p[1])
        else:
            P[:, 0] += dx
            pr.p = (pr.p[0] + dy, pr.p[1])
        P[:, 1] += dz
        pr.poly = P
    pr.cuts = [tuple([np.asarray(c[0], float) + (dx, dy), c[1]] + ([c[2] + dz, c[3]] if len(c) > 2 else [])
                     + list(c[4:])) for c in pr.cuts]
    for h in pr.holes:
        h.x += dx
        h.y += dy
        h.z0 += dz
        if h.cb:
            h.cb = (h.cb[0], h.cb[1] + dz, h.cb[2])


def _arc(cx, cz, r, a0, a1, n=8):
    a = np.radians(np.linspace(a0, a1, n + 1))
    return [(cx + r * math.cos(t_), cz + r * math.sin(t_)) for t_ in a]


def _rect_fit(rect, obstacles, keep, margin):
    """상자 rect = [x0, x1, y0, y1] 에서 obstacles (x, y) 를 margin 띄워 빼도록 줄임 — 줄이는 쪽은 넓이를 가장 적게
    잃는 쪽, keep = [x0, x1, y0, y1] (꼭 있어야 하는 자리) 는 못 줄임. (줄인 상자, 남은 점 수)."""
    x0, x1, y0, y1 = rect
    pts = [tuple(p) for p in obstacles]
    for _ in range(400):
        bad = [(px, py) for px, py in pts if x0 - margin < px < x1 + margin and y0 - margin < py < y1 + margin]
        if not bad:
            return [x0, x1, y0, y1], 0
        px, py = bad[0]
        opts = []
        if px - margin <= keep[0] + 1e-9 and px + margin > x0:      # 왼쪽에서 잘라냄 (x0 를 올림)
            opts.append(((x1 - (px + margin)) * (y1 - y0), "x0", px + margin))
        if px + margin >= keep[1] - 1e-9 and px - margin < x1:
            opts.append((((px - margin) - x0) * (y1 - y0), "x1", px - margin))
        if py - margin <= keep[2] + 1e-9 and py + margin > y0:
            opts.append(((x1 - x0) * (y1 - (py + margin)), "y0", py + margin))
        if py + margin >= keep[3] - 1e-9 and py - margin < y1:
            opts.append(((x1 - x0) * ((py - margin) - y0), "y1", py - margin))
        opts = [o for o in opts if o[0] > 0]
        if not opts:
            pts.remove((px, py))
            continue
        _, side, v = max(opts)
        if side == "x0":
            x0 = v
        elif side == "x1":
            x1 = v
        elif side == "y0":
            y0 = v
        else:
            y1 = v
    left = [(px, py) for px, py in obstacles if x0 - margin < px < x1 + margin and y0 - margin < py < y1 + margin]
    return [x0, x1, y0, y1], len(left)


# ---------------------------------------------------------------- 금형 좌표

class DieFrame:
    """세계 (Folder 3D) → 금형 좌표. 바탕 쪽 판 S 를 수평, 절곡 b 의 도는 쪽을 +x, 접선 x = 0, 제품 안쪽 (또는 밑면) z = 0."""

    def __init__(self, F, b, done, flange_up=False):
        self.F, self.b = F, b
        M = F.panel_matrix(b.near, done)
        self.Minv = np.linalg.inv(M)
        self.sz = (1.0 if b.up else -1.0) * (1.0 if flange_up else -1.0)
        snl = b.n[0] * b.l[1] - b.n[1] * b.l[0]
        self.sy = self.sz * (1.0 if snl > 0 else -1.0)
        self.t = F.t

    def __call__(self, P3):
        P3 = np.atleast_2d(np.asarray(P3, float))
        Q = (self.Minv[:3, :3] @ P3.T).T + self.Minv[:3, 3]
        d = Q[:, :2] - self.b.a
        x = d @ self.b.n + self.b.half
        y = self.sy * (d @ self.b.l)
        z = self.sz * Q[:, 2] + self.t / 2
        return np.column_stack([x, y, z])

    def flat(self, P2):
        """바탕 쪽 판 S 위 전개 점 (z = 0) → 금형 좌표."""
        P2 = np.atleast_2d(np.asarray(P2, float))
        d = P2 - self.b.a
        return np.column_stack([d @ self.b.n + self.b.half, self.sy * (d @ self.b.l), np.full(len(P2), self.t / 2)])


# ---------------------------------------------------------------- 조립 도우미

class _Asm:
    def __init__(self):
        self.parts = []
        self.checks = []
        self.notes = []

    def add(self, name, qty, material, size, prims, std=False, note="", upper=False, order=""):
        self.parts.append(DiePart(len(self.parts) + 1, name, qty, material, size, std, note, prims, upper, order))
        return self.parts[-1]

    def chk(self, item, val, crit, ok):
        self.checks.append([item, val, crit, "적합" if ok else "검토"])


def _bolts_down(asm, block: Prim, shoe: Prim, pts, M, z_shoe0, ts, z_blk0, blk_h, name, upper=False):
    """블록을 세트에 볼트로: 세트 바깥 면 카운터보어 → 블록 탭. upper: 상형 (세트 윗면에서 아래로)."""
    k, kh, d1, cb, cbh, tap = ds.SHCS[M]
    g = ts - cbh
    L = ds.up_std(g + ds.ENGAGE * M, ds.SHCS_L)
    if L - g > blk_h - 4:
        L = ds.down_std(g + blk_h - 4, ds.SHCS_L)
    e = L - g
    prims = []
    for x, y in pts:
        if upper:
            shoe.holes.append(Hole(x, y, d1, "통과", z_shoe0, ts, f"Ø{d1:g} 통과, 자리 Ø{cb:g} 깊이 {cbh:g} ({name})",
                                   cb=(cb, z_shoe0 + ts - cbh, cbh)))
            block.holes.append(Hole(x, y, tap, "탭", z_blk0 + blk_h - (e + 3), e + 3,
                                    f"M{M} 탭 깊이 {e + 3:.0f} (윗면, 드릴 Ø{tap:g})"))
            prims.append(screw(x, y, z_shoe0 + ts - cbh, M, kh, k, L, False))
        else:
            shoe.holes.append(Hole(x, y, d1, "통과", z_shoe0, ts, f"Ø{d1:g} 통과, 자리 Ø{cb:g} 깊이 {cbh:g} ({name})",
                                   cb=(cb, z_shoe0, cbh), side="밑면"))
            block.holes.append(Hole(x, y, tap, "탭", z_blk0, e + 3, f"M{M} 탭 깊이 {e + 3:.0f} (밑면, 드릴 Ø{tap:g})",
                                    side="밑면"))
            prims.append(screw(x, y, z_shoe0 + cbh - kh, M, kh, k, L, True))
    return prims, L, e


def _dowels(block: Prim, shoe: Prim, pts, d, z_shoe0, ts, z_blk0, blk_h, upper=False):
    L = ds.up_std(min(blk_h, 2.5 * d) + max(1.5 * d, 10), ds.DOWEL_L)
    into_blk = min(blk_h, L - max(1.5 * d, 10))
    into_shoe = L - into_blk
    prims = []
    for x, y in pts:
        if upper:
            shoe.holes.append(Hole(x, y, d, "H7", z_shoe0, into_shoe + 1, f"Ø{d:g} H7 리머 깊이 {into_shoe + 1:.0f} (다우얼)",
                                   side="밑면"))
            block.holes.append(Hole(x, y, d, "H7", z_blk0 + blk_h - into_blk - 1, into_blk + 1,
                                    f"Ø{d:g} H7 리머 깊이 {into_blk + 1:.0f} (윗면, 다우얼)"))
            prims.append(_pin(x, y, z_shoe0 - into_blk, d, L))
        else:
            shoe.holes.append(Hole(x, y, d, "H7", z_shoe0 + ts - into_shoe - 1, into_shoe + 1,
                                   f"Ø{d:g} H7 리머 깊이 {into_shoe + 1:.0f} (다우얼)"))
            block.holes.append(Hole(x, y, d, "H7", z_blk0, into_blk + 1, f"Ø{d:g} H7 리머 깊이 {into_blk + 1:.0f} (밑면, 다우얼)",
                                    side="밑면"))
            prims.append(_pin(x, y, z_shoe0 + ts - into_shoe, d, L))
    return prims, L


def _row(a, b, n):
    if n <= 1:
        return [0.5 * (a + b)]
    return list(np.linspace(a, b, n))


# ---------------------------------------------------------------- 절곡 금형

def design(F, op, result, settings: bc.BendSettings, machines=None):
    """절곡 공정 하나의 금형 (DieAssy). F: tandem.Folder, op: tandem.Op."""
    from . import tandem as tdm
    mat = settings.mat
    t = F.t
    uts = mat.tensile_mpa
    bs = [F.bmap[n] for n in op.bends]
    b1 = bs[0]
    up_die = op.kind in (tdm.FINISH, tdm.PREHEM, tdm.HEM)          # 플랜지를 위로 세워 놓고 위에서 넘김
    cam = op.kind == tdm.CAM                                       # 세운 플랜지 구멍을 옆으로 (캠 슬라이더)
    fr = DieFrame(F, b1, op.before, flange_up=up_die)
    moving = set()
    for b in bs:
        moving |= set(F.subtree(b.number))
    # 제품 선 (공정 전 · 뒤) — 도는 쪽 점 표시
    loops = [F.outer] + F.holes
    before, after, mov_b, mov_a = [], [], [], []
    for loop in loops:
        D = F.dense(loop)
        where = F.locate(D)
        mv = np.array([(k in moving) if kind == "panel" else (k in op.bends or F.bmap[k].near in moving)
                       for kind, k in where])
        Pb = fr(F.fold(D, op.before, where))
        Pa = fr(F.fold(D, op.after, where))
        before.append(Pb)
        after.append(Pa)
        mov_b.append(mv)
        mov_a.append(mv)
    allb = np.vstack(before)
    alla = np.vstack(after)
    mvb = np.concatenate(mov_b)
    # 두 번째 절곡 (U): 접선 위치 (금형 x)
    sides = [(1.0, 0.0, b1)]
    if len(bs) == 2:
        b2 = bs[1]
        q = b2.a + (-b2.half) * b2.n + 0.5 * b2.length * b2.l
        x2 = float(fr.flat(q)[0, 0])
        sides.append((-1.0, x2, b2))
    # 판 S 의 범위 (금형 좌표), 접는 쪽 끝
    still_b = allb[~mvb]
    sx0, sx1 = float(still_b[:, 0].min()), float(still_b[:, 0].max())
    sy0, sy1 = float(still_b[:, 1].min()), float(still_b[:, 1].max())
    yb = [fr.flat(np.array([b.a, b.a + b.length * b.l]))[:, 1] for _, _, b in sides]
    by0, by1 = float(min(v.min() for v in yb)), float(max(v.max() for v in yb))
    asm = _Asm()
    th = {b.number: op.after[b.number] - op.before.get(b.number, 0.0) for b in bs}
    # 스프링백 (모멘트 법, diecalc.springback): 접어야 할 각
    sb = {}
    for b in bs:
        fin = op.after[b.number]
        _, need, ks = dc.springback(mat, b.r, t, fin)
        sb[b.number] = min(max(need - fin, 0.0), 8.0) if math.isfinite(need) else 8.0
    kind = op.kind
    c_gap = t * (1.10 if uts >= 590 else 1.05)
    # 공정마다 블록 · 펀치 단면 (접는 쪽 국소 ξ = sgn (x − x_t), 아래 z)
    lower_blocks, punches, heels = [], [], []
    F_bend = 0.0
    depth = 0.0
    nose_z = 0.0
    contact_h = 0.0                                       # 펀치가 판에 닿는 높이 (BDC 에서 위로) — 행정 계산
    fparts = {}
    cam_units = []
    F_hold = 0.0                                          # 패드가 잡아야 할 힘의 기준 (바텀 · 눌러 접기 몫 뺌)
    for sgn, x_t, b in sides:
        mvp = np.vstack([P[m] for P, m in zip(after, mov_a)]) if any(m.any() for m in mov_a) else np.zeros((0, 3))
        mvp_b = np.vstack([P[m] for P, m in zip(before, mov_b)]) if any(m.any() for m in mov_b) else np.zeros((0, 3))
        # 이 절곡 쪽 점만 (U 는 x 부호로 나눔)
        if len(sides) == 2:
            xm = 0.5 * (sides[0][1] + sides[1][1])
            mvp = mvp[(sgn * (mvp[:, 0] - xm)) > 0]
            mvp_b = mvp_b[(sgn * (mvp_b[:, 0] - xm)) > 0]
        xi_a = sgn * (mvp[:, 0] - x_t) if len(mvp) else np.zeros(1)
        za = mvp[:, 2] if len(mvp) else np.zeros(1)
        xi_tip = float((sgn * (mvp_b[:, 0] - x_t)).max()) if len(mvp_b) else 3 * t
        r_d = b.r
        fparts[b.number] = (xi_a, za, xi_tip)
        L_b = b.length
        if kind in (tdm.BEND, tdm.UBEND):
            x_face = r_d
            leg = (xi_a <= x_face + t + 0.6) & (xi_a >= x_face - 0.6)
            D_f = float(-za[leg].min()) if leg.any() else xi_tip
            out_ = (xi_a > x_face + t + 0.6) & (za < -r_d - t)
            in_ = (xi_a < x_face - 0.6) & (za < -r_d - t)
            nose = -(D_f + 1.0)
            if out_.any():
                nose = max(nose, float(za[out_].max()) + 1.0)
            r_p = max(2 * t, 3.0)
            W = r_d + c_gap + r_p
            F_b = K_WIPE * uts * L_b * t * t / W
            F_bend += F_b
            d_sb = sb[b.number]
            Hb = _up5(max(D_f + 15.0, 45.0))
            x_p = x_face + c_gap
            wp = max(30.0, _up5(xi_tip + 4 - x_p), _up5(2.5 * t + 20))
            tanr = math.tan(math.radians(d_sb))
            # 다이 블록 단면 (국소): 위 (0, 0) → R → 옆면 (스프링백 빠짐) → 밑
            prof = _arc(0.0, -r_d, r_d, 90, 0) + [(x_face - tanr * (Hb - r_d), -Hb)]     # 모서리 (위 → 아래)
            # 펀치 단면 (BDC, 국소): 안쪽 면 x_p (아래 끝 D_f/3 은 스프링백 각만큼 안으로), 끝 R r_p
            kick = min(D_f / 3.0, 25.0)
            z_k = nose + kick
            pprof = [(x_p + r_p, nose)] + _arc(x_p + r_p, nose + r_p, r_p, 270, 180)[1:]
            pprof = [(x_p - tanr * (z_k - z) if z < z_k else x_p, z) for x, z in pprof]
            pprof = pprof + [(x_p, z_k), (x_p, 1e3), (x_p + wp, 1e3), (x_p + wp, nose)]
            lower_blocks.append((sgn, x_t, b, prof, Hb, r_d, x_face))
            punches.append((sgn, x_t, b, pprof, x_p, wp))
            heels.append((sgn, x_t, b, x_p + wp + 0.02))
            depth = max(depth, D_f)
            nose_z = min(nose_z, nose)
            contact_h = max(contact_h, t - nose)
            asm.chk(f"B{b.number} 와이핑 길이 (펀치 끝이 R 아래로)", f"{-nose - r_d:.1f} mm", f"≥ {r_d + 3 * t:.1f} (R + 3t)",
                    -nose - r_d >= r_d + 3 * t - 1e-6)
            asm.chk(f"B{b.number} 이미 접힌 부분 ↔ 펀치 · 다이", f"바깥 {int(out_.sum())} · 안 {int(in_.sum())} 점",
                    "0 (닿으면 공정 순서 · 캠)", not in_.any())
            if out_.any():
                asm.notes.append(f"B{b.number}: 플랜지 끝에 이미 접힌 부분이 바깥으로 — 와이핑 펀치를 그 위 {-nose:.1f} 까지만 "
                                 "(끝까지 못 쓸음, 각도 확인)")
            asm.notes.append(f"B{b.number} 와이핑: 굽힘력 F = {K_WIPE:g} × UTS {uts:.0f} × L {L_b:.1f} × t² / W {W:.1f} "
                             f"= {F_b / 1000:,.1f} kN (Kalpakjian, W = 다이 R {r_d:g} + 틈 {c_gap:.2f} + 펀치 R {r_p:g}), "
                             f"스프링백 보정 {d_sb:.1f}° (다이 옆면 · 펀치 끝 기울임)")
        elif cam:
            x_face = r_d
            leg = (xi_a <= x_face + t + 0.6) & (xi_a >= x_face - 0.6)
            D_f = float(-za[leg].min()) if leg.any() else xi_tip
            # 이 플랜지의 구멍 (금형 좌표): 가운데 · 지름
            hz = []
            for i in op.holes:
                c2 = F.holes[i].mean(0)
                pi_ = F.hole_panel(i)
                if pi_ not in F.subtree(b.number):
                    continue
                q = fr(F.fold(c2[None], op.after, where=[("panel", pi_)]))[0]    # 구멍 가운데 (빈 곳) 는 그 판으로
                d_h = 2 * float(np.mean(np.linalg.norm(F.holes[i] - c2, axis=1)))
                hz.append((q, d_h, i))
            Hb = _up5(max(D_f + 15.0, 45.0))
            prof = _arc(0.0, -r_d, r_d, 90, 0) + [(x_face, -Hb)]
            tau = dc.shear_strength(mat)
            F_b = sum(math.pi * d_h * t * tau for _, d_h, _ in hz)
            F_bend += F_b
            s_c = 5.0 + t + 1.0                                   # 캠 슬라이더 이송 (물러남 5 + t + 진입 1)
            clr_c = dc.clearance_pct(mat, t) / 100 * t
            lower_blocks.append((sgn, x_t, b, prof, Hb, r_d, x_face))
            x_tip = x_face + t + 5.0                               # 열림: 펀치 끝 (플랜지 바깥 5 mm)
            punches.append((sgn, x_t, b, None, x_tip, 0.0))
            heels.append((sgn, x_t, b, None))
            cam_units.append((sgn, x_t, b, hz, s_c, clr_c, x_face, D_f))
            depth = max(depth, D_f)
            contact_h = max(contact_h, s_c + 2.0)                 # 45° 드라이버: 상형 s_c 내려가면 슬라이더 s_c
            asm.notes.append(f"B{b.number} 플랜지 캠 피어싱: 구멍 {len(hz)} 개, 힘 {F_b / 1000:,.1f} kN, 캠 이송 {s_c:.1f} "
                             f"(45° 드라이버), 다이 구멍 = 구멍 + 2 × {clr_c:.3f} (앤빌 옆면)")
        elif kind == tdm.ANGLE:
            ang = th[b.number]
            ang_d = min(ang + sb[b.number], 89.0)
            a = math.radians(ang_d)
            dirv = np.array([math.cos(a), -math.sin(a)])
            arc = _arc(0.0, -r_d, r_d, 90, 90 - ang_d)
            e0 = np.array(arc[-1])
            Lf = max(xi_tip - r_d * math.radians(ang_d), 5 * t)
            Hb = _up5(max((Lf + 10) * math.sin(a) + r_d + 15, 45.0))
            far = e0 + dirv * ((Hb + e0[1]) / max(math.sin(a), 1e-3))
            prof = arc + [tuple(far)]
            nrm = np.array([math.sin(a), math.cos(a)])          # 다이 면 바깥 법선 (위쪽)
            p0 = e0 + dirv * 1.0 + nrm * t
            p1 = e0 + dirv * (Lf + 6) + nrm * t
            pprof = [tuple(p0), tuple(p1), (p1[0] + 15, p1[1]), (p1[0] + 15, 1e3), (p0[0], 1e3)]
            W = 8 * t
            F_b = dc.bend_force(mat, L_b, t, W, bc.BOTTOM)
            F_bend += F_b
            F_hold += K_WIPE * uts * L_b * t * t / (r_d + c_gap + 2 * t)     # 판을 잡는 힘은 와이핑 몫으로
            lower_blocks.append((sgn, x_t, b, prof, Hb, r_d, float(far[0])))
            punches.append((sgn, x_t, b, pprof, float(p0[0]), float(p1[0] + 15 - p0[0])))
            heels.append((sgn, x_t, b, float(p1[0] + 15 + 0.02)))
            depth = max(depth, float(-p1[1]))
            nose_z = min(nose_z, float(p1[1]))
            contact_h = max(contact_h, t - float(p1[1]))
            asm.notes.append(f"B{b.number} 각도 굽힘 {ang:.0f}° (다이 면 {ang_d:.1f}° — 스프링백 {sb[b.number]:.1f}°): 바텀 "
                             f"굽힘력 {F_b / 1000:,.1f} kN (V {W:.0f} 어림 ×2)")
        else:                                              # 위로 세운 플랜지를 넘김 (마무리 · 예비 헤밍 · 헤밍)
            a0 = op.before[b.number]
            a1 = op.after[b.number]
            Lf = max(xi_tip - b.r * math.radians(90), 4 * t)
            ro = b.r + t
            Hb = 45.0
            # 앤빌 (제품 밑면 받침): 위 z = 0, 절곡 바깥 R 앞 2 mm 까지
            prof = [(0.0, 0.0), (ro + 2, 0.0), (ro + 2, -Hb)]
            if kind == tdm.HEM:
                z_f = 2 * t + 0.0                                # 접힌 플랜지 위 (닫힌 헤밍)
                x0p, x1p = -(Lf + 5), ro + 8
                pprof = [(x0p, z_f), (x1p, z_f), (x1p, 1e3), (x0p, 1e3)]
                F_b = 3.0 * K_WIPE * uts * L_b * t * t / (2 * t)      # 눌러 접기 어림 (굽힘력 × 3)
                nose = z_f
                contact = z_f + Lf * math.sin(math.radians(180 - a0))
            else:
                ang_out = a1 + min(sb[b.number], 5.0)            # 넘길 각 (스프링백 보정)
                phi = math.radians(ang_out - 90)                 # 세운 플랜지가 안쪽으로 기울어지는 각 (수직에서)
                # 펀치 면: BDC 에서 플랜지 바깥 면을 따라 (뿌리 위 R 끝에서 끝까지)
                root = np.array([ro, ro])
                dirf = np.array([-math.sin(phi), math.cos(phi)])
                nrm = np.array([math.cos(phi), math.sin(phi)])
                q0 = root + dirf * 2.0
                q1 = root + dirf * (Lf + 4)
                pprof = [tuple(q0), tuple(q1), (q1[0], 1e3), (q0[0] + 30, 1e3), (q0[0] + 30, q0[1])]
                F_b = K_WIPE * uts * L_b * t * t / (ro + c_gap + 2 * t)
                nose = float(q0[1])
                contact = Lf + ro
                del nrm
            F_bend += F_b
            x0_ = min(q[0] for q in pprof)
            x1_ = max(q[0] for q in pprof)
            lower_blocks.append((sgn, x_t, b, prof, Hb, ro, ro + 2))
            punches.append((sgn, x_t, b, pprof, x0_, x1_ - x0_))
            heels.append((sgn, x_t, b, None))
            depth = max(depth, 0.0)
            nose_z = min(nose_z, nose)
            contact_h = max(contact_h, contact - nose)
            asm.notes.append(f"B{b.number} {op.title}: {a0:.0f}° → {a1:.0f}° — 힘 어림 {F_b / 1000:,.1f} kN"
                             + ("" if kind == tdm.HEM else f" (넘길 각 +{min(sb[b.number], 5.0):.1f}° 스프링백)"))
    # ---- 다이 블록 자리 (공정 전·뒤 제품이 다이 블록 · 패드와 닿지 않게)
    Hb = max(q[4] for q in lower_blocks)
    x_hi = lower_blocks[0][6]
    x_lo = sides[1][1] - lower_blocks[1][6] if len(sides) == 2 else sx0 - 15.0
    rect = [x_lo, x_hi, min(sy0, by0) - 15.0, max(sy1, by1) + 15.0]
    keep = [x_hi - 10.0, x_hi, by0 + 0.2 * (by1 - by0), by1 - 0.2 * (by1 - by0)] if len(sides) == 1 else \
        [x_lo, x_hi, by0 + 0.2 * (by1 - by0), by1 - 0.2 * (by1 - by0)]
    obst_down = [tuple(p[:2]) for p, m in zip(np.vstack(before + after), np.concatenate(mov_b + mov_a))
                 if p[2] < -0.3 and not m]
    rect, left = _rect_fit(rect, obst_down, keep, t + 1.0)
    asm.chk("다이 블록 ↔ 아래로 접힌 부분", f"{left} 점", "0", left == 0)
    # 패드: 판 S 위 (접선 0.5 앞까지), 위로 선 부분 피함
    pad_x1 = -0.5
    pad_x0 = (sides[1][1] + 0.5) if len(sides) == 2 else max(rect[0], sx0 - 5)
    if up_die:
        lean = 0.0
        for sgn, x_t, b, pprof, x0_, wpp in punches:
            lean = min(lean, x0_)
        pad_x1 = min(-0.5, lean - 3.0)
        if len(sides) == 2:
            pad_x0 = max(pad_x0, sides[1][1] - min(q[0] for q in punches[1][3]) + 3.0)
    obst_up = [tuple(p[:2]) for p, m in zip(np.vstack(before + after), np.concatenate(mov_b + mov_a))
               if p[2] > t + 0.3 and not (up_die and m)]
    prect, pleft = _rect_fit([pad_x0, pad_x1, rect[2] + 2, rect[3] - 2], obst_up,
                             [max(pad_x1 - 10, pad_x0), pad_x1, by0 + 0.3 * (by1 - by0), by1 - 0.3 * (by1 - by0)], t + 1.0)
    if prect[1] - prect[0] < 8:
        asm.notes.append("패드 자리가 좁음 — 패드 모양을 제품에 맞춰 깎을 것")
    asm.chk("패드 ↔ 위로 선 부분", f"{pleft} 점", "0", pleft == 0)
    yA, yB = rect[2], rect[3]
    Lb_y = yB - yA
    # ---- 힘 · 패드 스프링
    F_hold = F_hold if kind == tdm.ANGLE else F_bend
    F_pad = PAD_K * F_hold
    if kind == tdm.HEM:
        F_pad = PAD_K * F_bend / 3.0                        # 눌러 접는 힘은 앤빌이 받음 — 패드는 판만 잡음
    tp = max(25.0, _up5(0.04 * Lb_y + 20))
    s_pad = LEAD + contact_h                               # 패드가 판에 닿은 뒤 상형이 더 내려가는 길이
    # 패드 볼트 (네 귀) 먼저, 스프링은 그 사이 빈자리에 들어가는 지름·개수로
    sbd = ds.stripper_for(2.5 * F_pad / 4)
    sb_m, sb_dk, sb_k, sb_thr = ds.STRIPPER[sbd]
    ex_ = max(sb_dk / 2 + 3, 1.5 * sbd)
    sbxy = [(prect[0] + ex_, prect[2] + ex_), (prect[1] - ex_, prect[2] + ex_), (prect[0] + ex_, prect[3] - ex_),
            (prect[1] - ex_, prect[3] - ex_)]
    if prect[1] - prect[0] < 2 * ex_ + 60:                  # 좁은 패드: 볼트를 가운데 한 줄 (양 끝) — 스프링 자리를 넓게
        xm_ = 0.5 * (prect[0] + prect[1])
        sbxy = [(xm_, prect[2] + ex_), (xm_, prect[3] - ex_)]
    spring, sp_xy = _pick_pad_spring(F_pad, s_pad + REGRIND, prect, sbxy, sb_dk / 2)
    if spring is None or len(sp_xy) * spring.rate * spring.preload < F_pad - 1e-6:
        gas, gxy = _pick_gas(F_pad, s_pad + REGRIND, prect, sbxy, sb_dk / 2)
        if gas is not None:
            spring, sp_xy = gas, gxy
            asm.notes.append(f"패드: 코일 스프링으로는 움직임 {s_pad:.0f} mm 에 힘 {F_pad / 1000:,.1f} kN 이 모자라 질소 가스 스프링 "
                             f"(ISO 11901) {gas.label()} × {len(gxy)} — 힘·크기는 어림, 업체 표 (KALLER·DADCO 등) 로 고를 것")
    if spring is None:
        raise ValueError(f"패드 스프링 자리를 못 만듦 (힘 {F_pad / 1000:,.1f} kN, 행정 {s_pad:.0f} mm) — 패드를 넓히세요")
    sgap = spring.installed - spring.pocket
    # ---- 높이 (BDC, 다이 윗면 z = 0)
    ts = max(40.0, _up5(0.08 * max(rect[1] - rect[0] + 200, Lb_y + 60)))
    need_cb = sb_k + s_pad + REGRIND + 1                   # 패드 볼트 머리 자리 (머리 + 움직임 + 재연마)
    tus = max(45.0, _up5(spring.pocket + 12), ts - 5, _up5(need_cb + 12))
    z_ls0 = -Hb - ts
    z_pad_bdc = t
    z_us_bdc = z_pad_bdc + tp + sgap - s_pad              # 상형 세트 밑면 (하사점)
    g_load = max(30.0, float(allb[:, 2].max()) + 15.0)
    travel = g_load + s_pad
    up = travel                                            # 상형은 열린 상태로 그림 (BDC + travel)
    # ---- 부품
    lower = Prim(BOX, (0, 0, z_ls0, 0, 0, ts))             # 크기는 아래에서 정함
    xs_all = [rect[0], rect[1]]
    corners = []
    for (sgn, x_t, b, prof, Hb_i, r_d, x_face), (_, _, _, pprof, x_p, wp) in zip(lower_blocks, punches):
        C = [(x_t + sgn * xi, z) for xi, z in prof]
        C[-1] = (C[-1][0], -Hb)
        corners.append(C)
        if pprof is None:                                  # 캠: 슬라이더 (펀치 끝 + 펀치 + 슬라이더 길이) 까지
            xs_all += [x_t + sgn * x_p, x_t + sgn * (x_p + CAM_REACH)]
            continue
        Q = np.array([(x_t + sgn * xi, z) for xi, z in pprof], float)
        xs_all += [float(Q[:, 0].min()), float(Q[:, 0].max())]
    # 다이 블록 단면: 오른쪽 모서리 (아래 → 위) + (U 면 왼쪽 모서리 위 → 아래, 아니면 왼쪽 끝)
    R = corners[0][::-1]
    if len(corners) == 2:
        die_prof = np.array(R + corners[1], float)
    else:
        die_prof = np.array([(rect[0], -Hb)] + R + [(rect[0], 0.0)], float)
    die_prof = _ccw(die_prof)
    die = Prim(PROF, (yA, Lb_y), poly=die_prof)
    names_die = {tdm.BEND: "벤딩 다이", tdm.UBEND: "U 벤딩 다이", tdm.ANGLE: "각도 벤딩 다이",
                 tdm.FINISH: "앤빌 다이", tdm.PREHEM: "앤빌 다이", tdm.HEM: "헤밍 앤빌", tdm.CAM: "캠 피어싱 앤빌 (다이)"}
    # 펀치 (열린 상태: + up), 패드
    punch_prims = []
    for (sgn, x_t, b, pprof, x_p, wp) in punches:
        if pprof is None:
            continue
        Q = np.array([(x_t + sgn * xi, z) for xi, z in pprof], float)
        z_top = z_us_bdc
        Q[:, 1] = np.minimum(Q[:, 1], z_top)
        if sgn < 0:
            Q = Q[::-1]
        Q = _ccw(_dedupe(Q))
        Q[:, 1] += up
        punch_prims.append(Prim(PROF, (yA, Lb_y), poly=Q))
    pad = Prim(BOX, (prect[0], prect[2], z_pad_bdc + up - s_pad, prect[1] - prect[0], prect[3] - prect[2], tp))
    # 힐 블록
    heel_prims = []
    e_h = max(15.0, 3 * t)
    for sgn, x_t, b, xh in heels:
        if xh is None:
            continue
        wh = 35.0
        z_heel = t + e_h
        x0h = x_t + sgn * xh
        x1h = x0h + sgn * wh
        xa, xb = min(x0h, x1h), max(x0h, x1h)
        heel_prims.append(Prim(BOX, (xa, yA, -Hb, xb - xa, Lb_y, Hb + z_heel)))
        xs_all += [xa, xb]
    # ---- 다이 세트 크기 · 가이드
    X0, X1 = min(xs_all), max(xs_all)
    post_d = 25.0 if max(X1 - X0, Lb_y) < 250 else 32.0 if max(X1 - X0, Lb_y) < 450 else 38.0
    Ls = _up5((X1 - X0) + 2 * (post_d + 35))
    Ws = _up5(Lb_y + 2 * 30)
    xc, yc = 0.5 * (X0 + X1), 0.5 * (yA + yB)
    lower.p = (xc - Ls / 2, yc - Ws / 2, z_ls0, Ls, Ws, ts)
    z_us_open = z_us_bdc + up
    upper_shoe = Prim(BOX, (xc - Ls / 2, yc - Ws / 2, z_us_open, Ls, Ws, tus))
    z_top_open = z_us_open + tus
    asm.add("하형 다이 세트", 1, "SS400 (FC250)", f"{Ls:.0f} × {Ws:.0f} × {ts:.0f}", [lower])
    asm.add(names_die[kind], 1, "SKD11 HRC 58~62", f"{np.ptp(die_prof[:, 0]):.0f} × {Lb_y:.0f} × {Hb:.0f}", [die],
            note=(f"제품 안쪽 받침 · 옆면에 다이 구멍 (캠 펀치 받음) · 모서리 R{bs[0].r:g}" if cam else
                  f"모서리 R{bs[0].r:g} (제품 안쪽 R) · 옆면 스프링백 빠짐 {max(sb.values()):.1f}° · R 부 래핑 Ra 0.4"
                  if not up_die else f"제품 밑면 받침 · 절곡 바깥 R{bs[0].r + t:g} 앞까지"))
    for k, Q in enumerate(punch_prims):
        sgn, x_t, b, pprof, x_p, wp = punches[k]
        nm = {tdm.BEND: "와이핑 펀치", tdm.UBEND: "와이핑 펀치", tdm.ANGLE: "각도 펀치", tdm.FINISH: "넘김 펀치",
              tdm.PREHEM: "예비 헤밍 펀치", tdm.HEM: "헤밍 펀치"}[kind]
        e = Q.poly
        asm.add(nm + (f" (B{b.number})" if len(punch_prims) > 1 else ""), 1, "SKD11 HRC 58~62",
                f"{np.ptp(e[:, 0]):.0f} × {Lb_y:.0f} × {np.ptp(e[:, 1]):.0f}", [Q], upper=True,
                note=(f"틈 {c_gap:.2f} (t + {c_gap / t * 100 - 100:.0f} %) · 끝 R{max(2 * t, 3.0):g} · 끝 스프링백 "
                      f"{sb[b.number]:.1f}°" if kind in (tdm.BEND, tdm.UBEND) else "면 래핑 Ra 0.4"))
    if heel_prims:
        asm.add("힐 블록", len(heel_prims), "S50C (HRC 40~45) + 마모판 SKD11", f"35 × {Lb_y:.0f} × {Hb + t + e_h:.0f}",
                heel_prims, note=f"펀치 옆 힘 받침 — 펀치가 판에 닿기 {e_h:.0f} mm 전에 물림, 닿는 면 마모판 (6t 볼트 고정)")
    asm.add("패드", 1, "S50C (HRC 40~45)", f"{prect[1] - prect[0]:.0f} × {prect[3] - prect[2]:.0f} × {tp:.0f}", [pad],
            upper=True, note=f"판 누름 {F_pad / 1000:,.1f} kN · 펀치보다 "
                             f"{LEAD:g} 먼저 닿음 · 움직임 {s_pad:.1f}")
    asm.add("상형 다이 세트", 1, "SS400 (FC250)", f"{Ls:.0f} × {Ws:.0f} × {tus:.0f}", [upper_shoe], upper=True)
    # ---- 가이드 포스트 · 부시 (네 귀)
    px, py = Ls / 2 - post_d / 2 - 15, Ws / 2 - post_d
    corners = [(xc + sx * px, yc + sy * py) for sx in (-1, 1) for sy in (-1, 1)]
    bush_o = post_d + 12
    # 펀치가 판에 닿을 때 (BDC + contact_h) 부시에 10 mm 물리고, BDC 에서 상형 윗면 3 mm 아래
    z_top_bdc = z_us_bdc + tus
    post_L = math.floor((z_top_bdc - 3 - z_ls0) / 5) * 5
    eng_contact = z_ls0 + post_L - (z_us_bdc + contact_h)
    bush_ext = 0.0
    if eng_contact < 10:
        bush_ext = min(_up5(10 - eng_contact), max(0.0, z_us_bdc - 5 - (z_ls0 + ts)) // 5 * 5)
        eng_contact += bush_ext
    for x, y in corners:
        lower.holes.append(Hole(x, y, post_d, "압입", z_ls0, ts, f"Ø{post_d:g} H7 (포스트 압입) 관통"))
        upper_shoe.holes.append(Hole(x, y, bush_o, "압입", z_us_open, tus, f"Ø{bush_o:g} H7 (부시 압입) 관통"))
    asm.add("가이드 포스트", 4, "SUJ2 HRC 60", f"Ø{post_d:g} × {post_L:.0f}",
            [axi(x, y, [(z_ls0, post_L - 2, post_d / 2, post_d / 2), (z_ls0 + post_L - 2, 2, post_d / 2, post_d / 2 - 1.5)])
             for x, y in corners], std=True, order=f"가이드 포스트 Ø{post_d:g} L{post_L:.0f} (압입형)")
    Lbush = tus + bush_ext
    asm.add("가이드 부시", 4, "SUJ2 / 동합금", f"Ø{post_d:g} 안 × Ø{bush_o:g} 밖 × {Lbush:.0f}",
            [axi(x, y, [(z_us_open - bush_ext, Lbush, bush_o / 2, bush_o / 2)], bore=post_d / 2) for x, y in corners],
            std=True, upper=True, order=f"가이드 부시 Ø{post_d:g} × Ø{bush_o:g} L{Lbush:.0f}"
                                         + (f" (세트 아래로 {bush_ext:.0f} 나옴, 플랜지 붙임)" if bush_ext else ""))
    asm.chk("가이드 물림 (펀치가 판에 닿을 때)", f"{eng_contact:.0f} mm", "≥ 10 mm", eng_contact >= 10 - 1e-6)
    # ---- 볼트 · 다우얼: 다이 블록 · 힐 (하형 세트 밑에서), 펀치 (상형 세트 위에서)
    M = ds.bolt_for(max(Lb_y, np.ptp(die_prof[:, 0])))
    n_y = max(2, int(math.ceil(Lb_y / 120.0)) + 1)
    dx_ = float(die_prof[:, 0].min()), float(die_prof[:, 0].max())
    xs_b = _row(dx_[0] + 1.5 * M + 5, dx_[1] - 1.5 * M - 5, 2 if dx_[1] - dx_[0] > 6 * M + 30 else 1)
    ys_b = _row(yA + 2 * M, yB - 2 * M, n_y)
    pts = [(x, y) for x in xs_b for y in ys_b]
    pr_, L_, e_ = _bolts_down(asm, die, lower, pts, M, z_ls0, ts, -Hb, Hb, names_die[kind])
    asm.add(f"육각 구멍 붙이 볼트 M{M} (다이)", len(pts), "SCM435 (12.9)", f"M{M} × {L_:.0f}", pr_, std=True,
            order=f"JIS B 1176 M{M} × {L_:.0f}", note=f"물림 {e_:.0f} mm")
    dwp = [(xs_b[0], 0.5 * (ys_b[0] + ys_b[1])), (xs_b[-1], 0.5 * (ys_b[-2] + ys_b[-1]))]   # 볼트 사이
    pr_, Ld_ = _dowels(die, lower, dwp, float(M), z_ls0, ts, -Hb, Hb)
    asm.add("다우얼 핀 (다이)", 2, "SUJ2 (m6)", f"Ø{M:g} × {Ld_:.0f}", pr_, std=True, order=f"평행 핀 ISO 8734 Ø{M:g} m6 × {Ld_:.0f}")
    if heel_prims:
        hp, hpin = [], []
        for hpr in heel_prims:
            x0h, y0h, z0h, dxh, dyh, dzh = hpr.p
            ptsh = [(x0h + dxh / 2, y) for y in _row(yA + 2 * M, yB - 2 * M, n_y)]
            p1, Lh, eh = _bolts_down(asm, hpr, lower, ptsh, M, z_ls0, ts, -Hb, dzh, "힐 블록")
            hp += p1
            p2, Ldh = _dowels(hpr, lower, [(x0h + dxh / 2, 0.5 * (ptsh[0][1] + ptsh[1][1]))], float(min(M, 10)), z_ls0, ts,
                              -Hb, dzh)
            hpin += p2
        asm.add(f"육각 구멍 붙이 볼트 M{M} (힐 블록)", len(hp), "SCM435 (12.9)", f"M{M} × {Lh:.0f}", hp, std=True,
                order=f"JIS B 1176 M{M} × {Lh:.0f}")
        asm.add("다우얼 핀 (힐 블록)", len(hpin), "SUJ2 (m6)", f"Ø{min(M, 10):g} × {Ldh:.0f}", hpin, std=True,
                order=f"평행 핀 ISO 8734 Ø{min(M, 10):g} m6 × {Ldh:.0f}")
    pb, ppin = [], []
    for Q in punch_prims:
        e = Q.poly
        xm = float(e[:, 0].mean()) if np.ptp(e[:, 0]) < 3 * M + 10 else float(e[:, 0].min() + e[:, 0].max()) / 2
        ptsp = [(xm, y) for y in _row(yA + 2 * M, yB - 2 * M, n_y)]
        hgt = float(e[:, 1].max() - e[:, 1].min())
        p1, Lp, ep = _bolts_down(asm, Q, upper_shoe, ptsp, M, z_us_open, tus, float(e[:, 1].min()), hgt, "펀치", upper=True)
        pb += p1
        p2, Ldp = _dowels(Q, upper_shoe, [(xm, 0.5 * (ptsp[0][1] + ptsp[1][1]))] if len(ptsp) > 1 else [(xm, yc)],
                          float(min(M, 10)), z_us_open, tus, float(e[:, 1].min()), hgt, upper=True)
        ppin += p2
    if pb:
        asm.add(f"육각 구멍 붙이 볼트 M{M} (펀치)", len(pb), "SCM435 (12.9)", f"M{M} × {Lp:.0f}", pb, std=True, upper=True,
                order=f"JIS B 1176 M{M} × {Lp:.0f}")
        asm.add("다우얼 핀 (펀치)", len(ppin), "SUJ2 (m6)", f"Ø{min(M, 10):g} × {Ldp:.0f}", ppin, std=True, upper=True,
                order=f"평행 핀 ISO 8734 Ø{min(M, 10):g} m6 × {Ldp:.0f}")
    for cu in cam_units:
        _cam_unit(asm, cu, die, lower, upper_shoe, z_ls0, ts, z_us_bdc, up, yA, yB, Hb, t)
    # ---- 패드 볼트 (스트리퍼 볼트) · 스프링
    grip = sgap + tus
    sh_L = ds.down_std(grip - need_cb, LONG_STRIPPER_L)
    cb_d = grip - sh_L
    z_pad_open = pad.p[2]
    for x, y in sbxy:
        pad.holes.append(Hole(x, y, ds.SHCS[sb_m][5], "탭", z_pad_open + tp - sb_thr - 2, sb_thr + 2,
                              f"M{sb_m} 탭 깊이 {sb_thr + 2:g} (패드 볼트)"))
        upper_shoe.holes.append(Hole(x, y, sbd + 1, "통과", z_us_open, tus, f"Ø{sbd + 1:g} 통과, 자리 Ø{sb_dk + 1:g} 깊이 {cb_d:.1f}",
                                     cb=(sb_dk + 1, z_top_open - cb_d, cb_d)))
    asm.add("패드 볼트 (스트리퍼 볼트)", len(sbxy), "SCM435", f"어깨 Ø{sbd:g} × {sh_L:.0f} (M{sb_m})",
            [axi(x, y, [(z_pad_open + tp - sb_thr, sb_thr, sb_m / 2, sb_m / 2), (z_pad_open + tp, sh_L, sbd / 2, sbd / 2),
                        (z_pad_open + tp + sh_L, sb_k, sb_dk / 2, sb_dk / 2)],
                 socket=(z_pad_open + tp + sh_L + sb_k, 0.6 * sb_k, HEX_KEY.get(sb_m, 0.8 * sb_m), -1)) for x, y in sbxy],
            std=True, upper=True, order=f"스트리퍼 볼트 (ISO 7379) Ø{sbd:g} × {sh_L:.0f} M{sb_m}",
            note=f"머리 자리 깊이 {cb_d:.1f} (머리 {sb_k:g} + 패드 움직임 {s_pad:.1f} + 재연마 {REGRIND:g} + 1)")
    asm.chk("패드 볼트 머리 자리", f"깊이 {cb_d:.1f} mm", f"≥ {need_cb:.1f} · ≤ 상형 세트 − 5 ({tus - 5:.0f})",
            need_cb - 1e-6 <= cb_d <= tus - 5)
    for x, y in sp_xy:
        upper_shoe.holes.append(Hole(x, y, spring.D + 1, "스프링 자리", z_us_open, spring.pocket,
                                     f"Ø{spring.D + 1:g} 깊이 {spring.pocket:.1f} (스프링 자리)", side="밑면"))
    gas_ = isinstance(spring, GasPick)
    asm.add("가스 스프링 (패드)" if gas_ else "다이 스프링 (패드)", len(sp_xy),
            "질소 가스 스프링 (ISO 11901)" if gas_ else "SWOSC-V (ISO 10243)", spring.label(),
            [axi(x, y, [(z_pad_open + tp, spring.installed - spring.body, spring.rod / 2, spring.rod / 2),
                        (z_pad_open + tp + spring.installed - spring.body, spring.body, spring.D / 2, spring.D / 2)])
             if gas_ else
             axi(x, y, [(z_pad_open + tp, spring.installed, spring.D / 2 - 0.5, spring.D / 2 - 0.5)],
                 bore=ds.SPRING_D[spring.D] / 2 + 0.3) for x, y in sp_xy], std=True, upper=True,
            order=(f"질소 가스 스프링 Ø{spring.D:g} 초기 {spring.f_each / 1000:.1f} kN 행정 {spring.stroke_std:g} (업체 표 확인)"
                   if gas_ else f"다이 스프링 ISO 10243 Ø{spring.D:g} × {spring.L:g} {spring.color}"),
            note=f"끼움 눌림 {spring.preload:.1f} → 하사점 {spring.preload + s_pad:.1f}, 판에 닿을 때 "
                 f"{spring.n * spring.rate * spring.preload / 1000:,.2f} kN · 하사점 {spring.f_max / 1000:,.2f} kN")
    f_contact = len(sp_xy) * spring.rate * spring.preload
    asm.chk("패드 힘 (판에 닿을 때)", f"{f_contact / 1000:,.2f} kN",
            f"≥ {F_pad / 1000:,.2f} kN", f_contact >= F_pad - 1e-6)
    if gas_:
        asm.chk("가스 스프링 행정", f"{spring.stroke:.1f} mm 씀", f"≤ 규격 행정 {spring.stroke_std:g} × 0.9", spring.stroke <= 0.9 * spring.stroke_std + 1e-6)
    else:
        asm.chk("스프링 끝 휨", f"{spring.defl_pct:.1f} %", f"≤ {spring.limit_pct:.1f} %", spring.defl_pct <= spring.limit_pct + 1e-6)
    # ---- 위치 게이지 핀 (판 S 끝, 다이 블록 위) — 접는 쪽 반대 끝과 옆
    gpins = []
    sp_edge = sx0 - 4.0
    if len(sides) == 1 and sp_edge - 4 > rect[0] + 3:
        for y in (sy0 + 0.25 * (sy1 - sy0), sy0 + 0.75 * (sy1 - sy0)):
            gpins.append((sp_edge, y))
    xm_s = 0.5 * (max(sx0, rect[0] + 8) + min(sx1, rect[1] - 8))
    if sy0 - 4 - 4 > rect[2] + 3:
        gpins.append((xm_s, sy0 - 4.0))
    gpin_prims = []
    for x, y in gpins:
        die.holes.append(Hole(x, y, 8.0, "H7", -12.0, 12.0, "Ø8 H7 리머 깊이 12 (게이지 핀)"))
        gpin_prims.append(_pin(x, y, -12.0, 8.0, 12.0 + t + 4))
        if prect[0] - 4.5 < x < prect[1] + 4.5 and prect[2] - 4.5 < y < prect[3] + 4.5:
            pad.holes.append(Hole(x, y, 10.0, "통과", pad.p[2], tp, "Ø10 통과 (게이지 핀 피함)"))
    if gpin_prims:
        asm.add("게이지 핀", len(gpin_prims), "SUJ2 (m6)", f"Ø8 × {12 + t + 4:.0f}", gpin_prims, std=True,
                order=f"평행 핀 ISO 8734 Ø8 m6 × {ds.up_std(12 + t + 4, ds.DOWEL_L):.0f} (윗면 모따기)",
                note=f"제품 판 끝 자리 (판 위로 {t + 4 - t:.0f} 나옴)")
    else:
        asm.notes.append("게이지: 제품 끝이 다이 블록 밖 — 하형 세트 위 게이지 블록으로 (설계자)")
    # ---- 스톱 블록 · 클램프 홈 · 아이볼트 탭
    sbw = 30.0
    sbh = (z_us_bdc - 0.5) - (z_ls0 + ts)
    sxs = [xc + sgn * (Ls / 2 - post_d - 40) for sgn in (-1, 1)]
    stop = [Prim(BOX, (x - sbw / 2, yc - sbw / 2, z_ls0 + ts, sbw, sbw, sbh)) for x in sxs]
    clash = any(min(abs(x - h.p[0]), abs(x - h.p[0] - h.p[3])) < sbw / 2 + 2 for x in sxs for h in heel_prims)
    if sbh > 5 and not clash:
        for x, blk in zip(sxs, stop):
            lower.holes.append(Hole(x, yc, 9.0, "통과", z_ls0, ts, "Ø9 통과, 자리 Ø14 깊이 8.6 (스톱 블록)", cb=(14.0, z_ls0, 8.6),
                                    side="밑면"))
            blk.holes.append(Hole(x, yc, 6.8, "탭", z_ls0 + ts, 15, "M8 탭 깊이 15 (밑면, 드릴 Ø6.8)", side="밑면"))
        asm.add("스톱 블록", 2, "S50C", f"{sbw:g} × {sbw:g} × {sbh:.1f}", stop,
                note="하사점에서 상형 세트와 0.5 틈 (각도는 심으로 맞춤)")
    slot_w = 22.0 if max(Ls, Ws) < 800 else 26.0
    slot_d = min(max(post_d + 35 - post_d / 2 - 8, 20.0), 40.0)
    for shoe in (lower, upper_shoe):
        for sxn in (-1, 1):
            for yy in (yc - 0.5 * (Ws / 2 - post_d), yc + 0.5 * (Ws / 2 - post_d)):
                shoe.cuts.append((_uslot(xc + sxn * Ls / 2, yy, slot_w, slot_d, sxn), 0.0, shoe.p[2] - 1, shoe.p[5] + 2,
                                  "slot"))
    for shoe in (lower, upper_shoe):
        kg = _volume(shoe) * DENSITY
        m_ = 12 if kg <= 100 else 16 if kg <= 200 else 20 if kg <= 300 else 24
        tap = {12: 10.2, 16: 14.0, 20: 17.5, 24: 21.0}[m_]
        dep = 1.5 * m_ + 5
        x0_, y0_, z0_, dx__, dy__, dz__ = shoe.p
        if dz__ < m_ + 10:
            continue
        for sg in (-1, 1):
            for xx in (x0_ + dx__ / 4, x0_ + 3 * dx__ / 4):
                shoe.holes.append(Hole(xx, (y0_ + dy__) if sg > 0 else y0_, tap, "탭", z0_ + dz__ / 2, dep,
                                       f"M{m_} 탭 깊이 {dep:.0f} (옆면 아이볼트, 드릴 Ø{tap:g})",
                                       side="앞면" if sg < 0 else "뒷면", axis="-y" if sg > 0 else "+y"))
    # ---- 프레스 · 점검
    from . import costing as cs
    mlist = machines if machines is not None else cs.DEFAULT_MACHINES
    f_spring = spring.f_max
    F_total = F_bend + f_spring
    need_t = F_total * cs.SAFETY / dc.TON
    stroke = travel + 10
    long_ = [m for m in mlist if float(m.get("stroke") or cs.default_stroke(m.get("capacity", 100))) >= stroke]
    mach, ok = cs.pick(long_ or mlist, cs.PRESS, need_t, height=max(depth, t))
    if mach is not None and ok and float(mach.get("stroke") or cs.default_stroke(mach["capacity"])) < stroke:
        ok = False
    asm.chk("프레스", f"{mach['name'] if mach else '없음'} (필요 {need_t:,.0f} tf, 행정 ≥ {stroke:.0f})",
            f"(굽힘 {F_bend / 1000:,.1f} + 패드 스프링 {f_spring / 1000:,.1f} kN) × {cs.SAFETY:g}", ok)
    asm.chk("다이 블록 ↔ 플랜지 끝 (하사점)", f"{Hb - depth:.0f} mm", "≥ 5 mm (하형 세트에 닿지 않음)", Hb - depth >= 5 - 1e-6)
    asm.notes = [f"{op.label}: {op.detail}",
                 f"굽힘 {F_bend / 1000:,.1f} kN + 패드 스프링 (하사점) {f_spring / 1000:,.1f} kN → 권장 프레스 {need_t:,.0f} tf"
                 + (f" — {mach['name']}" if mach else ""),
                 f"높이: 닫힌 {z_top_bdc - z_ls0:.1f} · 열린 {z_top_open - z_ls0:.1f} mm · 행정 ≥ {stroke:.0f} "
                 f"(올려 놓는 틈 {g_load:.0f} + 패드 움직임 {s_pad:.1f})"] + asm.notes + [
                 "표준품 치수는 일반값 — 주문 전에 업체 (MISUMI 등) 표로 확인. 스프링백 각은 모멘트 법 어림 — 시타 뒤 다이 옆면 · "
                 "펀치 끝을 고쳐 맞춤"]
    # ---- 금형 좌표를 하형 세트 밑면 z = 0, 가운데 0 으로
    dz = -z_ls0
    for p in asm.parts:
        for pr in p.prims:
            shift_prim(pr, -xc, -yc, dz)
    work = []
    for P, tag in [(P, "before") for P in before] + [(P, "after") for P in after]:
        Q = np.asarray(P, float).copy()
        Q[:, 0] -= xc
        Q[:, 1] -= yc
        Q[:, 2] += dz
        work.append((Q, tag))
    spec = [("공정", op.label), ("굽힘력 / 패드 스프링", f"{F_bend / 1000:,.1f} / {f_spring / 1000:,.1f} kN"),
            ("필요 프레스", f"{need_t:,.0f} tf → {mach['name'] if mach else '-'}"),
            ("스프링백 보정", " · ".join(f"B{n} {v:.1f}°" for n, v in sb.items())),
            ("패드 스프링", spring.label() + f" × {len(sp_xy)}")]
    shut = z_top_bdc - z_ls0
    a = DieAssy(f"{op.no}차 {op.title}", asm.parts, Ls, Ws, shut, F_bend, asm.notes, None, [], asm.checks, (0.0, 0.0),
                z_top_open - z_ls0, stroke, (0.0, 0.0), spring, [], {"bend_kn": F_bend / 1000, "spring_kn": f_spring / 1000,
                                                                       "need_tf": need_t, "machine": mach["name"] if mach else "",
                                                                       "ok": bool(ok)})
    a.spec = spec
    a.work = work
    a.y_cut = float(0.5 * (by0 + by1) - yc)
    return a


# 질소 가스 스프링 (ISO 11901-1 꼴) 어림 표: 바깥 Ø → 초기 힘 (kN) — 업체마다 다름 (KALLER X · DADCO 90.10 등 비슷한 급)
GAS = [(32, 1.7), (38, 3.5), (45, 5.0), (50, 7.5), (63, 10.0), (75, 18.0), (95, 30.0), (120, 50.0)]
GAS_STROKE = (16, 25, 38, 50, 63, 80, 100, 125)
GAS_RISE = 1.4          # 끝 행정에서 힘 / 초기 힘 (어림)


class GasPick:
    """질소 가스 스프링 (SpringPick 과 같은 이름의 값을 가짐)."""
    color = "질소"
    cls = "가스"

    def __init__(self, D, f_each, stroke, stroke_std, n):
        self.D, self.f_each, self.stroke, self.stroke_std, self.n = D, f_each, stroke, stroke_std, n
        self.body = stroke_std + 0.6 * D + 25                # 몸통 길이 (어림)
        self.rod = 0.5 * D
        self.L = self.body + stroke_std                     # 다 나온 길이
        self.installed = self.L - 2.0                       # 2 mm 눌러 끼움
        self.pocket = min(self.body - 10.0, 60.0)
        self.rate = f_each * (GAS_RISE - 1) / stroke_std
        self.preload = f_each / self.rate
        self.f_pre = n * f_each
        self.f_max = n * f_each * (1 + (GAS_RISE - 1) * (stroke + 2) / stroke_std)
        self.defl_pct, self.limit_pct = 0.0, 100.0

    def label(self):
        return f"가스 Ø{self.D:g} × 행정 {self.stroke_std:g} ({self.f_each / 1000:.1f} kN)"


def _pack(rect, D, gap, bolts, r_bolt):
    """패드 위 둥근 자리 (지름 D, 서로 gap 띄움, 볼트 피함) — 촘촘한 후보에서 가운데부터 욕심껏, 나중에 x · y 순으로."""
    x0, x1, y0, y1 = rect
    e = D / 2 + 4
    if x1 - x0 < 2 * e or y1 - y0 < 2 * e:
        return []
    st = max((D + gap) / 3.0, 2.0)
    xs = np.arange(x0 + e, x1 - e + 1e-9, st) if x1 - x0 > 2 * e + 1e-9 else np.array([0.5 * (x0 + x1)])
    ys = np.arange(y0 + e, y1 - e + 1e-9, st) if y1 - y0 > 2 * e + 1e-9 else np.array([0.5 * (y0 + y1)])
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    cand = sorted(((float(x), float(y)) for x in xs for y in ys), key=lambda q: (abs(q[0] - cx) + abs(q[1] - cy), q))
    out = []
    for x, y in cand:
        if all(math.hypot(x - a, y - b) >= D / 2 + r_bolt + 2 for a, b in bolts) and \
                all(math.hypot(x - a, y - b) >= D + gap for a, b in out):
            out.append((x, y))
    return sorted(out)


def _pick_gas(force, stroke, rect, bolts, r_bolt):
    x0, x1, y0, y1 = rect
    std = next((s_ for s_ in GAS_STROKE if s_ * 0.9 >= stroke), None)
    if std is None:
        return None, []
    for D, f_kn in GAS:
        e = D / 2 + 4
        if x1 - x0 < 2 * e or y1 - y0 < 2 * e:
            continue
        slots = _pack(rect, D, 8.0, bolts, r_bolt)
        n = max(int(math.ceil(force / (f_kn * 1000))), 1)
        n = max(n, 2) if len(slots) >= 2 else n          # 둘 넘게 들어가면 둘 이상 (기울지 않게)
        if slots and n <= len(slots):
            step = len(slots) / n
            return GasPick(float(D), f_kn * 1000, stroke, float(std), n), [slots[int(i * step)] for i in range(n)]
    return None, []


CAM_REACH = 150.0       # 캠: 펀치 끝 (열림) 에서 슬라이더 뒤까지 금형 자리


def _cam_unit(asm, cu, die, lower, upper_shoe, z_ls0, ts, z_us_bdc, up, yA, yB, Hb, t):
    """캠 유닛 (표준품: 슬라이더 · 드라이버 · 리턴 스프링) + 가로 펀치 + 앤빌 옆면 다이 구멍. 슬라이더는 열린 상태 (물러남)."""
    sgn, x_t, b, hz, s_c, clr_c, x_face, D_f = cu
    if not hz:
        return
    ys = [q[1] for q, _, _ in hz]
    zs = [q[2] for q, _, _ in hz]
    dmax = max(d for _, d, _ in hz)
    p_out = 25.0                                           # 슬라이더 앞면에서 펀치가 나온 길이
    xa = x_t + sgn * (x_face + t + 5.0 + p_out)            # 슬라이더 앞면 (열림)
    xb = xa + sgn * 80.0
    y0 = max(min(ys) - max(30.0, dmax + 15), yA)
    y1 = min(max(ys) + max(30.0, dmax + 15), yB)
    z0 = -Hb
    z1 = max(zs) + max(25.0, dmax)
    sx0, sx1 = min(xa, xb), max(xa, xb)
    slider = Prim(BOX, (sx0, y0, z0, sx1 - sx0, y1 - y0, z1 - z0))
    # 드라이버: 상형에 붙은 45° 쐐기 (슬라이더 뒤 위) — 열린 상태
    xr = xb                                                # 슬라이더 뒤 끝
    z_bdc_contact = z1                                     # 하사점에서 쐐기 아래 끝 = 슬라이더 윗면 높이
    wedge = [(xr - sgn * 30.0, z_bdc_contact + up), (xr + sgn * 15.0, z_bdc_contact + up),
             (xr + sgn * 15.0, z_us_bdc + up), (xr - sgn * (30.0 + (z_us_bdc - z_bdc_contact)), z_us_bdc + up)]
    W = np.array(wedge)
    if sgn < 0:
        W = W[::-1]
    drv = Prim(PROF, (y0, y1 - y0), poly=_ccw(W))
    asm.add("캠 슬라이더 (캠 유닛)", 1, "캠 유닛 표준품", f"{sx1 - sx0:.0f} × {y1 - y0:.0f} × {z1 - z0:.0f} · 이송 {s_c:.1f}",
            [slider], std=True, order=f"캠 유닛 (다이 붙임형) 이송 ≥ {s_c:.0f} · 힘 ≥ 펀치 힘 × 1.3 (MISUMI·산쿄 등 표준품)",
            note="리턴 스프링 내장 — 하사점 뒤 펀치를 빼냄")
    asm.add("캠 드라이버", 1, "캠 유닛 표준품 (SKD11 마모판)", f"45° 쐐기 · 폭 {y1 - y0:.0f}", [drv], std=True, upper=True,
            order="캠 유닛 드라이버 (같은 표준품)")
    # 가로 펀치 (PROF ax x: 단면 (y, z) 원, x 로 민 것) — 끝 = 플랜지 바깥 5 mm (열림)
    pp_ = []
    for q, d_h, i in hz:
        tip = x_t + sgn * (x_face + t + 5.0)
        tail = xa + sgn * 20.0
        x_lo_, x_hi_ = min(tip, tail), max(tip, tail)
        circ = [(q[1] + d_h / 2 * math.cos(a), q[2] + d_h / 2 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        pp_.append(Prim(PROF, (x_lo_, x_hi_ - x_lo_), poly=np.array(circ), ax="x"))
        dd = d_h + 2 * clr_c
        die.holes.append(Hole(x_t + sgn * x_face, q[1], dd, "다이 구멍", q[2], 3.0 * t + 2,
                              f"Ø{dd:.3f} 다이 구멍 깊이 {3 * t + 2:.0f} → Ø{dd + 1:.1f} 빠짐 (옆면, 캠 펀치)",
                              side="옆면", axis="-x" if sgn > 0 else "+x"))
        die.holes.append(Hole(x_t + sgn * (x_face - 3.0 * t - 2), q[1], dd + 1.0, "빠짐", q[2], 25.0,
                              f"Ø{dd + 1:.1f} 빠짐 (슬러그 — 아래 슬러그 구멍으로)", side="옆면", axis="-x" if sgn > 0 else "+x"))
    names = sorted({round(d_h, 1) for _, d_h, _ in hz})
    asm.add("캠 피어싱 펀치 " + " · ".join(f"Ø{d:g}" for d in names), len(pp_), "SKH51 HRC 62~64",
            f"Ø{names[0]:g} × {abs(tail - tip):.0f}", pp_, std=True,
            order="머리 붙임 펀치 (슬라이더 리테이너에 고정, 길이 지정)",
            note=f"슬라이더에 고정 · 하사점에서 플랜지를 지나 1 mm 들어감 · 클리어런스 한쪽 {clr_c:.3f}")


LONG_STRIPPER_L = ds.STRIPPER_L + (130, 140, 150, 160, 180, 200)   # 어깨 길이 (긴 것은 업체 주문 길이)


def _pick_pad_spring(force, stroke, rect, bolts, r_bolt, pocket_max=60.0):
    """패드 스프링: 지름마다 패드 위 빈자리 (볼트 피함) 를 세고, 그 개수 안에서 판에 닿을 때 힘 ≥ force ·
    끝 휨 ≤ 오래 쓰기 한계 · 스프링 사이 ≥ 행정 + 3 인 것 — 개수 적고, 지름 작고, 짧은 것. 없으면 자리 가득 가장 센 것."""
    x0, x1, y0, y1 = rect
    best, strongest = None, None
    for D in sorted(ds.SPRING_D):
        e = D / 2 + 4
        if x1 - x0 < 2 * e or y1 - y0 < 2 * e:
            continue
        slots = _pack(rect, D, 6.0, bolts, r_bolt)
        if not slots:
            continue
        for n in range(2, len(slots) + 1):
            for cls in ds.SPRING_CLASS:
                for L in ds.SPRING_L:
                    k = ds.spring_rate(D, L, cls)
                    allow = ds.LIFE * ds.SPRING_CLASS[cls][2] * L
                    s0 = max(force / (n * k), 1.0)
                    inst = L - s0
                    pocket = min(pocket_max, inst - 15.0)
                    if pocket < 0.3 * inst or inst - pocket < stroke + 3:
                        continue
                    if s0 + stroke <= allow:
                        key = (n, D, L)
                        if best is None or key < best[0]:
                            best = (key, ds.SpringPick(D, float(L), cls, n, k, s0, stroke, pocket, inst), slots)
                    s_max = allow - stroke                      # 힘 모자랄 때: 끝 휨 한계에서 가장 센 것
                    if s_max >= 1.0:
                        inst2 = L - s_max
                        pk2 = min(pocket_max, inst2 - 15.0)
                        if pk2 >= 0.3 * inst2 and inst2 - pk2 >= stroke + 3:
                            f = len(slots) * k * s_max
                            if strongest is None or f > strongest[0]:
                                strongest = (f, ds.SpringPick(D, float(L), cls, len(slots), k, s_max, stroke, pk2, inst2),
                                             slots)
            if best is not None and best[0][1] == D:
                break
    if best is not None:
        sp, slots = best[1], best[2]
        # 고르게: 자리 가운데부터 n 개 대칭에 가깝게
        cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        order = sorted(slots, key=lambda q: (abs(q[1] - cy), abs(q[0] - cx)))
        if sp.n < len(slots):
            step = len(slots) / sp.n
            pick = [slots[int(i * step)] for i in range(sp.n)]
        else:
            pick = slots
        del order
        return sp, pick
    if strongest is not None:
        return strongest[1], strongest[2]
    return None, []


def _dedupe(Q, tol=1e-6):
    out = [Q[0]]
    for q in Q[1:]:
        if np.linalg.norm(q - out[-1]) > tol:
            out.append(q)
    if np.linalg.norm(out[0] - out[-1]) <= tol:
        out.pop()
    return np.array(out)


def _ccw(P):
    P = _dedupe(np.asarray(P, float))
    a = 0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))
    return P if a > 0 else P[::-1]
