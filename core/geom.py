# -*- coding: utf-8 -*-
"""
core.geom — Utilidades geométricas compartidas.

- Hachurado de concreto por líneas a 45°.
- Barras dobladas (poly_bar): trazo de línea central con radios de doblez
  y cálculo de longitud de desarrollo (para el cuadro de despiece).
- Flechas, símbolos de nivel, líneas de rotura, símbolos de soldadura.
"""

import math
from . import ir
from .ir import PT, Line, Arc, Poly, Filled, Text, Circle

TOL = 1e-9


# ------------------------------------------------------------- primitivas ---

def pol(p: PT, ang_deg: float, dist: float) -> PT:
    a = math.radians(ang_deg)
    return (p[0] + dist * math.cos(a), p[1] + dist * math.sin(a))


def ang(p1: PT, p2: PT) -> float:
    return math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))


def dist(p1: PT, p2: PT) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def rot(p: PT, deg: float, about: PT = (0.0, 0.0)) -> PT:
    a = math.radians(deg)
    dx, dy = p[0] - about[0], p[1] - about[1]
    return (about[0] + dx * math.cos(a) - dy * math.sin(a),
            about[1] + dx * math.sin(a) + dy * math.cos(a))


def line_x(x: float, y1: float, y2: float, layer=ir.L_EJE) -> Line:
    return Line((x, y1), (x, y2), layer)


def line_y(y: float, x1: float, x2: float, layer=ir.L_EJE) -> Line:
    return Line((x1, y), (x2, y), layer)


def rect(x0: float, y0: float, x1: float, y1: float,
         layer=ir.L_CONC, closed=True) -> Poly:
    return Poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                closed=closed, layer=layer)


# ---------------------------------------------------------------- hachurado ---

def hatch_poly(pts, spacing: float, angle_deg: float = 45.0,
               layer=ir.L_HACH) -> list:
    """Hachurado por líneas paralelas recortadas contra un polígono simple.
    (Recorte por pares de intersecciones; funciona también en no convexos)."""
    out = []
    if len(pts) < 3 or spacing <= 0:
        return out
    a = math.radians(angle_deg)
    ca, sa = math.cos(-a), math.sin(-a)          # rota el polígono -angle
    rp = [(p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca) for p in pts]
    ys = [p[1] for p in rp]
    y0, y1 = min(ys), max(ys)
    n = int((y1 - y0) / spacing) + 2
    yc = y0 - (y0 % spacing if spacing else 0)
    for k in range(n):
        y = y0 + k * spacing
        xs = []
        j = len(rp) - 1
        for i in range(len(rp)):
            p1, p2 = rp[j], rp[i]
            if (p1[1] <= y < p2[1]) or (p2[1] <= y < p1[1]):
                t = (y - p1[1]) / (p2[1] - p1[1])
                xs.append(p1[0] + t * (p2[0] - p1[0]))
            j = i
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa, xb = xs[i], xs[i + 1]
            if xb - xa < TOL:
                continue
            ca2, sa2 = math.cos(a), math.sin(a)
            q1 = (xa * ca2 - y * sa2, xa * sa2 + y * ca2)
            q2 = (xb * ca2 - y * sa2, xb * sa2 + y * ca2)
            out.append(Line(q1, q2, layer))
    return out


# --------------------------------------------------------- barras dobladas ---

def poly_bar(pts, d: float, R_in: float, layer=ir.L_ACERO,
             width: float = 0.0):
    """Dibuja una barra doblada como línea central con arcos de doblez.

    pts  : vértices del recorrido (esquinas de la barra, línea central)
    d    : diámetro nominal de la barra (mm)
    R_in : radio interior de doblez (mm); radio de línea central = R_in + d/2

    Devuelve (entidades, longitud_de_desarrollo_en_mm).
    """
    # depura puntos repetidos
    clean = [pts[0]]
    for p in pts[1:]:
        if dist(p, clean[-1]) > TOL:
            clean.append(p)
    pts = clean
    if len(pts) < 2:
        return [], 0.0

    Rm = R_in + d / 2.0
    ents: list = []
    dev = 0.0
    cur = pts[0]                       # punto actual del recorrido recortado

    for i in range(1, len(pts) - 1):
        v = pts[i]
        p_prev, p_next = pts[i - 1], pts[i + 1]
        l1 = dist(p_prev, v)
        l2 = dist(v, p_next)
        if l1 < TOL or l2 < TOL:
            continue
        ux, uy = (v[0] - p_prev[0]) / l1, (v[1] - p_prev[1]) / l1
        wx, wy = (p_next[0] - v[0]) / l2, (p_next[1] - v[1]) / l2
        cr = ux * wy - uy * wx
        dt = ux * wx + uy * wy
        th = math.atan2(cr, dt)                      # ángulo con signo
        if abs(th) < math.radians(0.5):              # prácticamente recta
            continue
        th = max(-math.radians(160), min(math.radians(160), th))
        Rm_i = Rm
        T = Rm_i * math.tan(abs(th) / 2.0)
        T = min(T, 0.45 * l1, 0.45 * l2)             # nunca excede los tramos
        t_in = (v[0] - T * ux, v[1] - T * uy)
        t_out = (v[0] + T * wx, v[1] + T * wy)
        # centro: a Rm del lado interior del doblez
        if cr > 0:    # giro antihorario -> centro a la izquierda de u
            nx, ny = -uy, ux
        else:         # horario -> centro a la derecha de u
            nx, ny = uy, -ux
        center = (t_in[0] + Rm_i * nx, t_in[1] + Rm_i * ny)

        ents.append(Line(cur, t_in, layer, width))
        dev += dist(cur, t_in)
        a1 = ang(center, t_in)
        a2 = ang(center, t_out)
        ents.append(Arc(center, Rm_i, a1, a2, ccw=(cr > 0), layer=layer))
        dev += Rm_i * abs(th)
        cur = t_out

    ents.append(Line(cur, pts[-1], layer, width))
    dev += dist(cur, pts[-1])
    return ents, dev


