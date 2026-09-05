# -*- coding: utf-8 -*-
"""
generators.slab — Losa de hormigón armado (sección transversal).

Armadura inferior con ganchos, repartición, armadura superior opcional,
apoyos hachurados, acotado y cuadro de despiece.
"""

from .panels import SpecPanel
from .data import DIAM_BARRAS, ESCALAS
from core import ir
from core.ir import Line, Poly, Circle, Text
from core.geom import hatch_poly, poly_bar, line_x
from core.dims import DimBuilder
from core.tables import cuadro_despiece, fila_barra, peso_barra
from core.labels import rebar_spacing


# ----------------------------------------------------------------- panel --
class SlabPanel(SpecPanel):
    SPEC = [
        ("L", "Luz libre L (cm)", "float", 100, 1200, 400, 0, 10, ""),
        ("t", "Espesor losa t (cm)", "float", 8, 40, 15, 1, 1, ""),
        ("bw", "Ancho apoyo (cm)", "float", 10, 100, 20, 1, 5, ""),
        ("hh", "Alto apoyo (cm)", "float", 20, 150, 40, 1, 5, ""),
        ("r", "Recubrimiento (cm)", "float", 1.5, 8, 3, 1, 0.5, ""),
        ("d1", "Ø inferior (mm)", "combo", DIAM_BARRAS, 12),
        ("s1", "Espac. inferior (cm)", "float", 5, 40, 20, 1, 1, ""),
        ("d2", "Ø repartición (mm)", "combo", DIAM_BARRAS, 8),
        ("s2", "Espac. repart. (cm)", "float", 5, 40, 25, 1, 1, ""),
        ("sup", "Armadura superior", "chk", True),
        ("d3", "Ø superior (mm)", "combo", DIAM_BARRAS, 10),
        ("s3", "Espac. superior (cm)", "float", 5, 40, 15, 1, 1, ""),
        ("a", "Largo superior a (cm)", "float", 20, 300, 60, 0, 5, ""),
        ("gv", "Gancho extremos (cm)", "float", 5, 40, 15, 1, 1, ""),
        ("escala", "Escala de acotado", "combo", ESCALAS, "1:50"),
    ]


