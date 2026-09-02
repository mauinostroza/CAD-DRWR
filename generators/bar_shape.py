# -*- coding: utf-8 -*-
"""
generators.bar_shape — Armado rápido de barras: formas normalizadas.

Recta, gancho 90° (L), U, estribo cerrado 135° y Z, con radios de doblez
reales (arcos de línea central), acotado de tramos, longitud de desarrollo
y fila de cuadro de despiece.
"""

from .panels import SpecPanel
from .data import DIAM_BARRAS, ESCALAS
from core import ir
from core.ir import Text
from core.geom import poly_bar, stirrup_pts
from core.dims import DimBuilder
from core.tables import cuadro_despiece, fila_barra


# ----------------------------------------------------------------- panel --
class BarShapePanel(SpecPanel):
    SPEC = [
        ("forma", "Forma de barra", "combo",
         ["Recta", "Gancho 90° (L)", "U", "Estribo 135°", "Z"], "U"),
        ("a", "Tramo a (mm)", "float", 50, 12000, 600, 0, 10, ""),
        ("b", "Tramo b (mm)", "float", 50, 3000, 300, 0, 10, ""),
        ("c", "Tramo c (mm)", "float", 0, 3000, 200, 0, 10, ""),
        ("d_barra", "Ø barra (mm)", "combo", DIAM_BARRAS, 12),
        ("k", "Radio doblez R = kØ", "float", 2, 8, 4, 1, 0.5, ""),
        ("qty", "Cantidad", "int", 1, 999, 10, 1, ""),
        ("marca", "Marca de barra", "combo",
         ["B1", "B2", "B3", "B4", "B5", "B6"], "B1"),
        ("escala", "Escala de acotado", "combo", ESCALAS, "1:25"),
    ]


def _path(p):
    forma = p["forma"]
    a, b, c = p["a"], p["b"], p["c"]
    if forma == "Recta":
        return [(0, 0), (a, 0)]
    if forma.startswith("Gancho"):
        return [(0, 0), (a, 0), (a, b)]
    if forma == "U":
        return [(0, 0), (0, b), (a, b), (a, 0)]
    if forma.startswith("Estribo"):
        return stirrup_pts(a, b, float(p["d_barra"]), p["k"] * float(p["d_barra"]))
    return [(0, 0), (a, 0), (a, b), (a + c, b)]        # Z


# -------------------------------------------------------------- generador --
def build_bar_shape(p: dict) -> ir.Drawing:
    d = ir.Drawing()
    f = p.get("_escala", 2.5)
    th = 3.0 * f
    db = DimBuilder(d.ents, th)
    db_d = float(p["d_barra"])
    R_in = p["k"] * db_d
    pts = _path(p)
    ents, dev = poly_bar(pts, db_d, R_in, width=max(1.2, db_d * 0.12))
    d.ents.extend(ents)

    # acotado de tramos
    xs = sorted(set(round(pt[0], 3) for pt in pts))
    ys = sorted(set(round(pt[1], 3) for pt in pts))
    y_min, x_max = min(ys), max(xs)
    if len(xs) > 1:
        db.h_chain(xs, y_min, y_min - 45 * f, ext_from=y_min)
    if len(ys) > 1:
        db.v_chain(ys, x_max, x_max + 45 * f, ext_from=x_max)
    if p["forma"] == "Recta":
        db.h_total(0, p["a"], 0, -45 * f, ext_from=0)

    # nota de radio y desarrollo
    forma = p["forma"]
    if len(pts) > 2:
        d.ents.append(ir.Leader(pts[1], (pts[1][0] + 35 * f,
                                         pts[1][1] + 35 * f),
                                f"R = {p['k']:g}Ø = {R_in:g} mm", th,
                                shelf=20 * f, side=1))
    d.ents.append(Text((0, y_min - 90 * f),
                       f"DESARROLLO = {dev / 1000.0:.2f} m x {p['qty']} "
                       f"unidades", 3.0 * f, 0, ir.L_TXT, "c", "m"))

    # fila de despiece
    celdas, sk, _ = fila_barra(str(p["marca"]), "", pts, db_d, R_in,
                               int(p["qty"]))
    y_tab = y_min - 125 * f
    tb = cuadro_despiece((-max(xs) / 2 - 90 * f, y_tab), f,
                         [(celdas, sk)], total_kg=None,
                         title="CUADRO DE DESPIECE")
    d.ents.append(tb)
    y_min = y_tab - 2.6 * tb.row_h - 14 * f
    d.ents.append(Text((0, y_min),
                       f"BARRA {p['marca']} - {forma.upper()}  Ø{db_d:g}  -  "
                       f"ESC {p['escala']}", 4.5 * f, 0, ir.L_TXT, "c", "m"))
    return d