# ------------------------------------------------------------- símbolos ---

def arrow(tip: PT, ang_deg: float, size: float, layer=ir.L_ACOT) -> Filled:
    """Cabeza de flecha rellena; `tip` es la punta, apunta hacia ang_deg."""
    b1 = pol(tip, ang_deg + 180 - 12, size)
    b2 = pol(tip, ang_deg + 180 + 12, size)
    return Filled([tip, b1, b2], layer)


def tick(p: PT, ang_deg: float, size: float, layer=ir.L_ACOT) -> Line:
    """Marca oblicua (tick) alternativa para cotas."""
    return Line(pol(p, ang_deg + 90 + 45, size / 2),
                pol(p, ang_deg + 90 - 45, size / 2), layer)


def level_symbol(p: PT, h: float, txt: str, layer=ir.L_TXT) -> list:
    """Símbolo de nivel (triángulo + texto), p = punto en el nivel."""
    s = h * 0.9
    tri = Filled([(p[0] - s, p[1] + s), (p[0] + s, p[1] + s), (p[0], p[1])],
                 layer)
    l1 = Line((p[0] - 3 * s, p[1] + s), (p[0] + 3.2 * s, p[1] + s), layer)
    t1 = Text((p[0] - 3 * s, p[1] + s + h * 0.35), txt, h, 0, layer,
              ha="l", va="b")
    return [tri, l1, t1]


def break_line(p1: PT, p2: PT, amp: float, layer=ir.L_CONC) -> list:
    """Línea de rotura (corte) con zigzag al centro."""
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    a = ang(p1, p2)
    n = pol((mx, my), a, -amp * 1.5)
    s = pol((mx, my), a, amp * 1.5)
    z1 = pol(n, a + 90, amp)
    z2 = pol(s, a + 90, -amp)
    return [Poly([p1, n, z1, s, z2, p2], closed=False, layer=layer)]


def weld_symbol(tip: PT, elbow: PT, h: float, layer=ir.L_SOLD) -> list:
    """Símbolo básico de soldadura de filete (triángulos a ambos lados)."""
    out = [Line(tip, elbow, layer)]
    sh = h * 3.5
    side = 1 if elbow[0] >= tip[0] else -1
    p2 = (elbow[0] + side * sh, elbow[1])
    out.append(Line(elbow, p2, layer))
    t = h * 0.9
    for dx in (0.9 * h, 2.2 * h):
        base_x = elbow[0] + side * dx
        out.append(Filled([(base_x, elbow[1]),
                           (base_x + side * t, elbow[1]),
                           (base_x, elbow[1] - t)], layer))
    return out


def stirrup_pts(b: float, h: float, d: float, R_in: float) -> list:
    """Recorrido (línea central) de un estribo cerrado con ganchos a 135°.
    b, h: dimensiones exteriores del estribo; origen en esquina inf-izq."""
    Lh = max(6.0 * d, 75.0)                    # largo de gancho (6d >= 75)
    Rm = R_in + d / 2.0
    T135 = Rm * math.tan(math.radians(135 / 2.0))
    T90 = Rm * math.tan(math.radians(45.0))
    e = min(0.45 * min(b, h), max(0.8 * Lh, T135 + T90 + 5.0))
    k = 0.7071
    bendA = (b - e, h)                          # gancho sobre cara superior
    bendB = (b, h - e)                          # gancho sobre cara derecha
    return [ (bendA[0] - k * Lh, bendA[1] - k * Lh), bendA,
             (0, h), (0, 0), (b, 0), bendB,
             (bendB[0] - k * Lh, bendB[1] - k * Lh) ]


def thread_zigzag(p0: PT, length: float, w: float, pitch: float,
                  layer=ir.L_ACERO) -> list:
    """Rosca esquemática de perno: zigzag a lo largo de +Y desde p0."""
    pts = [p0]
    y = p0[1]
    side = 1
    while y < p0[1] + length:
        y = min(y + pitch / 2, p0[1] + length)
        pts.append((p0[0] + side * w / 2, y))
        side = -side
    return [Poly(pts, closed=False, layer=layer, width=0.0)]
