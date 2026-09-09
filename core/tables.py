# -*- coding: utf-8 -*-
"""
core.tables — Cuadros de despiece de acero y tablas de pernos.
"""

from . import ir
from .geom import poly_bar

COLS = ["MARCA", "FORMA", "Ø\n(mm)", "Nº", "LARGO\n(m)", "P.U.\n(kg/m)", "PESO\n(kg)"]
COL_W = [20, 34, 16, 14, 24, 24, 26]          # anchos base (x factor de escala)


def peso_barra(d_mm: float) -> float:
    """Peso unitario teórico de barra corrugada en kg/m: d²/162."""
    return d_mm * d_mm / 162.0


def fila_barra(marca: str, shape_code: str, shape_pts, d: float, R_in: float,
               qty: int, layer=ir.L_ACERO):
    """Genera la fila del cuadro + entidades del boceto de forma.
    Devuelve (celdas_texto, sketch_ents_relativas, largo_mm)."""
    ents, dev = poly_bar(shape_pts, d, R_in, layer=layer)
    pu = peso_barra(d)
    celdas = [marca, "", f"Ø{d}", str(qty), f"{dev / 1000.0:.2f}",
              f"{pu:.2f}", f"{pu * qty * dev / 1000.0:.2f}"]
    # normaliza boceto alrededor de su centro, con origen (0,0)
    xs = [p[0] for e in ents for p in _pts_of(e)]
    ys = [p[1] for e in ents for p in _pts_of(e)]
    if xs:
        cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
        sketch = _translate_ents(ents, -cx, -cy)
    else:
        sketch = []
    return celdas, sketch, dev


def _pts_of(e):
    if hasattr(e, "p1"):
        return [e.p1, e.p2]
    if hasattr(e, "pts"):
        return e.pts
    if hasattr(e, "c"):
        return [e.c]
    return []


def _translate_ents(ents, dx, dy):
    out = []
    for e in ents:
        import copy
        e2 = copy.copy(e)
        if hasattr(e, "p1"):
            e2.p1 = (e.p1[0] + dx, e.p1[1] + dy)
            e2.p2 = (e.p2[0] + dx, e.p2[1] + dy)
        elif hasattr(e, "pts"):
            e2.pts = [(p[0] + dx, p[1] + dy) for p in e.pts]
        elif hasattr(e, "c"):
            e2.c = (e.c[0] + dx, e.c[1] + dy)
        out.append(e2)
    return out


def cuadro_despiece(pos, f: float, filas, total_kg: float = None,
                    title="CUADRO DE DESPIECE DE BARRAS") -> ir.Table:
    """filas: lista de (celdas, sketch) ya calculadas."""
    col_w = [w * f for w in COL_W]
    rows = []
    sketches = {}
    for i, fila in enumerate(filas):
        celdas, sketch = fila
        rows.append(celdas)
        if sketch:
            sketches[(i, 1)] = sketch
    t = ir.Table(pos=pos, col_w=col_w, row_h=15.0 * f, header=COLS,
                 rows=rows, title=title, h_row=5.0 * f, sketches=sketches)
    if total_kg is not None:
        blank = [""] * (len(COLS) - 1)
        rows.append(blank + [f"Σ {total_kg:.1f}"])
    return t


def tabla_pernos(pos, f: float, datos, title="CUADRO DE PERNOS DE ANCLAJE"):
    """datos: lista de listas de texto. Encabezados fijos."""
    headers = ["Nº", "Ø (mm)", "EMPOTR.\n(mm)", "PROY.\n(mm)", "MATERIAL",
               "TUERCA /\nARANDELA"]
    col_w = [w * f for w in [20, 24, 34, 30, 38, 56]]
    return ir.Table(pos=pos, col_w=col_w, row_h=15.0 * f, header=headers,
                    rows=datos, title=title, h_row=5.0 * f)


def tabla_perno_pg(pos, f: float, p: dict) -> ir.Table:
    """Tabla de fabricación vertical para el perno recto tipo PG."""
    r = float(p["Le"])
    proy = float(p["P"])
    rows = [
        ["DIÁMETRO DE PERNO", "d", f'{float(p["d_perno"]):g}'],
        ["TIPO DE HILO", "", str(p.get("tipo_hilo", "8UN"))],
        ["LARGO DE HILO", "h1", ir.fmt_mm(float(p.get("h1", 150)))],
        ["LARGO DE HILO", "h2", ir.fmt_mm(float(p.get("h2", 75)))],
        ["TAMAÑO GOLILLA", "W", ir.fmt_mm(float(p.get("W", 75)))],
        ["ESPESOR GOLILLA", "t", ir.fmt_mm(float(p.get("t_golilla", 20)))],
        ["", "b", ir.fmt_mm(float(p.get("b_golilla", 50)))],
        ["EMPOTRAMIENTO", "R", ir.fmt_mm(r)],
        ["PROYECCIÓN", "P", ir.fmt_mm(proy)],
        ["LARGO PERNO", "L", ir.fmt_mm(r + proy)],
        ["CANTIDAD", "", str(int(p.get("n", p.get("n_pernos", 1))))],
    ]
    return ir.Table(pos=pos, col_w=[58 * f, 13 * f, 22 * f],
                    row_h=10.0 * f, rows=rows, title='PERNO TIPO "PG"',
                    h_row=3.0 * f)
