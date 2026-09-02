# -*- coding: utf-8 -*-
"""
generators.base_plate — Placa base de columna con pernos de anclaje.

Genera: planta (perforaciones, pernos, cartelas, ejes), elevación (placa de
canto, columna, pernos proyectados, cartelas, grout, N.P.), detalle del perno
y cuadro de pernos de anclaje. Acotado completo en dos niveles.
"""

from .panels import SpecPanel
from .data import W_DB, DIAM_PERNOS, ESCALAS
from core import ir
from core.ir import Line, Poly, Circle, Text, Dim
from core.geom import (hatch_poly, poly_bar, level_symbol, break_line,
                       weld_symbol, thread_zigzag, line_x, line_y)
from core.dims import DimBuilder
from core.tables import tabla_pernos


# ----------------------------------------------------------------- panel --
class BasePlatePanel(SpecPanel):
    SPEC = [
        ("perfil", "Perfil columna", "combo",
         list(W_DB) + ["Manual"], "W250X25"),
        ("d", "Profundidad d (mm)", "float", 120, 1200, 257, 0, 5, ""),
        ("bf", "Ancho ala bf (mm)", "float", 80, 600, 101, 0, 5, ""),
        ("tw", "Espesor alma tw", "float", 4, 60, 5.8, 1, 0.5, ""),
        ("tf", "Espesor ala tf", "float", 6, 80, 8.4, 1, 0.5, ""),
        ("B", "Placa B, ancho X (mm)", "float", 150, 2000, 440, 0, 10, ""),
        ("N", "Placa N, largo Y (mm)", "float", 150, 2000, 590, 0, 10, ""),
        ("t", "Espesor placa (mm)", "float", 6, 60, 12, 0, 1, ""),
        ("n_pernos", "Nº de pernos", "combo", ["4", "6", "8"], "4"),
        ("d_perno", "Ø perno (mm)", "combo", DIAM_PERNOS, 19),
        ("g", "Separación g, eje X", "float", 60, 1400, 345, 0, 5, ""),
        ("p", "Separación p, eje Y", "float", 60, 1500, 495, 0, 5, ""),
        ("P", "Proyección P (mm)", "float", 40, 400, 100, 0, 5, ""),
        ("Le", "Empotramiento Le", "float", 200, 1500, 450, 0, 25, ""),
        ("cartelas", "Cartelas (gracejes)", "chk", True),
        ("hs", "Altura cartela hs", "float", 50, 400, 150, 0, 10, ""),
        ("ls", "Largo cartela ls", "float", 30, 300, 80, 0, 10, ""),
        ("ts", "Espesor cartela ts", "float", 6, 40, 12, 0, 1, ""),
        ("w_sold", "Soldadura w (mm)", "float", 4, 25, 8, 0, 1, ""),
        ("detalle_perno", "Detalle del perno", "chk", True),
        ("tabla_pernos", "Cuadro de pernos", "chk", True),
        ("escala", "Escala de acotado", "combo", ESCALAS, "1:50"),
    ]

    def on_change(self):
        if getattr(self, "_busy", False):
            return
        self._busy = True
        perfil = self.w["perfil"].currentText()
        if perfil in W_DB:
            s = W_DB[perfil]
            self.set_many({"d": s["d"], "bf": s["bf"],
                           "tw": s["tw"], "tf": s["tf"]})
        d = self.w["d"].value()
        bf = self.w["bf"].value()
        cart = self.w["cartelas"].isChecked()
        ls = self.w["ls"].value()
        dh = float(self.w["d_perno"].currentText())
        extra = (2 * ls + dh + 60) if cart else 110.0
        g = bf + extra
        pp = d + extra
        self.set_many({"g": _r5(g), "p": _r5(pp),
                       "B": _r10(g + 90), "N": _r10(pp + 90)})
        self._busy = False


def _r5(v): return round(v / 5.0) * 5.0
def _r10(v): return round(v / 10.0) * 10.0


def _bolt_rows(n: int, p: float):
    """Coordenadas Y de las filas de pernos (n/2 filas equidistantes)."""
    k = n // 2
    if k == 1:
        return [0.0]
    step = p / (k - 1)
    return [-p / 2 + i * step for i in range(k)]


