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
from core.bounds import drawing_bounds


# ----------------------------------------------------------------- panel --
class PedestalPanel(SpecPanel):
    SPEC = [
        ("b", "Ancho sección b (cm)", "float", 20, 200, 30, 1, 5, ""),
        ("h", "Alto sección h (cm)", "float", 20, 200, 30, 1, 5, ""),
        ("H", "Altura pedestal (cm)", "float", 30, 600, 250, 1, 10, ""),
        ("r", "Recubrimiento (cm)", "float", 2, 10, 4, 1, 0.5, ""),
        ("n_barras", "Nº barras long.", "combo", ["4", "6", "8", "10", "12"], "8"),
        ("preset", "Distribución longitudinal", "combo",
         ["Total anterior", "Por caras", "Referencia 20"], "Total anterior"),
        ("n_sup", "Barras superiores (incl. esquinas)", "int", 2, 20, 7, 1, ""),
        ("n_inf", "Barras inferiores (incl. esquinas)", "int", 2, 20, 7, 1, ""),
        ("n_izq", "Barras intermedias izquierda", "int", 0, 18, 3, 1, ""),
        ("n_der", "Barras intermedias derecha", "int", 0, 18, 3, 1, ""),
        ("lazos_interiores", "Lazos interiores", "chk", False),
        ("lazo_vertical", "Lazo vertical central", "chk", True),
        ("lazo_horizontal", "Lazo horizontal central", "chk", True),
        ("cuadro", "Cuadro de despiece", "chk", True),
        ("d_barra", "Ø barras (mm)", "combo", DIAM_BARRAS, 18),
        ("d_estribo", "Ø estribo (mm)", "combo", [8, 10, 12], 8),
        ("e_estribo", "Espaciamiento e (cm)", "float", 5, 30, 15, 1, 1, ""),
        ("elevacion", "Vista de elevación", "chk", True),
        ("ancho_zap", "Ancho zapata (cm)", "float", 40, 500, 130, 1, 10, ""),
        ("alto_zap", "Alto zapata (cm)", "float", 20, 120, 30, 1, 5, ""),
        ("traslape", "Traslape arranque (cm)", "float", 20, 200, 45, 1, 5, ""),
        ("gancho_arranque", "Pata de arranque (mm)", "float", 50, 600, 90, 0, 5, ""),
        ("largo_barra", "Largo barra B1 (m)", "float", 0.5, 12, 3.2, 2, 0.1, " m"),
        ("escala", "Escala de acotado", "combo", ESCALAS, "1:25"),
    ]

    def on_change(self):
        mode = self.w["preset"].currentText()
        by_face = mode == "Por caras"
        for key in ("n_sup", "n_inf", "n_izq", "n_der"):
            self.w[key].setEnabled(by_face)
        self.w["n_barras"].setEnabled(mode == "Total anterior")
        enabled = self.w["lazos_interiores"].isChecked()
        for key in ("lazo_vertical", "lazo_horizontal"):
            self.w[key].setEnabled(enabled)
        if mode == "Referencia 20" and getattr(self, "_previous_mode", None) != mode:
            # Caso de referencia explícito: 550 x 400, 20Ø16, estribos Ø10.
            for key, value in {"b": 55, "h": 40, "r": 5, "d_barra": 16,
                               "d_estribo": 10, "e_estribo": 15,
                               "lazos_interiores": True, "lazo_vertical": True,
                               "lazo_horizontal": True, "elevacion": False,
                               "cuadro": False}.items():
                w = self.w[key]
                w.blockSignals(True)
                if hasattr(w, "setCurrentText"):
                    w.setCurrentText(str(value))
                elif hasattr(w, "setChecked"):
                    w.setChecked(value)
                else:
                    w.setValue(value)
                w.blockSignals(False)
            for key in ("lazo_vertical", "lazo_horizontal"):
                self.w[key].setEnabled(True)
        self._previous_mode = mode

    def set_params(self, p):
        # Activa primero el modo y carga después las dimensiones guardadas.
        p = dict(p)
        mode = p.pop("preset", "Total anterior")
        if mode == "Legacy":
            mode = "Total anterior"
        super().set_params({"preset": mode})
        super().set_params(p)


