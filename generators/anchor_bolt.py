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
from core.tables import tabla_pernos, tabla_perno_pg
from core.bolt_spec import PGSpecError, pg_spec_from_params
from core.bounds import drawing_bounds
from core.geom import break_line


# ----------------------------------------------------------------- panel --
class AnchorBoltPanel(SpecPanel):
    SPEC = [
        ("d_perno", "Ø perno (mm)", "combo", DIAM_PERNOS + [25.4], 25.4),
        ("d_nominal", "Diámetro en tabla PG", "combo", ["mm", "1 in"], "1 in"),
        ("tipo", "Tipo de anclaje", "combo",
         ["PG (recto con golilla)", "L (codo 90°)", "J (gancho 135°)",
          "Recto con placa"], "PG (recto con golilla)"),
        ("Le", "Empotramiento R (mm)", "float", 150, 2000, 850, 0, 25, ""),
        ("P", "Proyección P (mm)", "float", 40, 500, 400, 0, 5, ""),
        ("lg", "Largo de gancho (mm)", "float", 60, 600, 150, 0, 10, ""),
        ("tipo_hilo", "Tipo de hilo", "combo", ["8UN", "UNC"], "8UN"),
        ("h1", "Largo hilo superior h1", "float", 40, 500, 150, 0, 5, ""),
        ("h2", "Largo hilo inferior h2", "float", 40, 300, 75, 0, 5, ""),
        ("W", "Golilla cuadrada W", "float", 40, 300, 75, 0, 5, ""),
        ("t_golilla", "Espesor golilla t", "float", 5, 60, 20, 0, 1, ""),
        ("b_golilla", "Vuelo soldadura b", "float", 20, 150, 50, 0, 5, ""),
        ("permitir_h1_bajo_tc", "Rosca superior bajo T.C.", "chk", False),
        ("material", "Material", "combo",
         ["A307", "A36", "F1554 Gr.55", "A325"], "A307"),
        ("n", "Cantidad total", "int", 1, 500, 48, 1, ""),
        ("tabla", "Cuadro de pernos", "chk", True),
        ("escala", "Escala de acotado", "combo", ESCALAS, "1:25"),
    ]

    def on_change(self):
        pg = self.w["tipo"].currentText().startswith("PG")
        inch = pg and self.w["d_nominal"].currentText() == "1 in"
        self.w["d_perno"].setEnabled(not inch)
        if inch and self.w["d_perno"].currentText() != "25.4":
            self.w["d_perno"].blockSignals(True)
            self.w["d_perno"].setCurrentText("25.4")
            self.w["d_perno"].blockSignals(False)
        for key in ("d_nominal", "h1", "h2", "W", "t_golilla", "b_golilla",
                    "permitir_h1_bajo_tc"):
            self.w[key].setEnabled(pg)
        self.w["lg"].setEnabled(not pg)

    def set_params(self, p):
        # Un archivo anterior sigue expresando su diámetro en mm.
        super().set_params({"d_nominal": "mm", **p})


