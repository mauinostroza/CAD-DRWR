# -*- coding: utf-8 -*-
"""
generators.foundation_sap — Fundaciones: parte pura del módulo (sin COM ni Qt).

Recibe la geometría ya leída de SAP2000 (`params["_geom"]`, dict producido por
`sap_geom.FundacionGeom.to_dict`) y construye el dibujo de cada zapata: plantas
en su posición real y dos elevaciones (corte A-A y B-B) por zapata.

La lectura desde SAP2000 y el panel interactivo no se portan aquí.
"""

import math
from ..core import ir
from ..core.ir import Poly, Text
from ..core.geom import corte_poligono, level_symbol
from ..core.dims import DimBuilder
from ..core.bounds import drawing_bounds
from .data import ESCALAS, factor_escala

# panel interactivo: parámetros fijos en params()
SPEC = []

PARAMS_DEFAULT = {"escala": "1:50", "espesor_default": 0.0, "fundacion": "", "_geom": None}

GAP_ELEV = 200.0       # mm entre las 2 elevaciones (ejeX/ejeY) de una zapata
GAP_FILA_ZAPATA = 300.0    # mm entre el par de elevaciones de zapatas vecinas
GAP_FILA = 400.0       # mm entre la fila de plantas y la fila de elevaciones
ALTO_ARRANQUE_COL = 300.0   # mm, tramo de columna dibujado sobre la zapata


# ------------------------------------------------------------ geometría --

def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def _dibujar_pedestal(d, pos, pedestal, f, layer=ir.L_ACERO):
    cx, cy = pos
    largo, ancho = pedestal["largo"], pedestal["ancho"]
    hx, hy = (largo / 2.0, ancho / 2.0) if pedestal["largo_en_x"] \
        else (ancho / 2.0, largo / 2.0)
    d.ents.append(ir.rect(cx - hx, cy - hy, cx + hx, cy + hy, layer))
    etiqueta = pedestal["frame"]
    if pedestal["aproximado"]:
        etiqueta += " (aprox.)"
    d.ents.append(Text((cx, cy), etiqueta, 2.0 * f, 0, ir.L_TXT, "c", "m"))


def _posicion_corte(zapata, eje):
    """Posición del corte que representa la fundación.

    Se privilegia el eje de los pedestales; sin pedestal se usa el centro
    geométrico del contorno.  La misma referencia se emplea en planta y en
    la elevación, para que las marcas de corte sean trazables.
    """
    x0, x1, y0, y1 = _bbox(zapata["contorno"])
    idx = 0 if eje == "x" else 1
    candidates = [p["centro"][idx] for p in zapata["pedestales"]]
    candidates.append((x0 + x1) / 2.0 if eje == "x" else (y0 + y1) / 2.0)
    # El centro de un shell válido evita vacíos en contornos cóncavos.
    candidates.extend(sum(pt[idx] for pt in a["pts"]) / len(a["pts"])
                      for a in zapata["areas"] if a["pts"])
    for value in candidates:
        if any(corte_poligono([(pt[0], pt[1]) for pt in a["pts"]], eje, value)
               for a in zapata["areas"]):
            return value
    raise ValueError("No se encontró un corte que atraviese los shells")