# -------------------------------------------------------------- generador --
def build_base_plate(p: dict) -> ir.Drawing:
    d = ir.Drawing()
    f = p.get("_escala", 5.0)
    th = 3.0 * f
    db = DimBuilder(d.ents, th)

    D, BF, TW, TF = p["d"], p["bf"], p["tw"], p["tf"]
    B, N, t = p["B"], p["N"], p["t"]
    n = int(p["n_pernos"])
    dh = float(p["d_perno"])
    g, pp, P = p["g"], p["p"], p["P"]
    cart = p["cartelas"]
    hs, ls, ts = p["hs"], p["ls"], p["ts"]
    w_sold = p["w_sold"]
    ys_rows = _bolt_rows(n, pp)
    r_h = dh / 2.0 + 3.0          # perforación sobredimensionada +6 mm

    # ============================ PLANTA ============================
    _planta(d, db, p, B, N, BF, D, TW, TF, dh, g, pp, r_h, n, ys_rows,
            cart, ls, ts, f, th)

    # ========================== ELEVACIÓN ===========================
    ex = B / 2.0 + 150.0 * f + N / 2.0          # centro de la elevación
    _elevacion(d, db, p, ex, B, N, BF, D, TW, t, dh, g, pp, P, ys_rows,
               cart, hs, ls, ts, w_sold, f, th)

    # ======================= DETALLE DEL PERNO ======================
    x_end = ex + N / 2.0 + 90.0 * f
    if p["detalle_perno"]:
        from .anchor_bolt import draw_bolt_detail
        dx = x_end + 90.0 * f + 8 * dh
        draw_bolt_detail(d.ents, dx, 0.0, p, f, th)
        x_end = dx + 10 * dh

    # ======================= CUADRO DE PERNOS =======================
    y_tab = -N / 2.0 - 115.0 * f
    if p["tabla_pernos"]:
        datos = [[str(n), str(dh), str(int(p["Le"])), str(int(P)),
                  "A307", "1 tuerca + arandela"]]
        tb = tabla_pernos((-B / 2.0 - 90.0 * f, y_tab), f, datos)
        d.ents.append(tb)
        y_tab -= 3 * tb.row_h + 12.0 * f

    # ============================= NOTAS ============================
    notas = [
        f"PLACA BASE A36  e = {t:g} mm",
        f"PERNOS DE ANCLAJE {n}x Ø{dh:g} A307, EMPOTRAMIENTO {int(p['Le'])} mm, "
        f"PROYECCIÓN {int(P)} mm",
        "GROUT: MORTERO DE PEGADO e = 20 MPa",
        f"SOLDADURAS DE FILETE w = {w_sold:g} mm, AWS D1.1",
    ]
    if cart:
        notas.append(f"CARTELAS: PLACA A36 e = {ts:g} mm, "
                     f"SOLDADURAS w = {w_sold:g} mm")
    y0 = y_tab - 12.0 * f
    for i, s in enumerate(notas):
        d.ents.append(Text((-B / 2.0 - 90.0 * f, y0 - i * 8.0 * f), s,
                           2.5 * f, 0, ir.L_TXT, "l", "m"))

    d.ents.append(Text((x_end / 2.0, y0 - len(notas) * 8.0 * f - 14.0 * f),
                       f"PLACA BASE PARA COLUMNA {p['perfil']}  -  "
                       f"ESC {p['escala']}", 4.5 * f, 0, ir.L_TXT, "c", "m"))
    return d


# ----------------------------------------------------------------- planta --
def _planta(d, db, p, B, N, BF, D, TW, TF, dh, g, pp, r_h, n, ys_rows,
            cart, ls, ts, f, th):
    e = d.ents
    # placa
    e.append(ir.rect(-B / 2, -N / 2, B / 2, N / 2))
    # contorno de la columna (W) con d en Y y bf en X
    a, c, hw = D / 2 - TF, D / 2, TW / 2
    e.append(Poly([
        (-BF / 2, c), (BF / 2, c), (BF / 2, a), (hw, a), (hw, -a),
        (BF / 2, -a), (BF / 2, -c), (-BF / 2, -c), (-BF / 2, -a),
        (-hw, -a), (-hw, a), (-BF / 2, a)], closed=True))
    # huellas de cartelas
    if cart:
        e.append(ir.rect(-ts / 2, D / 2, ts / 2, D / 2 + ls))
        e.append(ir.rect(-ts / 2, -D / 2 - ls, ts / 2, -D / 2))
    # perforaciones
    for x in (-g / 2, g / 2):
        for y in ys_rows:
            e.append(Circle((x, y), r_h, ir.L_PERF))
            e.append(Line((x - r_h - 4 * f, y), (x + r_h + 4 * f, y), ir.L_EJE))
            e.append(Line((x, y - r_h - 4 * f), (x, y + r_h + 4 * f), ir.L_EJE))
    # ejes principales
    e.append(line_y(0, -B / 2 - 35 * f, B / 2 + 35 * f))
    e.append(line_x(0, -N / 2 - 35 * f, N / 2 + 35 * f))
    # ejes de filas y columnas de pernos
    for y in ys_rows:
        if abs(y) > 1:
            e.append(line_y(y, -B / 2 - 25 * f, B / 2 + 25 * f))
    for x in (-g / 2, g / 2):
        e.append(line_x(x, -N / 2 - 25 * f, N / 2 + 25 * f))

    # acotado: abajo (ancho B), derecha (largo N)
    y1 = -N / 2 - 40 * f
    db.h_chain([-B / 2, -g / 2, g / 2, B / 2], -N / 2, y1, ext_from=-N / 2)
    db.h_total(-B / 2, B / 2, -N / 2, y1 - 35 * f, ext_from=-N / 2)
    x1 = B / 2 + 40 * f
    db.v_chain([-N / 2, -pp / 2, pp / 2, N / 2], B / 2, x1, ext_from=N / 2)
    db.v_total(-N / 2, N / 2, B / 2, x1 + 35 * f, ext_from=N / 2)
    # arriba: bf del perfil
    db.h_total(-BF / 2, BF / 2, D / 2, D / 2 + 40 * f, ext_from=D / 2)
    # izquierda: d del perfil
    db.v_total(-D / 2, D / 2, -BF / 2, -B / 2 - 40 * f, ext_from=-BF / 2)
    # etiqueta de perforación
    tip = (g / 2 + r_h * 0.707, pp / 2 + r_h * 0.707)
    elb = (tip[0] + 42 * f, tip[1] + 42 * f)
    d.ents.append(ir.Leader(tip, elb,
                            f"Ø{2 * r_h:g} PERF. ({n}x Ø{dh:g})", th,
                            shelf=18 * f, side=1))


