#!/usr/bin/env python3
"""NFC coil generator + inductance estimator for the NT3H2111 antenna.

Standalone (no KiCad, no numpy). Run it from a normal shell, not the KiCad console:

    python3 tools/nfc_coil.py rect --width 40 --height 46 --radius 4 --turns 4,5,6
    python3 tools/nfc_coil.py hex --size 32.8 --turns 7          # Koda's coil
    python3 tools/nfc_coil.py rect -W 36:44:2 -H 46 --turns 5 --track 0.3,0.5
    python3 tools/nfc_coil.py rect -W 40 -H 46 -r 4 --turns 5 --write
    python3 tools/nfc_coil.py selftest

Numeric options take a single value, a comma list (4,5,6) or an inclusive range
(start:stop:step); every combination is evaluated. --write saves each combination
as a footprint in lib/nfc-coils.pretty.

Footprint layout (origin = coil centre, leads exit on the left; rotate it on the board):
  * pad 1: outer end of the spiral (F.Cu), on the outer track just above the
    left-side midpoint -> route to U3 LA.
  * pad 2: via-pad at the inner end -> route a straight B.Cu track left along
    y = 0 under the turns, via up outside the coil, then to U3 LB. The dashed
    Dwgs.User line shows the bridge the inductance estimate assumes.
  * The spiral is copper graphics between pads 1 and 2; the footprint is a net
    tie ("1, 2") so DRC accepts the deliberate LA-LB connection.
  * A rule area (no copper pour, both layers) covers the coil plus --keepout margin.

Inductance: Neumann integral over the actual drawn path (spiral, stub, vias and the
assumed B.Cu bridge) as filaments, with the track cross-section handled by its
geometric mean distance 0.2235*(w+t). Parallel/collinear segment pairs and pairs
sharing a vertex use closed forms, the rest adaptive Gauss-Legendre. Expect ~5 %
agreement with reality; ground copper nearby, the phone and the chip's pads all
shift it, so measure the real board (NanoVNA + pickup loop) and tune with C3.
"""

import argparse
import itertools
import math
import os
import sys
import uuid

F_CARRIER = 13.56e6
RHO_CU = 1.72e-5  # ohm*mm
MU0_4PI_PER_MM = 1e-10  # mu0/4pi in H/mm


# --------------------------------------------------------------------------- geometry

def arc(cx, cy, r, a0, a1, tol):
    if r <= 1e-9:
        return [(cx, cy)]
    step = 2 * math.acos(max(-1.0, 1 - tol / r)) if tol < r else math.pi / 2
    n = max(1, math.ceil(abs(a1 - a0) / step))
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n),
             cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def dedupe(pts, eps=1e-6):
    out = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > eps:
            out.append(p)
    return out


def ngon_sides(shape, size, tol):
    if shape == "hex":
        return 6
    if shape == "oct":
        return 8
    r = size / 2
    return max(32, math.ceil(math.pi / math.acos(1 - tol / r)))


def turn_polygon(g, e, tol):
    """Centreline of one turn inset by e from the outer copper edge.

    [0] is the midpoint of the left side; the path then runs up (-y), clockwise on
    screen, and the last vertex lies on the left side below the midpoint.
    """
    if g["shape"] == "rect":
        a, b = g["W"] / 2 - e, g["H"] / 2 - e
        rr = max(g["r"] - e, 0.0)
        hp = math.pi / 2
        pts = [(-a, 0.0)]
        pts += arc(-a + rr, -b + rr, rr, math.pi, 3 * hp, tol)
        pts += arc(a - rr, -b + rr, rr, 3 * hp, 4 * hp, tol)
        pts += arc(a - rr, b - rr, rr, 0, hp, tol)
        pts += arc(-a + rr, b - rr, rr, hp, math.pi, tol)
        if rr <= 1e-9:  # sharp corners: arc() returned the corner only
            pts = [(-a, 0.0), (-a, -b), (a, -b), (a, b), (-a, b)]
        return dedupe(pts)
    n = ngon_sides(g["shape"], g["D"], tol)
    ap = g["D"] / 2 - e
    rad = ap / math.cos(math.pi / n)
    pts = [(-ap, 0.0)]
    for k in range(n):
        ang = math.pi + math.pi / n + k * 2 * math.pi / n
        pts.append((rad * math.cos(ang), rad * math.sin(ang)))
    return dedupe(pts)