def _dibujar_marcas_corte(d, zapata, f):
    """Añade en planta las referencias A-A y B-B de las dos elevaciones."""
    contorno = [(p[0], p[1]) for p in zapata["contorno"]]
    x0, x1, y0, y1 = _bbox(contorno)
    margen = 16.0 * f
    etiqueta_off = 8.0 * f

    # A-A: plano x = constante (elevación transversal en Y).
    x = _posicion_corte(zapata, "x")
    d.ents.append(ir.Line((x, y0 - margen), (x, y1 + margen), ir.L_EJE))
    for yy in (y0 - margen, y1 + margen):
        d.ents.append(ir.Filled([(x + 5*f, yy), (x, yy + 2*f),
                                (x, yy - 2*f)], ir.L_EJE))
    d.ents.append(Text((x, y1 + margen + etiqueta_off), "A", 2.2 * f,
                       0, ir.L_EJE, "c", "b"))
    d.ents.append(Text((x, y0 - margen - etiqueta_off), "A", 2.2 * f,
                       0, ir.L_EJE, "c", "t"))

    # B-B: plano y = constante (elevación transversal en X).
    y = _posicion_corte(zapata, "y")
    d.ents.append(ir.Line((x0 - margen, y), (x1 + margen, y), ir.L_EJE))
    for xx in (x0 - margen, x1 + margen):
        d.ents.append(ir.Filled([(xx, y + 5*f), (xx - 2*f, y),
                                (xx + 2*f, y)], ir.L_EJE))
    d.ents.append(Text((x0 - margen - etiqueta_off, y), "B", 2.2 * f,
                       0, ir.L_EJE, "r", "m"))
    d.ents.append(Text((x1 + margen + etiqueta_off, y), "B", 2.2 * f,
                       0, ir.L_EJE, "l", "m"))


def _dibujar_zapata_planta(d, db, zapata, f, th):
    """Dibuja la zapata en su posición real (coordenadas globales del
    modelo, sin recentrar ni trasladar). Devuelve el y mínimo alcanzado
    por su dibujo (contorno + acotado + rótulo), para saber dónde
    empieza, lejos de todas las plantas, la fila de elevaciones."""
    contorno = [(p[0], p[1]) for p in zapata["contorno"]]
    d.ents.append(Poly(contorno, closed=True, layer=ir.L_CONC))

    for pedestal in zapata["pedestales"]:
        _dibujar_pedestal(d, pedestal["centro"], pedestal, f)
    _dibujar_marcas_corte(d, zapata, f)

    xs_l = sorted(set(round(p[0], 1) for p in contorno))
    ys_l = sorted(set(round(p[1], 1) for p in contorno))
    lx0, lx1 = xs_l[0], xs_l[-1]
    ly0, ly1 = ys_l[0], ys_l[-1]
    cx = (lx0 + lx1) / 2.0

    # El título queda al lado opuesto del acotado para que la planta pueda
    # leerse como una vista independiente, incluso en grupos con zapatas
    # cercanas entre sí.
    d.ents.append(Text((cx, ly1 + 42 * f),
                       f"{zapata['nombre']} — PLANTA", 3.0 * f,
                       0, ir.L_TXT, "c", "b"))

    y_dim1 = ly0 - 30 * f
    if len(xs_l) > 2:
        db.h_chain(xs_l, ly0, y_dim1, ext_from=ly0)
        y_dim1 -= 30 * f
    db.h_total(lx0, lx1, ly0, y_dim1, ext_from=ly0)
    x_dim1 = lx1 + 30 * f
    if len(ys_l) > 2:
        db.v_chain(ys_l, lx1, x_dim1, ext_from=lx1)
        x_dim1 += 30 * f
    db.v_total(ly0, ly1, lx1, x_dim1, ext_from=lx1)

    y_label = y_dim1 - 60 * f
    d.ents.append(Text((cx, y_label), zapata["nombre"], 3.5 * f,
                       0, ir.L_TXT, "c", "m"))
    return y_label - 15 * f


