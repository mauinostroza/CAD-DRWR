# -*- coding: utf-8 -*-
"""
generators.anchor_bolt — Pernos de anclaje: detalle de fabricación/instalación.

Tipos: L (codo 90°), J (gancho 135°) y recto con placa de anclaje.
Incluye rosca esquemática, tuerca, arandela, concreto de apoyo y acotado.
"""

from .panels import SpecPanel
from .data import DIAM_PERNOS, ESCALAS
from core import ir
from core.ir import Line, Poly, Text
from core.geom import (hatch_poly, poly_bar, level_symbol, thread_zigzag,
                       line_x)
from core.dims import DimBuilder
from core.tables import tabla_pernos


# ----------------------------------------------------------------- panel --
class AnchorBoltPanel(SpecPanel):
    SPEC = [
        ("d_perno", "Ø perno (mm)", "combo", DIAM_PERNOS, 19),
        ("tipo", "Tipo de anclaje", "combo",
         ["L (codo 90°)", "J (gancho 135°)", "Recto con placa"],
         "L (codo 90°)"),
        ("Le", "Empotramiento Le (mm)", "float", 150, 2000, 450, 0, 25, ""),
        ("P", "Proyección P (mm)", "float", 40, 500, 120, 0, 5, ""),
        ("lg", "Largo de gancho (mm)", "float", 60, 600, 150, 0, 10, ""),
        ("material", "Material", "combo",
         ["A307", "A36", "F1554 Gr.55", "A325"], "A307"),
        ("n", "Cantidad por columna", "int", 1, 24, 4, 1, ""),
        ("tabla", "Cuadro de pernos", "chk", True),
        ("escala", "Escala de acotado", "combo", ESCALAS, "1:25"),
    ]


# ------------------------------------------------------- detalle reusable --
def draw_bolt_detail(ents, ox, oy, p, f, th, with_dims=True):
    """Dibuja el detalle del perno con origen (ox, oy) en la rasante del
    concreto. `p` necesita: d_perno, tipo, Le, P, lg, material."""
    db = DimBuilder(ents, th)
    dh = float(p["d_perno"])
    Le, P = float(p["Le"]), float(p["P"])
    lg = float(p.get("lg", 150))
    tipo = p.get("tipo", "L (codo 90°)")
    mat = p.get("material", "A307")
    Lth = 2.5 * dh + 8
    w_conc = max(14 * dh, lg + 10 * dh)
    h_conc = Le + 120            # cubre el codo/gancho dentro del concreto

    # concreto y eje
    c_rect = ir.rect(ox - w_conc / 2, oy - h_conc, ox + w_conc / 2, oy)
    ents.append(c_rect)
    ents.extend(hatch_poly(c_rect.pts, 9 * f))
    ents.append(line_x(ox, oy - h_conc - 25 * f, oy + P + 30 * f))

    # cuerpo del perno según tipo
    R_in = 2.5 * dh
    if tipo.startswith("L"):
        pts = [(ox + lg, oy - Le), (ox, oy - Le), (ox, oy + P)]
        bar, _ = poly_bar(pts, dh, R_in, width=max(1.2, dh * 0.16))
        ents.extend(bar)
    elif tipo.startswith("J"):
        hx = 0.7071 * lg
        pts = [(ox + hx, oy - Le + hx), (ox, oy - Le), (ox, oy + P)]
        bar, _ = poly_bar(pts, dh, R_in, width=max(1.2, dh * 0.16))
        ents.extend(bar)
    else:  # recto con placa de anclaje
        ents.append(Line((ox, oy - Le), (ox, oy + P), ir.L_ACERO,
                         width=max(1.2, dh * 0.16)))
        tp = 12.0
        ents.append(ir.rect(ox - 3 * dh, oy - Le - tp, ox + 3 * dh,
                            oy - Le, ir.L_ACERO))

    # rosca, arandela y tuerca
    ents.extend(thread_zigzag((ox, oy + P - Lth), Lth, dh,
                              max(2.5, dh * 0.18), ir.L_ACERO))
    ents.append(ir.rect(ox - 1.5 * dh, oy, ox + 1.5 * dh, oy + 5, ir.L_ACERO))
    ents.append(ir.rect(ox - 0.9 * dh, oy + 5, ox + 0.9 * dh,
                        oy + 5 + 0.8 * dh, ir.L_ACERO))

    if not with_dims:
        return

    # nivel y acotado
    ents.extend(level_symbol((ox - w_conc / 2 - 25 * f, oy), th, "N.P."))
    x1 = ox + w_conc / 2 + 40 * f
    db.v_chain([oy, oy + P], ox + dh / 2, x1,
               texts=[f"P = {ir.fmt_mm(P)}"], ext_from=ox + dh / 2)
    db.v_chain([oy - Le, oy], ox + dh / 2, x1,
               texts=[f"Le = {ir.fmt_mm(Le)}"], ext_from=ox + dh / 2)
    if tipo.startswith("L"):
        db.h_total(ox, ox + lg, oy - Le, oy - Le - 35 * f,
                   texts=[f"{ir.fmt_mm(lg)}"], ext_from=oy - Le)
    elif tipo.startswith("J"):
        db.h_total(ox, ox + hx, oy - Le, oy - Le - 35 * f,
                   texts=[f"{ir.fmt_mm(hx)}"], ext_from=oy - Le)
    # etiqueta del perno
    ents.append(ir.Leader((ox + dh * 0.707, oy + P - Lth * 0.35),
                          (ox + 55 * f, oy + P + 38 * f),
                          f"Ø{dh:g} {mat} ROSCADO", th, shelf=22 * f, side=1))


# -------------------------------------------------------------- generador --
def build_anchor_bolt(p: dict) -> ir.Drawing:
    d = ir.Drawing()
    f = p.get("_escala", 2.5)
    th = 3.0 * f
    dh = float(p["d_perno"])

    draw_bolt_detail(d.ents, 0.0, 0.0, p, f, th)
    d.ents.append(Text((0.0, float(p["P"]) + 90 * f), "DETALLE PERNO",
                       3.5 * f, layer=ir.L_TXT, ha="c", va="m"))
    w_conc = 14 * dh

    h_conc = float(p["Le"]) + 120.0
    y_tab = -h_conc - 90.0 * f
    if p["tabla"]:
        datos = [[str(p["n"]), str(dh), str(int(p["Le"])), str(int(p["P"])),
                  str(p["material"]), "1 tuerca + arandela"]]
        tb = tabla_pernos((-w_conc / 2 - 70 * f, y_tab), f, datos)
        d.ents.append(tb)
        y_tab -= 3 * tb.row_h + 12.0 * f

    notas = [
        f"PERNO DE ANCLAJE Ø{dh:g} {p['material']}, "
        f"TIPO {p['tipo']}",
        f"EMPOTRAMIENTO Le = {int(p['Le'])} mm, PROYECCIÓN P = {int(p['P'])} mm",
        "ROSCA: ASME B1.1  |  GALVANIZADO EN CALIENTE",
        f"GANCHO: RADIO INTERIOR = 2.5Ø, LARGO = {int(p['lg'])} mm",
    ]
    for i, s in enumerate(notas):
        d.ents.append(Text((-w_conc / 2 - 70 * f, y_tab - i * 8.0 * f), s,
                           2.5 * f, 0, ir.L_TXT, "l", "m"))
    d.ents.append(Text((0.0, y_tab - len(notas) * 8.0 * f - 14.0 * f),
                       f"PERNO DE ANCLAJE Ø{dh:g}  -  ESC {p['escala']}",
                       4.5 * f, 0, ir.L_TXT, "c", "m"))
    return d