def walk(poly, dist):
    acc = 0.0
    for k in range(len(poly) - 1):
        (x0, y0), (x1, y1) = poly[k], poly[k + 1]
        seg = math.hypot(x1 - x0, y1 - y0)
        if acc + seg > dist:
            t = (dist - acc) / seg
            return (x0 + t * (x1 - x0), y0 + t * (y1 - y0)), k + 1
        acc += seg
    raise ValueError("start offset longer than the first turn")


def cut_at_jog(poly, jog):
    """Drop the end of a turn below y = jog so the step to the next turn is a short diagonal."""
    closed = poly + [poly[0]]
    for k in range(len(poly) - 1, -1, -1):
        (x0, y0), (x1, y1) = closed[k], closed[k + 1]
        if y0 >= jog > y1:
            t = (y0 - jog) / (y0 - y1)
            return poly[:k + 1] + [(x0 + t * (x1 - x0), jog)]
    raise ValueError("jog longer than the turn")


def poly_area(pts):
    return abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1]
                   for i in range(len(pts)))) / 2


def build(g, tol):
    """Return the coil geometry: F.Cu path, pad positions, assumed bridge."""
    n, w, s = g["n"], g["w"], g["s"]
    pitch = w + s
    turns = [turn_polygon(g, w / 2 + i * pitch, tol) for i in range(n + 1)]
    # turn i -> i+1 step: 4 pitches tall keeps the diagonal gap at 97 % of nominal
    jog = 4 * pitch
    start, idx = walk(turns[0], g["start"])
    path = [start] + cut_at_jog(turns[0], jog)[idx:]
    for i in range(1, n):
        path += cut_at_jog(turns[i], jog)
    inner = turns[n][0]
    stub = max(g["via_d"] / 2 - w / 2 + 0.1, 0.0)
    end = (inner[0] + stub, 0.0)
    path += [inner, end]
    x_out = turns[0][0][0] - w / 2 - s - g["via_d"] / 2
    return {
        "path": dedupe(path),
        "pad1": start,
        "pad2": end,
        "bridge": [end, (x_out, 0.0)],
        "turns": turns[:n],
        "inner_e": w / 2 + (n - 1) * pitch + w / 2,
    }


def outline(g, offset, tol):
    """Closed polygon at `offset` outside the outer copper edge."""
    return turn_polygon(g, -offset, tol)


# ----------------------------------------------------------------- inductance solver

def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def norm(a): return math.sqrt(dot(a, a))
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def seg_dist(p0, p1, q0, q1):
    """Minimum distance between 3D segments (Ericson, Real-Time Collision Detection)."""
    d1, d2, r = sub(p1, p0), sub(q1, q0), sub(p0, q0)
    a, e, f = dot(d1, d1), dot(d2, d2), dot(d2, r)
    c, b = dot(d1, r), dot(d1, d2)
    den = a * e - b * b
    s = min(max((b * f - c * e) / den, 0.0), 1.0) if den > 1e-12 else 0.0
    t = (b * s + f) / e
    if t < 0:
        t, s = 0.0, min(max(-c / a, 0.0), 1.0)
    elif t > 1:
        t, s = 1.0, min(max((b - c) / a, 0.0), 1.0)
    cp = (p0[0] + d1[0] * s, p0[1] + d1[1] * s, p0[2] + d1[2] * s)
    cq = (q0[0] + d2[0] * t, q0[1] + d2[1] * t, q0[2] + d2[2] * t)
    return norm(sub(cp, cq))