def _dibujar_zapata_elevacion(d, db, zapata, eje, offset_x, y0_off, f, th,
                              espesor_default):
    """Dibuja UNA elevación (corte real perpendicular a `eje`) de la
    zapata, aislada de todo lo demás (solo usa los shells propios de esa
    zapata). Devuelve (x_min_usado, x_max_usado, esp_max): el rango real
    de X ocupado por TODO lo dibujado (cortes, arranques de columna,
    cota y rótulo), para que el llamador pueda ubicar la siguiente
    elevación sin traslape."""
    x0, x1, y0, y1 = _bbox(zapata["contorno"])
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    marca = "A-A" if eje == "x" else "B-B"
    titulo = (f"{zapata['nombre']} — CORTE {marca} "
              f"(EJE {'X' if eje == 'x' else 'Y'})")
    pos_corte = _posicion_corte(zapata, eje)

    tramos = []   # (a, b, espesor)
    for a in zapata["areas"]:
        pts_xy = [(p[0], p[1]) for p in a["pts"]]
        esp = a.get("espesor") or espesor_default
        for t0, t1 in corte_poligono(pts_xy, eje, pos_corte):
            tramos.append((t0, t1, esp if esp else espesor_default))

    centro_transv = cy if eje == "x" else cx

    def loc_t(t):
        return offset_x + (t - centro_transv)

    if not tramos:
        d.ents.append(Text((offset_x, y0_off),
                           f"{titulo}: EL CORTE AUTOMÁTICO NO ATRAVIESA "
                           "NINGÚN SHELL", 2.5 * f, 0, ir.L_TXT, "c", "m"))
        ancho_txt = 0.6 * 2.5 * f * len(titulo) / 2.0
        return offset_x - ancho_txt, offset_x + ancho_txt, 0.0

    esp_max = max(t[2] for t in tramos)
    for t0, t1, esp in tramos:
        d.ents.append(ir.rect(loc_t(t0), y0_off - esp, loc_t(t1), y0_off,
                              ir.L_CONC))

    t_min = min(t[0] for t in tramos)
    t_max = max(t[1] for t in tramos)
    x_min_usado = loc_t(t_min) - 25 * f    # símbolo de nivel a la izquierda
    x_max_usado = loc_t(t_max)

    zs = [pt[2] for a in zapata["areas"] for pt in a["pts"] if len(pt) > 2]
    datum = f"Z MODELO = {zs[0]:g} mm" if zs else "NIVEL LOCAL 0 (REFERENCIA)"
    d.ents.extend(level_symbol((loc_t(t_min) - 25 * f, y0_off), th, datum))

    alto_col = ALTO_ARRANQUE_COL
    for pedestal in zapata["pedestales"]:
        idx = 0 if eje == "x" else 1
        normal_width = (pedestal["largo"] if
                        ((eje == "x") == pedestal["largo_en_x"])
                        else pedestal["ancho"])
        if abs(pedestal["centro"][idx] - pos_corte) > normal_width / 2:
            continue
        centro_ped = pedestal["centro"][1] if eje == "x" else \
            pedestal["centro"][0]
        ancho_ped = pedestal["ancho"] if (
            (eje == "x") == pedestal["largo_en_x"]) else pedestal["largo"]
        xa = loc_t(centro_ped) - ancho_ped / 2.0
        xb = loc_t(centro_ped) + ancho_ped / 2.0
        d.ents.append(ir.rect(xa, y0_off, xb, y0_off + alto_col,
                              ir.L_ACERO))
        d.ents.append(Text(((xa + xb)/2, y0_off + alto_col + 4*f),
                           "SECCIÓN APROXIMADA — CONTINUACIÓN ESQUEMÁTICA"
                           if pedestal.get("aproximado", False) else
                           "CONTINUACIÓN ESQUEMÁTICA", 2*f, layer=ir.L_TXT))
        x_min_usado = min(x_min_usado, xa)
        x_max_usado = max(x_max_usado, xb)

    y_dim2 = y0_off - esp_max - 30 * f
    db.h_total(loc_t(t_min), loc_t(t_max), y0_off - esp_max, y_dim2,
              ext_from=y0_off - esp_max)
    x_cota_v = loc_t(t_max) + 30 * f
    db.v_total(y0_off - esp_max, y0_off, loc_t(t_max), x_cota_v,
              ext_from=loc_t(t_max))
    x_max_usado = max(x_max_usado, x_cota_v + 15 * f)

    nombres_sec = ", ".join(sorted({a["seccion"] for a in zapata["areas"]
                                    if a["seccion"]}))
    rotulo = titulo + (f"  -  SEC. {nombres_sec}" if nombres_sec else "")
    d.ents.append(Text(
        (offset_x, y0_off - esp_max - 60 * f), rotulo, 2.5 * f,
        0, ir.L_TXT, "c", "m"))
    ancho_rotulo = 0.6 * 2.5 * f * len(rotulo) / 2.0
    x_min_usado = min(x_min_usado, offset_x - ancho_rotulo)
    x_max_usado = max(x_max_usado, offset_x + ancho_rotulo)

    return x_min_usado, x_max_usado, esp_max