# -------------------------------------------------------------- elevación --
def _elevacion(d, db, p, ex, B, N, BF, D, TW, t, dh, g, pp, P, ys_rows,
               cart, hs, ls, ts, w_sold, f, th):
    e = d.ents
    zc, zp = 20.0, 20.0 + t          # tope grout / tope placa
    w_conc, h_conc = N + 200, 350
    # pedestal de concreto + grout
    c_rect = ir.rect(ex - w_conc / 2, -h_conc, ex + w_conc / 2, 0)
    e.append(c_rect)
    e.extend(hatch_poly(c_rect.pts, 9 * f))
    g_rect = ir.rect(ex - (N - 20) / 2, 0, ex + (N - 20) / 2, zc)
    e.append(g_rect)
    e.extend(hatch_poly(g_rect.pts, 5 * f))
    # placa y columna
    e.append(ir.rect(ex - N / 2, zc, ex + N / 2, zp))
    z_top = zp + 1.7 * D
    e.append(ir.rect(ex - BF / 2, zp, ex + BF / 2, z_top))
    # rotura superior de columna
    e.extend(break_line((ex - BF / 2, z_top), (ex + BF / 2, z_top), 6 * f))
    # pernos (vistas de canto): shaft + arandela + tuerca + rosca
    Lth = 2.5 * dh + 8
    for x in (-g / 2, g / 2):
        xb = ex + x
        e.append(Line((xb - dh / 2, zp - 6), (xb - dh / 2, zp + P),
                      ir.L_ACERO, width=max(1.2, dh * 0.16)))
        e.append(Line((xb + dh / 2, zp - 6), (xb + dh / 2, zp + P),
                      ir.L_ACERO, width=max(1.2, dh * 0.16)))
        e.append(ir.rect(xb - 1.5 * dh, zp, xb + 1.5 * dh, zp + 5, ir.L_ACERO))
        e.append(ir.rect(xb - 0.9 * dh, zp + 5, xb + 0.9 * dh,
                         zp + 5 + 0.8 * dh, ir.L_ACERO))
        e.extend(thread_zigzag((xb, zp + P - Lth), Lth, dh,
                               max(2.5, dh * 0.18), ir.L_ACERO))
    # cartelas (triángulos) en caras exteriores de alas
    if cart:
        for sx in (-1, 1):
            x0 = ex + sx * BF / 2
            tri = [(x0, zp), (x0, zp + hs), (x0 + sx * ls, zp)]
            e.append(Poly(tri, closed=True))
            e.extend(weld_symbol((x0 + sx * 2, zp + 2),
                                 (x0 + sx * (25 * f), zp + 22 * f),
                                 th * 0.8))
            # cota de altura de cartela (lado interior)
            db.v_total(zp, zp + hs, x0, x0 + sx * (ls + 28 * f),
                       ext_from=x0)
        # símbolo de soldadura columna-placa
        e.extend(weld_symbol((ex - BF / 2 + 4, zp + 4),
                             (ex - BF / 2 - 30 * f, zp + 30 * f), th * 0.8))
    # eje de columna y nivel de piso
    e.append(line_x(ex, -h_conc - 30 * f, z_top + 25 * f))
    e.extend(level_symbol((ex - w_conc / 2 - 25 * f, 0), th, "N.P. ±0.00"))

    # acotado derecho: grout / placa / proyección, y altura de columna
    x1 = ex + N / 2 + 40 * f
    db.v_chain([0, zc, zp, zp + P], ex + N / 2, x1, ext_from=ex + N / 2)
    db.v_total(zp, zp + D, ex + BF / 2, x1 + 35 * f, ext_from=ex + BF / 2)
    # abajo: largo de placa y ancho de pedestal
    yb = -h_conc - 40 * f
    db.h_chain([ex - N / 2, ex + N / 2], -h_conc, yb, ext_from=-h_conc,
               texts=[f"N = {ir.fmt_mm(N)}"])
    db.h_total(ex - w_conc / 2, ex + w_conc / 2, -h_conc, yb - 35 * f,
               ext_from=-h_conc)
    # etiqueta de espesor de placa
    d.ents.append(ir.Leader((ex + N / 4, zp + t / 2),
                            (ex + N / 2 + 55 * f, zp + 45 * f),
                            f"PLACA e = {t:g} mm", th, shelf=20 * f, side=1))