# ------------------------------------------------------- detalle reusable --
def draw_bolt_detail(ents, ox, oy, p, f, th, with_dims=True):
    """Dibuja el detalle del perno con origen (ox, oy) en la rasante del
    concreto. `p` necesita: d_perno, tipo, Le, P, lg, material."""
    db = DimBuilder(ents, th)
    if str(p.get("tipo", "")).startswith("PG"):
        return _draw_pg_detail(ents, ox, oy, p, f, th, with_dims)
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
    if tipo.startswith("PG"):
        h2 = min(float(p.get("h2", 75)), Le)
        tw = float(p.get("t_golilla", 20))
        ww = float(p.get("W", 75))
        tail = min(float(p.get("b_golilla", 50)), Le - tw)
        washer_y = oy - Le + tail
        ents.append(Line((ox, oy - Le), (ox, oy + P), ir.L_ACERO,
                         width=max(1.2, dh * 0.16)))
        # Golilla cuadrada inferior, tuerca y contratuerca soldadas por puntos.
        ents.append(ir.rect(ox - ww / 2, washer_y, ox + ww / 2,
                            washer_y + tw, ir.L_ACERO))
        nut_h = 0.8 * dh
        ents.append(ir.rect(ox - 0.9 * dh, washer_y - nut_h,
                            ox + 0.9 * dh, washer_y, ir.L_ACERO))
        ents.extend(thread_zigzag((ox, oy - Le), h2, dh,
                                  max(2.5, dh * 0.18), ir.L_ACERO))
    elif tipo.startswith("L"):
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
    h1 = min(float(p.get("h1", Lth)), P)
    ents.extend(thread_zigzag((ox, oy + P - h1), h1, dh,
                              max(2.5, dh * 0.18), ir.L_ACERO))
    ents.append(ir.rect(ox - 1.5 * dh, oy, ox + 1.5 * dh, oy + 5, ir.L_ACERO))
    ents.append(ir.rect(ox - 0.9 * dh, oy + 5, ox + 0.9 * dh,
                        oy + 5 + 0.8 * dh, ir.L_ACERO))
    if tipo.startswith("PG"):
        ents.append(ir.rect(ox - 0.9 * dh, oy + 5 + 0.8 * dh,
                            ox + 0.9 * dh, oy + 5 + 1.6 * dh, ir.L_ACERO))

    if not with_dims:
        return

    # nivel y acotado
    ents.extend(level_symbol((ox - w_conc / 2 - 25 * f, oy), th, "N.P."))
    x1 = ox + w_conc / 2 + 40 * f
    db.v_chain([oy, oy + P], ox + dh / 2, x1,
               texts=[f"P = {ir.fmt_mm(P)}"], ext_from=ox + dh / 2)
    db.v_chain([oy - Le, oy], ox + dh / 2, x1,
               texts=[f"Le = {ir.fmt_mm(Le)}"], ext_from=ox + dh / 2)
    if tipo.startswith("PG"):
        db.v_chain([oy - Le, oy], ox - dh / 2,
                   ox - w_conc / 2 - 40 * f,
                   texts=[f"R = {ir.fmt_mm(Le)}"], ext_from=ox - dh / 2)
        db.v_total(oy - Le, oy + P, ox - dh / 2,
                   ox - w_conc / 2 - 75 * f,
                   txt=f"L = {ir.fmt_mm(Le + P)}", ext_from=ox - dh / 2)
        washer_y = oy - Le + float(p.get("b_golilla", 50))
        ents.append(ir.Leader((ox + float(p.get("W", 75)) / 2,
                               washer_y + float(p.get("t_golilla", 20)) / 2),
                              (ox + 55 * f, oy - Le + 55 * f),
                              "GOLILLA CUADRADA", th, shelf=22 * f, side=1))
    elif tipo.startswith("L"):
        db.h_total(ox, ox + lg, oy - Le, oy - Le - 35 * f,
                   texts=[f"{ir.fmt_mm(lg)}"], ext_from=oy - Le)
    elif tipo.startswith("J"):
        db.h_total(ox, ox + hx, oy - Le, oy - Le - 35 * f,
                   texts=[f"{ir.fmt_mm(hx)}"], ext_from=oy - Le)
    # etiqueta del perno
    ents.append(ir.Leader((ox + dh * 0.707, oy + P - Lth * 0.35),
                          (ox + 55 * f, oy + P + 38 * f),
                          f"Ø{dh:g} {mat} ROSCADO", th, shelf=22 * f, side=1))