# -------------------------------------------------------------- generador --
def build_foundation(p: dict) -> ir.Drawing:
    geom_d = p.get("_geom")
    zapatas = geom_d.get("zapatas") if geom_d else None
    if not zapatas:
        raise ValueError("Conecte a SAP2000 y elija un grupo con shells "
                         "asignados.")

    f = p.get("_escala", 5.0)
    th = 3.0 * f
    d = ir.Drawing()
    db = DimBuilder(d.ents, th)
    espesor_default = p.get("espesor_default", 0.0)

    # ===================== PLANTAS (posición real) =====================
    # Cada zapata se dibuja en sus coordenadas reales del modelo, sin
    # recolocarla: conservan su posición relativa unas con otras.
    y_min_plantas = 0.0
    for zapata in zapatas:
        coordinates = [v for a in zapata["areas"] for pt in a["pts"] for v in pt]
        coordinates.extend(v for pt in zapata["contorno"] for v in pt)
        if not all(math.isfinite(float(v)) for v in coordinates):
            raise ValueError(f"{zapata['nombre']}: coordenadas no finitas")
        zs = [pt[2] for a in zapata["areas"] for pt in a["pts"] if len(pt) > 2]
        if zs and max(zs) - min(zs) > 1e-6:
            raise ValueError(f"{zapata['nombre']}: shells con diferentes niveles Z; "
                             "no se puede emitir un corte horizontal simplificado")
        if any(not math.isfinite(float(a.get("espesor") or espesor_default)) or
               (a.get("espesor") or espesor_default) <= 0 for a in zapata["areas"]):
            raise ValueError(f"{zapata['nombre']}: espesor desconocido; ingrese un valor")
        y_bottom = _dibujar_zapata_planta(d, db, zapata, f, th)
        y_min_plantas = min(y_min_plantas, y_bottom)

    # ========================== ELEVACIONES ===========================
    # Fila aparte, lejos de todas las plantas. Dos elevaciones por zapata
    # (corte eje X y corte eje Y, "sus dos lados"), cada una aislada del
    # resto y sin traslape entre bloques (el ancho de avance del cursor
    # es el rango real de X que ocupó cada elevación, no una estimación).
    y_fila_elev = y_min_plantas - GAP_FILA * f
    cursor_x = 0.0
    for zapata in zapatas:
        for eje in ("x", "y"):
            inicio = len(d.ents)
            x_min, x_max, esp = _dibujar_zapata_elevacion(
                d, db, zapata, eje, cursor_x, y_fila_elev, f, th,
                espesor_default)
            actual = drawing_bounds(ir.Drawing(ents=d.ents[inicio:]))
            if actual is not None:
                x_min, x_max = actual[0], actual[2]
            # El dibujo queda centrado en cursor_x (no alineado a su
            # borde izquierdo) — se traslada lo recién agregado para que
            # su borde izquierdo real (x_min) coincida con cursor_x,
            # garantizando que no invada el bloque anterior.
            shift = cursor_x - x_min
            if abs(shift) > 1e-6:
                bloque = ir.translate(ir.Drawing(ents=d.ents[inicio:]),
                                      shift, 0.0)
                d.ents[inicio:] = bloque.ents
                x_max += shift
            cursor_x = x_max + GAP_ELEV * f
        cursor_x += GAP_FILA_ZAPATA * f

    return d
