# -*- coding: utf-8 -*-
"""
generators.pedestal — Pedestal de hormigón armado.

Sección transversal con armadura longitudinal, estribo cerrado con ganchos
a 135°, tirantes, acotado y cuadro de despiece. Elevación con arranques
(rampas de anclaje en zapata) y estribos en vista.
"""

import math

from .panels import SpecPanel
from .data import DIAM_BARRAS, ESCALAS
from core import ir
from core.ir import Line, Poly, Circle, Text
from core.geom import (hatch_poly, poly_bar, stirrup_pts, level_symbol,
                       break_line, line_x, line_y)
from core.dims import DimBuilder
from core.tables import cuadro_despiece, fila_barra, peso_barra


# ----------------------------------------------------------------- panel --
class PedestalPanel(SpecPanel):
    SPEC = [
        ("b", "Ancho sección b (cm)", "float", 20, 200, 30, 1, 5, ""),
        ("h", "Alto sección h (cm)", "float", 20, 200, 30, 1, 5, ""),
        ("H", "Altura pedestal (cm)", "float", 30, 600, 250, 1, 10, ""),
        ("r", "Recubrimiento (cm)", "float", 2, 10, 4, 1, 0.5, ""),
        ("n_barras", "Nº barras long.", "combo", ["4", "6", "8", "10", "12"], "8"),
        ("d_barra", "Ø barras (mm)", "combo", DIAM_BARRAS, 18),
        ("d_estribo", "Ø estribo (mm)", "combo", [8, 10, 12], 8),
        ("e_estribo", "Espaciamiento e (cm)", "float", 5, 30, 15, 1, 1, ""),
        ("elevacion", "Vista de elevación", "chk", True),
        ("ancho_zap", "Ancho zapata (cm)", "float", 40, 500, 130, 1, 10, ""),
        ("alto_zap", "Alto zapata (cm)", "float", 20, 120, 30, 1, 5, ""),
        ("traslape", "Traslape arranque (cm)", "float", 20, 200, 45, 1, 5, ""),
        ("largo_barra", "Largo barra B1 (m)", "float", 0.5, 12, 3.2, 2, 0.1, " m"),
        ("escala", "Escala de acotado", "combo", ESCALAS, "1:25"),
    ]