GAUSS = {}
for _n in (2, 4, 6):
    # Gauss-Legendre nodes/weights on [0, 1] via Newton on Legendre polynomials
    nodes = []
    for i in range(1, _n + 1):
        x = math.cos(math.pi * (i - 0.25) / (_n + 0.5))
        for _ in range(50):
            p0, p1 = 1.0, x
            for k in range(2, _n + 1):
                p0, p1 = p1, ((2 * k - 1) * x * p1 - (k - 1) * p0) / k
            dp = _n * (x * p1 - p0) / (x * x - 1)
            x -= p1 / dp
        nodes.append(((x + 1) / 2, 1 / ((1 - x * x) * dp * dp)))
    GAUSS[_n] = nodes


def quad(p0, p1, q0, q1, g2, depth=0):
    """Integral of ds dt / sqrt(r^2 + g^2) over two segments (unsigned)."""
    la, lb = norm(sub(p1, p0)), norm(sub(q1, q0))
    d = seg_dist(p0, p1, q0, q1)
    big = max(la, lb)
    if d > 0.75 * big or depth > 30:
        order = 2 if d > 4 * big else 4 if d > 1.5 * big else 6
        tot = 0.0
        for u, wu in GAUSS[order]:
            pu = (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u, p0[2] + (p1[2] - p0[2]) * u)
            for v, wv in GAUSS[order]:
                dx = pu[0] - q0[0] - (q1[0] - q0[0]) * v
                dy = pu[1] - q0[1] - (q1[1] - q0[1]) * v
                dz = pu[2] - q0[2] - (q1[2] - q0[2]) * v
                tot += wu * wv / math.sqrt(dx * dx + dy * dy + dz * dz + g2)
        return tot * la * lb
    if la >= lb:
        m = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, (p0[2] + p1[2]) / 2)
        return quad(p0, m, q0, q1, g2, depth + 1) + quad(m, p1, q0, q1, g2, depth + 1)
    m = ((q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2, (q0[2] + q1[2]) / 2)
    return quad(p0, p1, q0, m, g2, depth + 1) + quad(p0, p1, m, q1, g2, depth + 1)


def pair(A, B, gmd):
    p0, p1 = A
    q0, q1 = B
    ua, ub = sub(p1, p0), sub(q1, q0)
    la, lb = norm(ua), norm(ub)
    ua = (ua[0] / la, ua[1] / la, ua[2] / la)
    ub = (ub[0] / lb, ub[1] / lb, ub[2] / lb)
    c = dot(ua, ub)
    if abs(c) < 1e-12:
        return 0.0
    if norm(cross(ua, ub)) < 1e-9:
        # parallel / collinear / self: closed form with GMD regularisation
        tb0, tb1 = dot(sub(q0, p0), ua), dot(sub(q1, p0), ua)
        lo, hi = min(tb0, tb1), max(tb0, tb1)
        perp = sub(sub(q0, p0), (ua[0] * tb0, ua[1] * tb0, ua[2] * tb0))
        de = math.sqrt(dot(perp, perp) + gmd * gmd)

        def G(x):
            return x * math.asinh(x / de) - math.sqrt(x * x + de * de)
        return math.copysign(1, c) * (G(la - lo) - G(la - hi) - G(-lo) + G(-hi))
    for v, pa, qb in ((p0, p1, q1), (p0, p1, q0), (p1, p0, q1), (p1, p0, q0)):
        other_b = q0 if qb is q1 else q1
        if norm(sub(v, other_b)) < 1e-9:
            # segments meet at vertex v (Grover): closed form
            P, Q = sub(pa, v), sub(qb, v)
            l, m, R = norm(P), norm(Q), norm(sub(P, Q))
            filament = 2 * (l * math.atanh(m / (l + R)) + m * math.atanh(l / (m + R)))
            # finite track width near the vertex: apply the collinear GMD correction
            # (matters for short arc segments, where the bend is small)
            def G(x):
                return x * math.asinh(x / gmd) - math.sqrt(x * x + gmd * gmd)
            def U(x):
                return x * math.log(x) if x > 0 else 0.0
            corr = (G(l + m) - G(l) - G(m) + G(0)) - (U(l + m) - U(l) - U(m))
            return c * (filament + corr)
    return c * quad(p0, p1, q0, q1, gmd * gmd)


def inductance(segs, gmd):
    tot = 0.0
    for i, A in enumerate(segs):
        tot += pair(A, A, gmd)
        for B in segs[i + 1:]:
            tot += 2 * pair(A, B, gmd)
    return tot * MU0_4PI_PER_MM


def to_segments(pts, z):
    return [((a[0], a[1], z), (b[0], b[1], z)) for a, b in zip(pts, pts[1:])]


def coil_segments(geo, board):
    segs = to_segments(geo["path"], 0.0)
    (xe, ye), (xo, yo) = geo["bridge"]
    segs.append(((xe, ye, 0.0), (xe, ye, -board)))
    segs += to_segments(geo["bridge"], -board)
    segs.append(((xo, yo, -board), (xo, yo, 0.0)))
    return segs


# ------------------------------------------------------------- closed-form estimate

def wheeler(g):
    """Mohan et al. 1999 modified Wheeler / current-sheet, regular shapes only."""
    n, w, s = g["n"], g["w"], g["s"]
    if g["shape"] == "rect":
        if abs(g["W"] - g["H"]) > 1e-9 or g["r"] > 0:
            return None
        dout, k = g["W"], (2.34, 2.75)
    else:
        dout = g["D"]
        k = {"hex": (2.33, 3.82), "oct": (2.25, 3.55)}.get(g["shape"])
    din = dout - 2 * n * w - 2 * (n - 1) * s
    davg, rho = (dout + din) / 2 * 1e-3, (dout - din) / (dout + din)
    mu0 = 4e-7 * math.pi
    if k is None:  # circle, current-sheet expression
        return mu0 * n * n * davg / 2 * (math.log(2.46 / rho) + 0.20 * rho * rho)
    return k[0] * mu0 * n * n * davg / (1 + k[1] * rho)


# ------------------------------------------------------------------- footprint writer

def fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def uid():
    return f'(uuid "{uuid.uuid4()}")'


def name_of(g):
    if g["shape"] == "rect":
        dims = f"{fmt(g['W'])}x{fmt(g['H'])}mm" + (f"_R{fmt(g['r'])}" if g["r"] else "")
    else:
        dims = f"{fmt(g['D'])}mm"
    return f"NFC_Coil_{g['shape'].capitalize()}_{dims}_{g['n']}T_W{fmt(g['w'])}_S{fmt(g['s'])}"


def footprint(g, geo, res, tol):
    w = g["w"]
    out = []
    add = out.append
    descr = (f"NFC spiral coil, {g['n']} turns, track {fmt(w)} / gap {fmt(g['s'])} mm. "
             f"Estimated L = {res['L'] * 1e6:.2f} uH, f0 = {res['f0'] / 1e6:.2f} MHz with "
             f"{fmt(g['cchip'] + g['cpar'])} pF. Pad 1 = outer end (to LA); pad 2 = inner via "
             f"(B.Cu bridge along y=0, then via, to LB). Generated by tools/nfc_coil.py.")
    top = min(y for _, y in outline(g, 0, tol))
    add(f'(footprint "{name_of(g)}"')
    add('\t(version 20260206)\n\t(generator "nfc_coil.py")\n\t(layer "F.Cu")')
    add(f'\t(descr "{descr}")\n\t(tags "NFC antenna coil spiral net tie")')
    for prop, val, layer, y, hide in (("Reference", "L**", "F.SilkS", top - 1.5, "yes"),
                                       ("Value", name_of(g), "F.Fab", top - 3, "no")):
        add(f'\t(property "{prop}" "{val}" (at 0 {fmt(y)} 0) (layer "{layer}") (hide {hide}) {uid()}'
            f' (effects (font (size 1 1) (thickness 0.15))))')
    add("\t(attr exclude_from_pos_files exclude_from_bom)")
    add('\t(net_tie_pad_groups "1, 2")\n\t(duplicate_pad_numbers_are_jumpers no)')

    def line(a, b, width, layer, dash=False):
        style = "dash" if dash else "solid"
        add(f'\t(fp_line (start {fmt(a[0])} {fmt(a[1])}) (end {fmt(b[0])} {fmt(b[1])})'
            f' (stroke (width {fmt(width)}) (type {style})) (layer "{layer}") {uid()})')

    def poly(pts, width, layer):
        xy = " ".join(f"(xy {fmt(x)} {fmt(y)})" for x, y in pts)
        add(f'\t(fp_poly (pts {xy}) (stroke (width {fmt(width)}) (type solid)) (fill no)'
            f' (layer "{layer}") {uid()})')

    for a, b in zip(geo["path"], geo["path"][1:]):
        line(a, b, w, "F.Cu")
    poly(outline(g, 0, tol), 0.1, "F.Fab")
    poly(outline(g, 0.5, tol), 0.05, "F.CrtYd")
    # assumed bridge + outer via, for reference only
    (xe, _), (xo, _) = geo["bridge"]
    line((xe, 0), (xo, 0), 0.1, "Dwgs.User", dash=True)
    r = g["via_d"] / 2
    add(f'\t(fp_circle (center {fmt(xo)} 0) (end {fmt(xo + r)} 0) (stroke (width 0.1) (type solid))'
        f' (fill no) (layer "Dwgs.User") {uid()})')
    add(f'\t(fp_text user "B.Cu bridge, via here, to LB" (at {fmt(xo - 1)} 1.2 0) (layer "Dwgs.User") {uid()}'
        f' (effects (font (size 0.6 0.6) (thickness 0.1)) (justify right)))')
    ko = " ".join(f"(xy {fmt(x)} {fmt(y)})" for x, y in outline(g, g["keepout"], tol))
    add(f'\t(zone (layers "F.Cu" "B.Cu") {uid()} (name "NFC coil: no pour") (hatch full 0.5)'
        ' (connect_pads (clearance 0)) (min_thickness 0.25)'
        ' (keepout (tracks allowed) (vias allowed) (pads allowed) (copperpour not_allowed) (footprints allowed))'
        ' (placement (enabled no) (sheetname ""))'
        ' (fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))'
        f' (polygon (pts {ko})))')
    p1, p2 = geo["pad1"], geo["pad2"]
    pd = max(g["pad_d"], w)
    p1 = (p1[0] - (pd - w) / 2, p1[1])  # grow outward only, keep the gap to turn 2
    add(f'\t(pad "1" smd circle (at {fmt(p1[0])} {fmt(p1[1])}) (size {fmt(pd)} {fmt(pd)})'
        f' (layers "F.Cu") {uid()})')
    add(f'\t(pad "2" thru_hole circle (at {fmt(p2[0])} {fmt(p2[1])}) (size {fmt(g["via_d"])} {fmt(g["via_d"])})'
        f' (drill {fmt(g["via_drill"])}) (layers "*.Cu") (remove_unused_layers no) {uid()})')
    add("\t(embedded_fonts no)\n)")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- driver

def evaluate(g):
    tol_draw, tol_solve = 0.01, 0.05
    geo_s = build(g, tol_solve)
    if geo_s["inner_e"] * 2 + 2 * (g["via_d"] + g["s"]) >= (g["W"] if g["shape"] == "rect" else g["D"]) \
            or (g["shape"] == "rect" and geo_s["inner_e"] * 2 + 2 * (g["via_d"] + g["s"]) >= g["H"]):
        return None
    L = inductance(coil_segments(geo_s, g["board"]), 0.2235 * (g["w"] + g["t"]))
    c_tot = (g["cchip"] + g["cpar"]) * 1e-12
    f0 = 1 / (2 * math.pi * math.sqrt(L * c_tot))
    c_tune = 1 / ((2 * math.pi * F_CARRIER) ** 2 * L) - c_tot
    length = sum(norm(sub(b, a)) for a, b in coil_segments(geo_s, g["board"]))
    if g["shape"] == "rect":
        inner = f"{fmt(g['W'] - 2 * geo_s['inner_e'])}x{fmt(g['H'] - 2 * geo_s['inner_e'])}"
    else:
        inner = fmt(g["D"] - 2 * geo_s["inner_e"])
    return {
        "L": L, "Lw": wheeler(g), "f0": f0, "c_tune": c_tune * 1e12,
        "area": sum(poly_area(t) for t in geo_s["turns"]) / 100,
        "len": length, "rdc": RHO_CU * length / (g["w"] * g["t"]), "inner": inner,
        "geo": build(g, tol_draw), "tol": tol_draw,
    }


def verdict(r):
    f = r["f0"] / 1e6
    if f < F_CARRIER / 1e6:
        return "L too high (cap can't fix)"
    if f <= 15.0:
        return "good" if f >= 13.8 else "ok, little tuning margin"
    return f"high: needs ~{r['c_tune']:.0f} pF in C3"


def values(text, cast=float):
    out = []
    for part in str(text).split(","):
        if ":" in part:
            a, b, *st = part.split(":")
            a, b, st = float(a), float(b), float(st[0]) if st else 1.0
            k = 0
            while a + k * st <= b + 1e-9:
                out.append(cast(round(a + k * st, 6)))
                k += 1
        else:
            out.append(cast(float(part)))
    return out


def selftest():
    print("1) single circular loop R=20 mm, w=0.3 mm, 35 um copper")
    gmd = 0.2235 * 0.335
    pts = [(20 * math.cos(2 * math.pi * k / 720), 20 * math.sin(2 * math.pi * k / 720)) for k in range(721)]
    L = inductance(to_segments(pts, 0.0), gmd)
    ref = 4e-7 * math.pi * 0.020 * (math.log(8 * 20 / gmd) - 2)
    print(f"   solver {L * 1e9:.1f} nH, textbook mu0*R*(ln(8R/GMD)-2) = {ref * 1e9:.1f} nH")
    print("2) square loop 30 mm side")
    sq = [(0, 0), (30, 0), (30, 30), (0, 30), (0, 0)]
    L = inductance(to_segments(sq, 0.0), gmd)
    a = 30
    ref = 2e-7 * 4 * a * 1e-3 * (math.log(a / gmd) - 0.774)  # Grover: (2mu0 a/pi)(ln(a/GMD) - 0.774)
    print(f"   solver {L * 1e9:.1f} nH, Grover {ref * 1e9:.1f} nH")
    print("3) Koda hex coil (32.8 mm across flats, 7 T, 0.3/0.3), schematic value 2.78 uH")
    main(["hex", "--size", "32.8", "--turns", "7"])


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shape", choices=["rect", "hex", "oct", "circle", "selftest"])
    ap.add_argument("-W", "--width", default=None, help="rect: outer copper width, mm")
    ap.add_argument("-H", "--height", default=None, help="rect: outer copper height, mm")
    ap.add_argument("-r", "--radius", default="0", help="rect: outer corner radius, mm")
    ap.add_argument("-D", "--size", default=None, help="hex/oct: outer across flats; circle: outer diameter, mm")
    ap.add_argument("-n", "--turns", default="5")
    ap.add_argument("--track", default="0.3", help="track width, mm")
    ap.add_argument("--gap", default="0.3", help="gap between turns, mm")
    ap.add_argument("--copper", type=float, default=0.035, help="copper thickness, mm (1 oz)")
    ap.add_argument("--board", type=float, default=0.6, help="board thickness, mm")
    ap.add_argument("--cchip", type=float, default=50.0, help="NT3H2111 input capacitance, pF")
    ap.add_argument("--cpar", type=float, default=3.0, help="coil self-capacitance + pads, pF (guess)")
    ap.add_argument("--start", type=float, default=1.2, help="pad 1 offset above the left midpoint, mm")
    ap.add_argument("--pad", type=float, default=0.6, help="pad 1 diameter, mm")
    ap.add_argument("--via", type=float, default=0.6, help="pad 2 (via) diameter, mm")
    ap.add_argument("--drill", type=float, default=0.3, help="pad 2 drill, mm")
    ap.add_argument("--keepout", type=float, default=3.0, help="no-pour margin around the coil, mm")
    ap.add_argument("--write", action="store_true", help="write footprints to --lib")
    ap.add_argument("--lib", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "..", "lib", "nfc-coils.pretty"))
    a = ap.parse_args(argv)
    if a.shape == "selftest":
        return selftest()

    if a.shape == "rect":
        if a.width is None and a.size is None:
            ap.error("rect needs --width/--height (or --size for a square)")
        dims = [dict(W=W, H=H, r=r)
                for W in values(a.width or a.size) for H in values(a.height or a.width or a.size)
                for r in values(a.radius)]
    else:
        if a.size is None:
            ap.error(f"{a.shape} needs --size")
        dims = [dict(D=D) for D in values(a.size)]

    rows = []
    for d, n, w, s in itertools.product(dims, values(a.turns, int), values(a.track), values(a.gap)):
        g = dict(shape=a.shape, n=n, w=w, s=s, t=a.copper, board=a.board, cchip=a.cchip,
                 cpar=a.cpar, start=a.start, pad_d=a.pad, via_d=a.via, via_drill=a.drill,
                 keepout=a.keepout, **d)
        res = evaluate(g)
        rows.append((g, res))

    hdr = f"{'coil':<44} {'L uH':>6} {'Wheel':>6} {'f0 MHz':>7} {'C3 pF':>6} {'sumA cm2':>8} {'inner mm':>10} {'Rdc':>5}  verdict"
    print(hdr)
    print("-" * len(hdr))
    for g, r in rows:
        nm = name_of(g).replace("NFC_Coil_", "")
        if r is None:
            print(f"{nm:<44} too many turns for this outline")
            continue
        lw = f"{r['Lw'] * 1e6:6.2f}" if r["Lw"] else f"{'-':>6}"
        ct = f"{r['c_tune']:6.1f}" if r["c_tune"] >= 0 else f"{'-':>6}"
        print(f"{nm:<44} {r['L'] * 1e6:6.2f} {lw} {r['f0'] / 1e6:7.2f} {ct} {r['area']:8.1f}"
              f" {r['inner']:>10} {r['rdc']:5.2f}  {verdict(r)}")
    print(f"\nf0 uses Cchip {fmt(a.cchip)} pF + Cpar {fmt(a.cpar)} pF. C3 pF = parallel cap that brings f0 to 13.56 MHz."
          "\nAim for f0 ~ 14-14.5 MHz untuned: C3 can only pull it down. sumA = total turn area (bigger couples better).")

    if a.write:
        os.makedirs(a.lib, exist_ok=True)
        for g, r in rows:
            if r is None:
                continue
            path = os.path.join(a.lib, name_of(g) + ".kicad_mod")
            with open(path, "w") as f:
                f.write(footprint(g, r["geo"], r, r["tol"]))
            print("wrote", os.path.relpath(path))


if __name__ == "__main__":
    main(sys.argv[1:])