# ---------------------------------------------------------- armadura sección
def _bar_layout(p: dict, n: int) -> dict:
    """Devuelve cantidades por cara sin duplicar las cuatro esquinas.

    ``top`` y ``bottom`` cuentan los extremos de la cara; ``left`` y
    ``right`` cuentan únicamente barras intermedias. El preset de referencia
    es 7+7+3+3 = 20 barras, tal como se ve en la sección entregada.
    ``barras_por_cara`` permite pasar esas cuatro cantidades desde una
    integración externa sin cambiar la API histórica basada en n_barras.
    """
    explicit = p.get("barras_por_cara")
    if explicit is not None:
        try:
            vals = tuple(int(v) for v in explicit)
            if len(vals) != 4 or min(vals) < 0 or min(vals[:2]) < 2:
                raise ValueError
            return dict(top=vals[0], bottom=vals[1],
                        left=vals[2], right=vals[3])
        except (TypeError, ValueError):
            raise ValueError("barras_por_cara debe ser [top, bottom, left, right]")

    preset = str(p.get("preset", p.get("distribucion", ""))).strip().lower()
    if preset == "por caras":
        return _bar_layout({"barras_por_cara": [p["n_sup"], p["n_inf"],
                                               p["n_izq"], p["n_der"]]}, n)
    if preset in {"referencia 20", "referencia", "ejemplo", "ejemplo 20",
                  "ref20", "20"}:
        return {"top": 7, "bottom": 7, "left": 3, "right": 3}

    if n < 4 or n % 2:
        raise ValueError("La distribución anterior requiere un total par de al menos 4 barras")
    return {"top": n // 2, "bottom": n // 2, "left": 0, "right": 0}


def _perimeter_bars(x0: float, y0: float, layout: dict) -> list:
    """Genera los centros de barra del perímetro, una sola vez por esquina."""
    out = []

    def add(p):
        if not any(abs(p[0] - q[0]) < 1e-7 and abs(p[1] - q[1]) < 1e-7
                   for q in out):
            out.append(p)

    for count, y in ((layout["top"], y0), (layout["bottom"], -y0)):
        for i in range(max(2, count)):
            add((-x0 + 2 * x0 * i / (count - 1), y))
    for count, x in ((layout["left"], -x0), (layout["right"], x0)):
        for i in range(1, count + 1):
            add((x, -y0 + 2 * y0 * i / (count + 1)))
    return out


def _outer_stirrup(B: float, H: float, R: float, ds: float):
    """Recorrido del eje exterior del estribo y sus dimensiones de línea."""
    eje = R + ds / 2.0
    w, h = B - 2 * eje, H - 2 * eje
    pts = stirrup_pts(w, h, ds, 2.5 * ds)
    return ([(x - B / 2 + eje, y - H / 2 + eje) for x, y in pts], w, h)


def _interior_tie_paths(p: dict, B: float, H: float, R: float, ds: float,
                        layout: dict) -> list:
    """Lazos centrales que abrazan las barras intermedias de cada dirección."""
    preset = str(p.get("preset", p.get("distribucion", ""))).lower()
    reference = preset in {
        "referencia", "referencia 20", "ejemplo", "ejemplo 20", "ref20", "20"
    }
    enabled = bool(p.get("lazos_interiores", reference))
    if not enabled:
        return []
    eje = R + ds / 2.0
    cw, ch = B - 2 * eje, H - 2 * eje
    vertical = bool(p.get("lazo_vertical", True))
    horizontal = bool(p.get("lazo_horizontal", True))
    out = []
    db = float(p["d_barra"])
    pad = (ds + db) / 2
    bx, by = cw / 2 - pad, ch / 2 - pad

    def one(w, h, rotation=0):
        raw = stirrup_pts(w, h, ds, 2.5 * ds)
        path = [(x - w / 2, y - h / 2) for x, y in raw]
        if rotation == -90:
            path = [(y, -x) for x, y in path]
        elif rotation == 180:
            path = [(-x, -y) for x, y in path]
        return path

    if vertical:
        count = min(layout["top"], layout["bottom"])
        if count < 4:
            raise ValueError("El lazo vertical requiere al menos 4 barras en cada cara horizontal")
        span = 2 * bx * (count - 3) / (count - 1)
        iw = float(p.get("lazo_ancho", span + 2 * pad))
        if not 0 < iw < cw:
            raise ValueError("El ancho del lazo vertical debe quedar dentro del estribo exterior")
        out.append(one(ch, iw, rotation=-90))
    if horizontal:
        count = min(layout["left"], layout["right"])
        if count < 2:
            raise ValueError("El lazo horizontal requiere al menos 2 barras intermedias por lateral")
        span = 2 * by * (count - 1) / (count + 1)
        ih = float(p.get("lazo_alto_horizontal", span + 2 * pad))
        if not 0 < ih < ch:
            raise ValueError("El alto del lazo horizontal debe quedar dentro del estribo exterior")
        out.append(one(cw, ih, rotation=180))
    return out


# -------------------------------------------------------------- generador --
def build_pedestal(p: dict) -> ir.Drawing:
    d = ir.Drawing()
    f = p.get("_escala", 2.5)
    th = 5.0 * f
    B, H = p["b"] * 10.0, p["h"] * 10.0        # sección en mm
    R = p["r"] * 10.0                          # recubrimiento en mm
    db_d = float(p["d_barra"])
    ds = float(p["d_estribo"])
    n = int(p.get("n_barras", 8) or 0)

    # El eje de una barra queda a recubrimiento libre + diámetro del
    # estribo + medio diámetro de la barra. El estribo tiene su propio eje
    # (R + ds/2), no el recubrimiento libre R.
    o = R + ds + db_d / 2.0
    x0 = B / 2 - o
    y0 = H / 2 - o
    if min(x0, y0) <= db_d:
        raise ValueError("La sección no permite el recubrimiento y los diámetros ingresados")
    layout = _bar_layout(p, n)
    bars = _perimeter_bars(x0, y0, layout)
    if any(math.dist(a, b) < db_d + 1e-6
           for i, a in enumerate(bars) for b in bars[i + 1:]):
        raise ValueError("Las barras longitudinales se tocan o superponen; revise cantidades y sección")
    arranque_xs = sorted({x for x, y in bars})
    outer_stirrup = _outer_stirrup(B, H, R, ds)
    inner_paths = _interior_tie_paths(p, B, H, R, ds, layout)

    # ------------------------- SECCIÓN -------------------------
    sec = ir.rect(-B / 2, -H / 2, B / 2, H / 2)
    d.ents.append(sec)
    # La sección de referencia prioriza la lectura de armadura; el hachurado
    # denso detrás de barras y ganchos se omite deliberadamente aquí.
    # estribo
    st_pts = outer_stirrup[0]
    bar, _ = poly_bar(st_pts, ds, 2.5 * ds)
    d.ents.extend(bar)
    for path in inner_paths:
        tbar, _ = poly_bar(path, ds, 2.5 * ds)
        d.ents.extend(tbar)
    # barras longitudinales
    for x, y in bars:
        d.ents.append(Circle((x, y), db_d / 2, ir.L_ACERO, filled=True))
    # Cuatro cadenas corresponden a centros reales, con totales exteriores.
    dbb = DimBuilder(d.ents, th)
    for y, sign in ((y0, 1), (-y0, -1)):
        xs = sorted(x for x, by in bars if abs(by - y) < 1e-6)
        face = sign * H / 2
        dbb.h_chain(xs, y, face + sign * 3 * th)
    for x, sign in ((-x0, -1), (x0, 1)):
        ys = sorted(y for bx, y in bars if abs(bx - x) < 1e-6)
        dbb.v_chain(ys, x, sign * (B / 2 + 3 * th))
    dbb.h_total(-B / 2, B / 2, H / 2, H / 2 + 6 * th)
    dbb.v_total(-H / 2, H / 2, B / 2, B / 2 + 6 * th)
    d.ents.append(Text((0, H / 2 + 10 * th),
                        f"SECCIÓN — {len(bars)}Ø{db_d:g}", 1.3 * th,
                        layer=ir.L_TXT, va="b"))
    # Las flechas terminan en las familias que describen, nunca en un eje vacío.
    d.ents.append(ir.Leader((-x0, y0), (-B / 2 - 10 * th, H / 2 + 5 * th),
                            f"B1: {len(bars)}Ø{db_d:g} TOTAL", th, shelf=th, side=-1))
    d.ents.append(ir.Leader((B / 2 - R - ds / 2, -H / 4),
                            (B / 2 + 10 * th, -H / 2 - 4 * th),
                            f"B3: Ø{ds:g}@{p['e_estribo'] * 10:g} E", th, shelf=th))
    for i, path in enumerate(inner_paths, start=4):
        side = -1 if i == 4 else 1
        # Lazo vertical: punto en su cara izquierda; horizontal: cara superior.
        if i == 4 and p.get("lazo_vertical", True):
            tip = (min(x for x, y in path), 0)
            elbow = (-B / 2 - 10 * th, -H / 2 - 4 * th)
        else:
            tip = (0, max(y for x, y in path))
            elbow = (B / 2 + 10 * th, H / 2 + 5 * th)
        d.ents.append(ir.Leader(tip, elbow, f"B{i}: Ø{ds:g}@{p['e_estribo'] * 10:g} E",
                                th, shelf=th, side=side))

    # ------------------------- ELEVACIÓN (a la derecha) -------------------
    Wf = p["ancho_zap"] * 10.0
    section_bounds = drawing_bounds(d)
    ex = section_bounds[2] + 16 * th + Wf / 2
    y_min = section_bounds[1]
    if p["elevacion"]:
        y_min = min(y_min, _elevacion_ped(d, dbb, p, ex, B, H, R, db_d, ds,
                                          arranque_xs, len(bars), f, th))

    # ---------------------- CUADRO DESPIECE ----------------------
    filas, total = _despiece(p, B, H, R, db_d, ds, layout, bars,
                             outer_stirrup, inner_paths, f)
    y_tab = y_min - 30 * f
    ancho_tab = sum(w for w in [20, 34, 16, 14, 24, 24, 26]) * f
    if p.get("cuadro", True):
        tb = cuadro_despiece((section_bounds[0], y_tab), f, filas, total_kg=total)
        d.ents.append(tb)
        y_min = drawing_bounds(d)[1] - 3 * th

    # --------------------------- TÍTULO ---------------------------
    notas = [
        f"CONCRETO f'c = 21 MPa  |  ACERO fy = 420 MPa",
        f"RECUBRIMIENTO r = {ir.fmt_cm(R)} cm  |  "
        f"ESTRIBOS Ø{ds:g} c/{ir.fmt_cm(p['e_estribo'] * 10)} cm",
    ]
    for i, s in enumerate(notas):
        d.ents.append(Text((section_bounds[0], y_min - (i + 1) * 3 * th), s,
                           2.5 * f, 0, ir.L_TXT, "l", "m"))
    d.ents.append(Text((0, y_min - (len(notas) + 2) * 3 * th),
                       f"PEDESTAL {ir.fmt_m(B)}x{ir.fmt_m(H)} m  -  "
                       f"ESC {p['escala']}", 4.5 * f, 0, ir.L_TXT, "c", "m"))
    return d


# -------------------------------------------------------------- elevación --
def _stirrup_levels(p, R, ds):
    start, end = R + ds / 2, p["H"] * 10.0 - R - ds / 2
    spacing = float(p["e_estribo"]) * 10
    if spacing <= 0 or end < start:
        raise ValueError("Altura o espaciamiento de estribos inválido")
    levels = [start + i * spacing for i in range(int((end - start) / spacing) + 1)]
    if end - levels[-1] > 1e-6:
        levels.append(end)
    return levels


def _starter_path(p):
    leg = float(p.get("gancho_arranque", 90))
    return [(leg, -p["alto_zap"] * 10 + 60),
            (0, -p["alto_zap"] * 10 + 60), (0, p["traslape"] * 10)]


def _elevacion_ped(d, dbb, p, ex, B, H, R, db_d, ds, xs, n_long, f, th):
    e = d.ents
    Hm = p["H"] * 10.0
    Wf = p["ancho_zap"] * 10.0
    hf = p["alto_zap"] * 10.0
    lap = p["traslape"] * 10.0

    z_rect = ir.rect(ex - Wf / 2, -hf, ex + Wf / 2, 0)
    e.append(z_rect)
    e.extend(hatch_poly(z_rect.pts, 9 * f))
    # Una elevación muy alta se representa con una rotura convencional para
    # que la sección y el cuadro sigan siendo legibles. La cota conserva Hm.
    shortened = Hm > 1100.0
    if shortened:
        seg = min(400.0, Hm * 0.25)
        gap = 70.0 * f
        y_upper = seg + gap
        Hdraw = y_upper + seg
        e.append(ir.rect(ex - B / 2, 0, ex + B / 2, seg))
        e.append(ir.rect(ex - B / 2, y_upper, ex + B / 2, Hdraw))
        for yb in (seg, y_upper):
            e.extend(break_line((ex - B / 2 - 5 * f, yb),
                                (ex + B / 2 + 5 * f, yb), 5 * f))
    else:
        seg, y_upper, Hdraw = Hm, Hm, Hm
        e.append(ir.rect(ex - B / 2, 0, ex + B / 2, Hdraw))
    e.extend(break_line((ex - B / 2 - 6 * f, Hdraw),
                        (ex + B / 2 + 6 * f, Hdraw), 5 * f))
    # arranques con gancho en zapata (alternando lado) + barras principales
    for i, xb in enumerate(xs):
        x = ex + xb
        sgn = -1 if i % 2 else 1
        hook_y = -hf + 60
        arr, _ = poly_bar([(x + sgn * px, py) for px, py in _starter_path(p)], db_d, 3 * db_d,
                          width=max(1.2, db_d * 0.14))
        e.extend(arr)
        if shortened:
            e.append(Line((x, 0), (x, seg), ir.L_ACERO,
                          width=max(1.2, db_d * 0.14)))
            e.append(Line((x, y_upper), (x, Hdraw - R), ir.L_ACERO,
                          width=max(1.2, db_d * 0.14)))
        else:
            e.append(Line((x, 0), (x, Hdraw - R), ir.L_ACERO,
                          width=max(1.2, db_d * 0.14)))
    # estribos en vista: extremos representativos cuando existe rotura
    e_st = p["e_estribo"] * 10.0
    niv = _stirrup_levels(p, R, ds)
    if shortened:
        lower = [y for y in niv if y < seg - 10]
        upper = [y_upper + (y - (Hm - seg)) for y in niv
                 if y > Hm - seg + 10]
        niv = lower + upper
    elif len(niv) > 12:
        niv = niv[:6] + niv[-6:]
    for y in niv:
        e.append(Line((ex - B / 2 + R + ds / 2, y),
                       (ex + B / 2 - R - ds / 2, y), ir.L_ACERO))
    # ejes y nivel
    e.append(line_x(ex, -hf - 30 * f, Hdraw + 30 * f))
    e.extend(level_symbol((ex - Wf / 2 - 25 * f, 0), th, "N.P."))
    e.append(Text((ex, Hdraw + 72 * f), "ELEVACIÓN", 3.5 * f,
                  layer=ir.L_TXT, ha="c", va="m"))

    # acotado
    dbb.v_total(0, Hdraw, ex + B / 2, ex + B / 2 + 40 * f,
                txt=ir.fmt_mm(Hm), ext_from=ex + B / 2)
    dbb.v_total(0, lap, ex - B / 2, ex - B / 2 - 40 * f,
                texts=[f"TR = {ir.fmt_m(lap)}"], ext_from=ex - B / 2)
    yb = -hf - 40 * f
    dbb.h_chain([ex - Wf / 2, ex + Wf / 2], -hf, yb, ext_from=-hf,
                texts=[f"{ir.fmt_m(Wf)}"])
    dbb.h_total(ex - B / 2, ex + B / 2, 0, -hf - 75 * f, ext_from=-hf)
    e.append(ir.Leader((ex + xs[-1], 60),
                       (ex + Wf / 2 + 4 * th, 60 + 8 * th),
                       f"ARRANQUES {n_long}Ø{db_d:g}", th, shelf=20 * f,
                       side=1))
    return -hf - 120 * f


# ------------------------------------------------------------- despiece --
def _despiece(p, B, H, R, db_d, ds, layout, bars, outer_stirrup,
              inner_paths, f):
    filas = []
    total = 0.0
    Hm = p["H"] * 10.0
    qty_long = len(bars)

    # B1 barras principales (rectas)
    L1 = p["largo_barra"] * 1000.0
    celdas, sk, dev = fila_barra("B1", "recta", [(0, 0), (0, 1)], db_d,
                                 2 * db_d, qty_long)
    celdas[4] = f"{p['largo_barra']:.2f}"
    pu = peso_barra(db_d)
    celdas[6] = f"{pu * qty_long * p['largo_barra']:.1f}"
    total += pu * qty_long * p["largo_barra"]
    filas.append((celdas, sk))

    # B2 arranques (L con gancho en zapata)
    hf = p["alto_zap"] * 10.0
    lap = p["traslape"] * 10.0
    celdas, sk, dev = fila_barra("B2", "L", _starter_path(p),
                                 db_d, 3 * db_d, qty_long)
    total += peso_barra(db_d) * qty_long * dev / 1000.0
    filas.append((celdas, sk))

    # B3 estribos
    st_pts = outer_stirrup[0]
    # El boceto de tabla conserva coordenadas locales de la sección.
    eje = R + ds / 2.0
    st_pts = [(x + B / 2 - eje, y + H / 2 - eje) for x, y in st_pts]
    q3 = len(_stirrup_levels(p, R, ds))
    celdas, sk, dev = fila_barra("B3", "estribo", st_pts, ds, 2.5 * ds, q3)
    total += peso_barra(ds) * q3 * dev / 1000.0
    filas.append((celdas, sk))

    # B4... lazos interiores: cada familia usa exactamente el recorrido que
    # se dibuja en sección y su cantidad longitudinal de estribos.
    for i, path in enumerate(inner_paths, start=4):
        local = [(x + B / 2, y + H / 2) for x, y in path]
        celdas, sk, dev = fila_barra(f"B{i}", "lazo", local, ds,
                                     2.5 * ds, q3)
        total += peso_barra(ds) * q3 * dev / 1000.0
        filas.append((celdas, sk))
    return filas, total