def _draw_pg_detail(ents, ox, tc_y, p, f, th, with_dims=True):
    """Detalle PG acotado desde una única especificación, sin truncamientos."""
    spec = pg_spec_from_params(p)
    db = DimBuilder(ents, th)
    d, R, P = spec.d_mm, spec.R, spec.P
    y_bot, y_top = tc_y - R, tc_y + P
    half = d / 2.0
    # Vástago como dos líneas reales, no como una línea gruesa simbólica.
    ents.extend([Line((ox - half, y_bot), (ox - half, y_top), ir.L_ACERO),
                 Line((ox + half, y_bot), (ox + half, y_top), ir.L_ACERO),
                 line_x(ox, y_bot - 30 * f, y_top + 40 * f)])
    # Borde interrumpido esquemático de apoyo, tal como el detalle S/ESC.
    span = max(16 * d, spec.W + 8 * d)
    lip = min(P * 0.33, 80.0)
    ents.extend([Line((ox - span / 2, tc_y), (ox + span / 2, tc_y), ir.L_CONC),
                 Line((ox - span / 2, tc_y + lip), (ox + span / 2 - lip, tc_y + lip), ir.L_CONC),
                 Line((ox + span / 2 - lip, tc_y + lip), (ox + span / 2, tc_y), ir.L_CONC)])
    ents.extend(break_line((ox - span / 2, tc_y), (ox - span / 2, tc_y + lip),
                           0.2 * th))
    # Convención de rosca en líneas finas interiores; extremos exactos h1/h2.
    for start, end in ((y_top - spec.h1, y_top), (y_bot, y_bot + spec.h2)):
        for x in (ox - 0.32 * d, ox + 0.32 * d):
            ents.append(Line((x, start), (x, end), ir.L_PERF))
        ents.extend([Line((ox - half, start), (ox + half, start), ir.L_ACERO),
                     Line((ox - half, end), (ox + half, end), ir.L_ACERO)])
    # Componentes superiores: golilla estándar, tuerca y contratuerca.
    washer_t = spec.standard_washer_thickness
    washer_w = max(2.9 * d, 28.0)
    nut_h, nut_w = spec.nut_height, 1.8 * d
    wy = tc_y + spec.upper_washer_bottom
    ents.append(ir.rect(ox - washer_w / 2, wy, ox + washer_w / 2,
                        wy + washer_t, ir.L_ACERO))
    for y in (wy + washer_t, wy + washer_t + nut_h):
        ents.append(ir.rect(ox - nut_w / 2, y, ox + nut_w / 2,
                            y + nut_h, ir.L_ACERO))
    # Golilla cuadrada y tuerca soldada por puntos inferiores. b corresponde
    # al extremo libre bajo el conjunto, y no se vuelve a reinterpretar.
    square_y = y_bot + spec.b
    ents.append(ir.rect(ox - spec.W / 2, square_y,
                        ox + spec.W / 2, square_y + spec.t, ir.L_ACERO))
    ents.append(ir.rect(ox - nut_w / 2, square_y - nut_h,
                        ox + nut_w / 2, square_y, ir.L_ACERO))
    weld_tip = (ox + nut_w / 2, square_y - nut_h / 2)
    if not with_dims:
        return spec
    # Niveles equivalentes al ejemplo, conservando el rótulo parametrizable.
    el = str(p.get("nivel_el", "E.L."))
    tc = str(p.get("nivel_tc", "T.C."))
    level_x = ox + span / 2 + 8 * th
    ents.extend(level_symbol((level_x, tc_y), th, tc))
    ents.append(Line((level_x - 3 * th, tc_y + lip),
                     (level_x + 4 * th, tc_y + lip), ir.L_CONC))
    ents.append(Text((level_x - 2.7 * th, tc_y + lip + th * .35), el, th,
                     layer=ir.L_TXT, ha="l", va="b"))
    # L fuera; R y P interiores. Las restantes cotas se ubican en torno a
    # los componentes físicos, por lo que tabla y figura permanecen trazables.
    left = ox - span / 2 - 32 * f
    db.v_total(y_bot, y_top, ox - half, left - 35 * f,
               txt="L", ext_from=ox - half)
    db.v_total(y_bot, tc_y, ox - half, left,
               txt="R", ext_from=ox - half)
    db.v_total(tc_y, y_top, ox - half, left,
               txt="P", ext_from=ox - half)
    right = ox + spec.W / 2 + 6 * th
    db.h_total(ox - half, ox + half, tc_y - 140, tc_y - 180,
               txt="d", ext_from=tc_y - 140)
    db.v_total(y_top - spec.h1, y_top, ox + half, right,
               txt="h1", ext_from=ox + half)
    db.v_total(y_bot, y_bot + spec.h2, ox + half, right,
               txt="h2", ext_from=ox + half)
    db.h_total(ox - spec.W / 2, ox + spec.W / 2, square_y,
               square_y + spec.t + 8 * th, txt="W", ext_from=square_y + spec.t)
    db.v_total(square_y, square_y + spec.t, ox + spec.W / 2,
               ox - spec.W / 2 - 4 * th, txt="t", ext_from=ox - spec.W / 2)
    db.v_total(y_bot, square_y, ox - spec.W / 2, ox - spec.W / 2 - 4 * th,
               txt="b", ext_from=ox - spec.W / 2)
    ents.append(ir.Leader((ox + nut_w / 2, wy + washer_t + nut_h * 1.5),
                          (right + 4 * th, y_top + 5 * th),
                          "TUERCA Y CONTRATUERCA", th, shelf=2 * th))
    ents.append(ir.Leader((ox + washer_w / 2, wy + washer_t / 2),
                          (right + 4 * th, y_top + 2 * th), "GOLILLA ESTÁNDAR",
                          th, shelf=2 * th))
    ents.append(ir.Leader((ox + spec.W / 2, square_y + spec.t / 2),
                          (right + 4 * th, square_y + spec.t + 5 * th),
                          "GOLILLA CUADRADA", th, shelf=2 * th))
    ents.extend(_spot_weld(weld_tip, (right + 4 * th, y_bot - 4 * th), th))
    return spec