# -------------------------------------------------------------- generador --
def build_slab(p: dict) -> ir.Drawing:
    d = ir.Drawing()
    f = p.get("_escala", 5.0)
    th = 3.0 * f
    db = DimBuilder(d.ents, th)

    L = p["L"] * 10.0                # mm
    t = p["t"] * 10.0
    bw = p["bw"] * 10.0
    hh = p["hh"] * 10.0
    R = p["r"] * 10.0
    d1, d2, d3 = float(p["d1"]), float(p["d2"]), float(p["d3"])
    s1, s2 = p["s1"] * 10.0, p["s2"] * 10.0
    gv = p["gv"] * 10.0
    sup = p["sup"]
    a = p["a"] * 10.0

    # ------------------------- geometría -------------------------
    slab = ir.rect(-bw, 0, L + bw, t)
    d.ents.append(slab)
    d.ents.extend(hatch_poly(slab.pts, 12 * f))
    for x0, x1 in ((-bw, 0), (L, L + bw)):
        s = ir.rect(x0, -hh, x1, 0)
        d.ents.append(s)
        d.ents.extend(hatch_poly(s.pts, 9 * f))
    # ejes de apoyos
    for xc in (-bw / 2, L + bw / 2):
        d.ents.append(line_x(xc, -hh - 25 * f, t + 30 * f))
    d.ents.append(Text((L / 2, t + 105 * f), "SECCIÓN DE LOSA",
                       3.5 * f, layer=ir.L_TXT, ha="c", va="m"))

    # armadura inferior con ganchos
    yr = R + d1 / 2
    b1_pts = [(-bw + 50, yr - gv), (-bw + 50, yr),
              (L + bw - 50, yr), (L + bw - 50, yr - gv)]
    b1, dev1 = poly_bar(b1_pts, d1, 2.5 * d1, width=max(1.2, d1 * 0.12))
    d.ents.extend(b1)

    # repartición (puntos en sección)
    yd = yr + d1 / 2 + d2 / 2
    n2 = int((L + 2 * bw - 2 * R) / s2) + 1
    for i in range(n2):
        x = -bw + R + i * s2
        d.ents.append(Circle((min(x, L + bw - R), yd), d2 / 2,
                             ir.L_ACERO, filled=True))

    # armadura superior (gancho hacia afuera, desarrollo hacia la luz)
    dev3 = 0.0
    if sup:
        yt = t - R - d3 / 2
        for xc in (-bw / 2, L + bw / 2):
            sg = -1 if xc < L / 2 else 1
            pts = [(xc + sg * 60, yt - gv), (xc + sg * 60, yt),
                   (xc - sg * a, yt)]
            b3, dev3_i = poly_bar(pts, d3, 2.5 * d3,
                                  width=max(1.2, d3 * 0.12))
            dev3 = dev3_i
            d.ents.extend(b3)

    # ------------------------- acotado -------------------------
    y1 = -hh - 45 * f
    db.h_chain([-bw, 0, L, L + bw], -hh, y1, ext_from=-hh)
    db.h_total(-bw, L + bw, -hh, y1 - 35 * f, ext_from=-hh)
    x1 = L + bw + 45 * f
    db.v_chain([-hh, 0, t], L + bw, x1, ext_from=L + bw)
    # espaciamientos como cotas pequeñas sobre la losa
    if sup:
        db.h_total(-bw / 2, -bw / 2 + a, t, t + 45 * f,
                   texts=[f"a = {ir.fmt_m(a)}"], ext_from=t)

    # ------------------------- etiquetas -------------------------
    d.ents.append(ir.Leader((L * 0.5, yr), (L * 0.5 - 60 * f, yr + 70 * f),
                            rebar_spacing(d1, s1, "inferior"), th,
                            shelf=25 * f, side=-1))
    d.ents.append(ir.Leader((L * 0.75, yd), (L * 0.75 + 40 * f,
                                             yd - 70 * f),
                            rebar_spacing(d2, s2, "repartición"),
                            th, shelf=25 * f, side=1))
    if sup:
        d.ents.append(ir.Leader((L + bw / 2 - a * 0.5, t - R),
                                (L + bw / 2 - a * 0.5 + 30 * f,
                                 t + 75 * f),
                                rebar_spacing(d3, p["s3"] * 10, "superior"),
                                th, shelf=25 * f, side=1))

    # ---------------------- cuadro de despiece ----------------------
    filas, total = [], 0.0
    q1 = int(L / s1) + 1
    celdas, sk, _ = fila_barra("B1", "inf.", b1_pts, d1, 2.5 * d1, q1)
    total += peso_barra(d1) * q1 * dev1 / 1000.0
    filas.append((celdas, sk))

    len2 = L + 2 * bw - 2 * R
    celdas, sk, _ = fila_barra("B2", "repart.", [(0, 0), (1, 0)], d2,
                               2 * d2, n2)
    celdas[4] = f"{len2 / 1000.0:.2f}"
    celdas[6] = f"{peso_barra(d2) * n2 * len2 / 1000.0:.2f}"
    total += peso_barra(d2) * n2 * len2 / 1000.0
    filas.append((celdas, sk))

    if sup:
        q3 = 2
        celdas, sk, _ = fila_barra("B3", "sup.", pts, d3, 2.5 * d3, q3)
        total += peso_barra(d3) * q3 * dev3 / 1000.0
        filas.append((celdas, sk))

    y_tab = -hh - 160 * f
    tb = cuadro_despiece((-bw - 90 * f, y_tab), f, filas, total_kg=total)
    d.ents.append(tb)
    y_min = y_tab - (len(filas) + 1.6) * tb.row_h - 14 * f

    notas = [f"CONCRETO f'c = 21 MPa  |  RECUBRIMIENTO r = {ir.fmt_cm(R)} cm",
             f"LOSA e = {ir.fmt_cm(t)} cm  |  APOYOS: {ir.fmt_cm(bw)} cm"]
    for i, s in enumerate(notas):
        d.ents.append(Text((-bw - 90 * f, y_min - i * 8 * f), s,
                           2.5 * f, 0, ir.L_TXT, "l", "m"))
    d.ents.append(Text((L / 2, y_min - len(notas) * 8 * f - 14 * f),
                       f"LOSA {ir.fmt_cm(t)} cm, LUZ {ir.fmt_m(L)} m  -  "
                       f"ESC {p['escala']}", 4.5 * f, 0, ir.L_TXT, "c", "m"))
    return d