# -------------------------------------------------------------- generador --
def build_pedestal(p: dict) -> ir.Drawing:
    d = ir.Drawing()
    f = p.get("_escala", 2.5)
    th = 3.0 * f
    B, H = p["b"] * 10.0, p["h"] * 10.0        # sección en mm
    R = p["r"] * 10.0                          # recubrimiento en mm
    db_d = float(p["d_barra"])
    ds = float(p["d_estribo"])
    n = int(p["n_barras"])

    o = R + ds + db_d / 2.0                    # eje de barra desde la cara
    x0 = B / 2 - o
    y0 = H / 2 - o

    # posiciones de barras: esquinas + intermedias en caras horizontales
    xs = [-x0, x0]
    m = max(0, (n - 4) // 2)
    for k in range(1, m + 1):
        xs.append(-x0 + 2 * x0 * k / (m + 1))
    xs = sorted(set(round(v, 3) for v in xs))

    # ------------------------- SECCIÓN -------------------------
    sec = ir.rect(-B / 2, -H / 2, B / 2, H / 2)
    d.ents.append(sec)
    d.ents.extend(hatch_poly(sec.pts, 9 * f))
    # estribo
    st_pts = stirrup_pts(B - 2 * R, H - 2 * R, ds, 2.5 * ds)
    bar, _ = poly_bar([(px - B / 2 + R, py - H / 2 + R) for px, py in st_pts],
                      ds, 2.5 * ds)
    d.ents.extend(bar)
    # tirantes (un tirante por barra intermedia)
    ties = []
    if m >= 1:
        hy = H / 2 - R
        tk = min(25.0, o)
        for xt in [x for x in xs if abs(x) < x0 - 1]:
            tpts = [(xt - tk, hy), (xt, hy), (xt, -hy), (xt - tk, -hy)]
            tbar, _ = poly_bar(tpts, ds, 2 * ds)
            d.ents.extend(tbar)
            ties.append(xt)
    # barras longitudinales
    for x in xs:
        for y in (-y0, y0):
            if abs(y) < H / 2 and (abs(x) > x0 - 1 or abs(y) > y0 - 1):
                d.ents.append(Circle((x, y), db_d / 2, ir.L_ACERO, filled=True))
    # ejes
    d.ents.append(line_y(0, -B / 2 - 40 * f, B / 2 + 40 * f))
    d.ents.append(line_x(0, -H / 2 - 40 * f, H / 2 + 40 * f))

    # acotado sección
    dbb = DimBuilder(d.ents, th)
    xs_chain = sorted(set([-x0] + [x for x in xs if abs(x) < x0 - 1] + [x0]))
    dbb.h_chain(xs_chain, -y0, -H / 2 - 40 * f, ext_from=-H / 2)
    dbb.h_total(-B / 2, B / 2, -H / 2, -H / 2 - 75 * f, ext_from=-H / 2)
    dbb.v_total(-H / 2, H / 2, B / 2, B / 2 + 40 * f, ext_from=B / 2)
    dbb.h_total(-B / 2, -B / 2 + R, -H / 2 + R, -H / 2 - 22 * f,
                texts=[f"r = {ir.fmt_cm(R)}"], ext_from=-H / 2 + R)

    # etiquetas
    d.ents.append(ir.Leader((x0, y0), (x0 + 45 * f, y0 + 45 * f),
                            f"4Ø{db_d:g}", th, shelf=16 * f, side=1))
    if m:
        xm = [x for x in xs if abs(x) < x0 - 1][0]
        d.ents.append(ir.Leader((xm, y0), (xm - 10 * f, y0 + 55 * f),
                                f"{2 * m}Ø{db_d:g}", th, shelf=16 * f,
                                side=-1))
    d.ents.append(ir.Leader((-B / 2 + R + 4, H / 2 - R - 4),
                            (-B / 2 - 40 * f, H / 2 + 42 * f),
                            f"Ø{ds:g} c/{ir.fmt_cm(p['e_estribo'] * 10)} cm",
                            th, shelf=20 * f, side=-1))

    # ------------------------- ELEVACIÓN (a la derecha) -------------------
    Wf = p["ancho_zap"] * 10.0
    ex = B / 2 + 150.0 * f + Wf / 2
    y_min = -H / 2 - 110 * f
    if p["elevacion"]:
        y_min = min(y_min, _elevacion_ped(d, dbb, p, ex, B, H, R, db_d, ds,
                                          xs, f, th))

    # ---------------------- CUADRO DESPIECE ----------------------
    filas, total = _despiece(p, B, H, R, db_d, ds, m, f)
    y_tab = y_min - 30 * f
    ancho_tab = sum(w for w in [20, 34, 16, 14, 24, 24, 26]) * f
    tb = cuadro_despiece((-B / 2 - 90 * f, y_tab), f, filas,
                         total_kg=total)
    d.ents.append(tb)
    y_min = y_tab - (len(filas) + 1.6) * tb.row_h - 14 * f

    # --------------------------- TÍTULO ---------------------------
    notas = [
        f"CONCRETO f'c = 21 MPa  |  ACERO fy = 420 MPa",
        f"RECUBRIMIENTO r = {ir.fmt_cm(R)} cm  |  "
        f"ESTRIBOS Ø{ds:g} c/{ir.fmt_cm(p['e_estribo'] * 10)} cm",
    ]
    for i, s in enumerate(notas):
        d.ents.append(Text((-B / 2 - 90 * f, y_min - i * 8 * f), s,
                           2.5 * f, 0, ir.L_TXT, "l", "m"))
    d.ents.append(Text((ex / 2.0, y_min - len(notas) * 8 * f - 14 * f),
                       f"PEDESTAL {ir.fmt_m(B)}x{ir.fmt_m(H)} m  -  "
                       f"ESC {p['escala']}", 4.5 * f, 0, ir.L_TXT, "c", "m"))
    return d


# -------------------------------------------------------------- elevación --
def _elevacion_ped(d, dbb, p, ex, B, H, R, db_d, ds, xs, f, th):
    e = d.ents
    Hm = p["H"] * 10.0
    Wf = p["ancho_zap"] * 10.0
    hf = p["alto_zap"] * 10.0
    lap = p["traslape"] * 10.0

    z_rect = ir.rect(ex - Wf / 2, -hf, ex + Wf / 2, 0)
    e.append(z_rect)
    e.extend(hatch_poly(z_rect.pts, 9 * f))
    p_rect = ir.rect(ex - B / 2, 0, ex + B / 2, Hm)
    e.append(p_rect)
    e.extend(break_line((ex - B / 2 - 6 * f, Hm), (ex + B / 2 + 6 * f, Hm),
                        5 * f))
    # arranques con gancho en zapata (alternando lado) + barras principales
    for i, xb in enumerate(xs):
        x = ex + xb
        sgn = -1 if i % 2 else 1
        hook_y = -hf + 60
        arr, _ = poly_bar([(x + sgn * 80, hook_y), (x, hook_y),
                           (x, lap)], db_d, 3 * db_d,
                          width=max(1.2, db_d * 0.14))
        e.extend(arr)
        e.append(Line((x, 0), (x, Hm - R), ir.L_ACERO,
                      width=max(1.2, db_d * 0.14)))
    # estribos en vista (máx. 10 trazos)
    e_st = p["e_estribo"] * 10.0
    niv = [50.0 + i * e_st for i in range(int((Hm - 60) / e_st) + 1)][:10]
    for y in niv:
        e.append(Line((ex - B / 2 + 3, y), (ex + B / 2 - 3, y), ir.L_ACERO))
    # ejes y nivel
    e.append(line_x(ex, -hf - 30 * f, Hm + 30 * f))
    e.extend(level_symbol((ex - Wf / 2 - 25 * f, 0), th, "N.P."))

    # acotado
    dbb.v_total(0, Hm, ex + B / 2, ex + B / 2 + 40 * f, ext_from=ex + B / 2)
    dbb.v_total(0, lap, ex - B / 2, ex - B / 2 - 40 * f,
                texts=[f"TR = {ir.fmt_m(lap)}"], ext_from=ex - B / 2)
    yb = -hf - 40 * f
    dbb.h_chain([ex - Wf / 2, ex + Wf / 2], -hf, yb, ext_from=-hf,
                texts=[f"{ir.fmt_m(Wf)}"])
    dbb.h_total(ex - B / 2, ex + B / 2, 0, -hf - 75 * f, ext_from=-hf)
    e.append(ir.Leader((ex + xs[-1], 60),
                       (ex - Wf / 2 - 45 * f, 60 + 45 * f),
                       f"ARRANQUES {len(xs)}Ø{db_d:g}", th, shelf=20 * f,
                       side=-1))
    return -hf - 120 * f


# ------------------------------------------------------------- despiece --
def _despiece(p, B, H, R, db_d, ds, m, f):
    filas = []
    total = 0.0
    Hm = p["H"] * 10.0

    # B1 barras principales (rectas)
    L1 = p["largo_barra"] * 1000.0
    celdas, sk, dev = fila_barra("B1", "recta", [(0, 0), (0, 1)], db_d,
                                 2 * db_d, int(p["n_barras"]))
    celdas[4] = f"{p['largo_barra']:.2f}"
    pu = peso_barra(db_d)
    celdas[6] = f"{pu * int(p['n_barras']) * p['largo_barra']:.1f}"
    total += pu * int(p["n_barras"]) * p["largo_barra"]
    filas.append((celdas, sk))

    # B2 arranques (L con gancho en zapata)
    hf = p["alto_zap"] * 10.0
    lap = p["traslape"] * 10.0
    celdas, sk, dev = fila_barra("B2", "L", [(0, 0), (90, 0),
                                             (90, hf - 60 + lap)],
                                 db_d, 3 * db_d, int(p["n_barras"]))
    total += peso_barra(db_d) * int(p["n_barras"]) * dev / 1000.0
    filas.append((celdas, sk))

    # B3 estribos
    st_pts = stirrup_pts(B - 2 * R, H - 2 * R, ds, 2.5 * ds)
    q3 = int(math.ceil(Hm / (p["e_estribo"] * 10.0)) + 1)
    celdas, sk, dev = fila_barra("B3", "estribo", st_pts, ds, 2.5 * ds, q3)
    total += peso_barra(ds) * q3 * dev / 1000.0
    filas.append((celdas, sk))

    # B4 tirantes
    if m >= 1:
        hy = H / 2 - R
        tk = min(25.0, R + ds)
        tpts = [(-tk, hy), (0, hy), (0, -hy), (-tk, -hy)]
        celdas, sk, dev = fila_barra("B4", "tirante", tpts, ds, 2 * ds, m * q3)
        total += peso_barra(ds) * m * q3 * dev / 1000.0
        filas.append((celdas, sk))
    return filas, total