def _spot_weld(tip, elbow, th):
    """Llamada de soldadura por puntos, consistente con DXF/COM/preview."""
    x, y = elbow
    return [ir.Leader(tip, elbow, "SOLDADURA\nPOR PUNTOS", th,
                      ir.L_SOLD, shelf=4 * th, side=1),
            ir.Circle((x + 1.6 * th, y), 0.5 * th, ir.L_SOLD)]


# -------------------------------------------------------------- generador --
def build_anchor_bolt(p: dict) -> ir.Drawing:
    if str(p.get("tipo", "")).startswith("PG"):
        return _build_pg(p)
    d = ir.Drawing()
    f = p.get("_escala", 2.5)
    th = 3.0 * f
    dh = float(p["d_perno"])
    is_pg = str(p.get("tipo", "")).startswith("PG")
    spec = pg_spec_from_params(p) if is_pg else None
    diam_label = spec.d_display if spec else f"{dh:g}"

    draw_bolt_detail(d.ents, 0.0, 0.0, p, f, th)
    p_top = spec.P if spec else float(p["P"])
    d.ents.append(Text((0.0, p_top + 90 * f),
                       'DET. PERNO TIPO "PG"' if is_pg else "DETALLE PERNO",
                       3.5 * f, layer=ir.L_TXT, ha="c", va="m"))
    w_conc = max(14 * dh, (spec.W + 4 * dh) if spec else 14 * dh)

    embed = spec.R if spec else float(p["Le"])
    y_tab = -embed - 105.0 * f
    if p["tabla"]:
        if str(p.get("tipo", "")).startswith("PG"):
            tb = tabla_perno_pg((-w_conc / 2 - 70 * f, y_tab), f, p)
        else:
            datos = [[str(p["n"]), str(dh), str(int(p["Le"])), str(int(p["P"])),
                      str(p["material"]), "1 tuerca + arandela"]]
            tb = tabla_pernos((-w_conc / 2 - 70 * f, y_tab), f, datos)
        d.ents.append(tb)
        y_tab -= (len(tb.rows) + 2) * tb.row_h + 12.0 * f

    notas = [
        f"PERNO DE ANCLAJE Ø{diam_label} {p['material']}, "
        f"TIPO {p['tipo']}",
        f"EMPOTRAMIENTO R = {int(embed)} mm, PROYECCIÓN P = {int(p_top)} mm",
        "ROSCA: ASME B1.1  |  GALVANIZADO EN CALIENTE",
    ]
    if str(p.get("tipo", "")).startswith("PG"):
        notas.append("GOLILLA CUADRADA Y TUERCA INFERIOR SOLDADAS POR PUNTOS")
    else:
        notas.append(f"GANCHO: RADIO INTERIOR = 2.5Ø, "
                     f"LARGO = {int(p['lg'])} mm")
    for i, s in enumerate(notas):
        d.ents.append(Text((-w_conc / 2 - 70 * f, y_tab - i * 8.0 * f), s,
                           2.5 * f, 0, ir.L_TXT, "l", "m"))
    d.ents.append(Text((0.0, y_tab - len(notas) * 8.0 * f - 14.0 * f),
                       f"PERNO DE ANCLAJE Ø{diam_label}  -  ESC {p['escala']}",
                       4.5 * f, 0, ir.L_TXT, "c", "m"))
    return d


def _build_pg(p):
    spec = pg_spec_from_params(p)
    f = float(p.get("_escala", 2.5))
    th = 6.0 * f
    drawing = ir.Drawing()
    _draw_pg_detail(drawing.ents, 0, 0, p, f, th)
    x0, y0, x1, y1 = drawing_bounds(drawing)
    title_y = y0 - 4 * th
    title = 'DET. PERNO TIPO "PG"'
    drawing.ents.extend([
        Text((x0, title_y), title, 1.7 * th, layer=ir.L_TXT, ha="l", va="b"),
        Line((x0, title_y - .5 * th), (x0 + len(title) * 1.1 * th, title_y - .5 * th), ir.L_TXT),
        Text((x0, title_y - 2.8 * th), "S/ESC. — COTAS EN mm SALVO DIÁMETRO INDICADO",
             .85 * th, layer=ir.L_TXT, ha="l", va="b")])
    if p.get("tabla", True):
        table_x = x1 + 5 * th
        drawing.ents.append(tabla_perno_pg((table_x, y1), 2 * f, spec))
        drawing.ents.append(Text((table_x, y1 - 250 * f - 3 * th),
                                 f"MATERIAL: {spec.material}", th,
                                 layer=ir.L_TXT, ha="l", va="b"))
    return drawing
