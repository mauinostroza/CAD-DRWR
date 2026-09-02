# -*- coding: utf-8 -*-
"""
cad.dxf_out — Exportación de la IR a DXF R2010 (AutoCAD / ZWCAD).

- Capas normalizadas con colores y grosores de línea.
- Cotas asociativas nativas (DIMENSION) con estilo paramétrico.
- Texto en estilo SHX estándar (txt.shx) disponible en AutoCAD y ZWCAD.
- Escala de acotado: las alturas de texto/flechas ya vienen escaladas en la IR.
"""

import ezdxf
from ezdxf.enums import TextEntityAlignment

from core import ir
from core.ir import (Line, Circle, Arc, Poly, Filled, Text, Dim, Leader,
                     Table, Drawing)

_AL = {"l": 0, "c": 1, "r": 2}
_VA = {"b": 1, "m": 2, "t": 3}

# grosores de capa en centésimas de mm
_LW = {ir.L_EJE: 13, ir.L_ACOT: 18, ir.L_TXT: 18, ir.L_CONC: 35,
       ir.L_ACERO: 50, ir.L_PERF: 25, ir.L_SOLD: 18, ir.L_HACH: 9,
       ir.L_TABLA: 18, ir.L_OCULTO: 18}


def _align(ha: str, va: str):
    h = _AL[ha]
    v = _VA[va]
    return {
        (1, 2): TextEntityAlignment.MIDDLE_CENTER,
        (0, 1): TextEntityAlignment.BOTTOM_LEFT,
        (1, 1): TextEntityAlignment.BOTTOM_CENTER,
        (2, 1): TextEntityAlignment.BOTTOM_RIGHT,
        (0, 2): TextEntityAlignment.MIDDLE_LEFT,
        (2, 2): TextEntityAlignment.MIDDLE_RIGHT,
        (0, 3): TextEntityAlignment.TOP_LEFT,
        (1, 3): TextEntityAlignment.TOP_CENTER,
        (2, 3): TextEntityAlignment.TOP_RIGHT,
    }.get((h, v), TextEntityAlignment.MIDDLE_CENTER)


def write_dxf(dwg: Drawing, path: str) -> None:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4          # milímetros
    doc.header["$LWDISPLAY"] = 1
    doc.header["$LTSCALE"] = _infer_ltscale(dwg)
    msp = doc.modelspace()

    # capas
    for name, aci in ir.LAYER_COLORS.items():
        doc.layers.add(name, color=aci, lineweight=_LW.get(name, 25))
    doc.layers.get(ir.L_EJE).dxf.linetype = "CENTER"
    doc.layers.get(ir.L_OCULTO).dxf.linetype = "HIDDEN"

    # estilo de texto SHX estándar
    if "ING" not in doc.styles:
        doc.styles.add("ING", font="txt.shx")

    # estilo de cota
    th = _infer_th(dwg)
    if "ING" not in doc.dimstyles:
        doc.dimstyles.add("ING", dxfattribs={
            "dimtxt": th, "dimasz": 0.85 * th, "dimexe": 0.45 * th,
            "dimexo": 0.30 * th, "dimgap": 0.35 * th, "dimtad": 1,
            "dimjust": 0, "dimdec": 0, "dimzin": 8, "dimlunit": 2,
            "dimtxsty": "ING", "dimscale": 1.0,
        })

    for e in dwg.ents:
        _write_ent(msp, e)

    doc.saveas(path)


def _infer_th(dwg: Drawing) -> float:
    for e in dwg.ents:
        if isinstance(e, Text) and e.h > 0:
            return e.h
    return 15.0


def _infer_ltscale(dwg: Drawing) -> float:
    th = _infer_th(dwg)
    return max(1.0, th / 3.0 * 2.0)


# ----------------------------------------------------------------- entidades --

def _write_ent(msp, e) -> None:
    if isinstance(e, Line):
        if e.width > 0:
            # línea con grosor (p. ej. barra/perno) -> LWPOLYLINE con ancho
            msp.add_lwpolyline([e.p1, e.p2], dxfattribs={
                "layer": e.layer, "const_width": e.width})
        else:
            msp.add_line(e.p1, e.p2, dxfattribs={"layer": e.layer})

    elif isinstance(e, Circle):
        if e.filled:
            _solid_circle(msp, e.c, e.r, e.layer)
        else:
            msp.add_circle(e.c, e.r, dxfattribs={"layer": e.layer})

    elif isinstance(e, Arc):
        a1, a2 = (e.a1, e.a2) if e.ccw else (e.a2, e.a1)
        msp.add_arc(e.c, e.r, a1, a2, dxfattribs={"layer": e.layer})

    elif isinstance(e, Poly):
        if e.width > 0:
            msp.add_lwpolyline(e.pts, close=e.closed,
                               dxfattribs={"layer": e.layer,
                                           "const_width": e.width})
        else:
            msp.add_lwpolyline(e.pts, close=e.closed,
                               dxfattribs={"layer": e.layer})

    elif isinstance(e, Filled):
        msp.add_solid([e.pts[0], e.pts[1], e.pts[2]] +
                      ([e.pts[3]] if len(e.pts) > 3 else []),
                      dxfattribs={"layer": e.layer})

    elif isinstance(e, Text):
        t = msp.add_text(e.s, dxfattribs={"style": "ING", "height": e.h,
                                          "rotation": e.rot, "layer": e.layer})
        t.set_placement(e.pos, align=_align(e.ha, e.va))

    elif isinstance(e, Dim):
        ang = 90.0 if e.vertical else 0.0
        dxf = {"layer": e.layer}
        dim = msp.add_linear_dim(base=e.base, p1=e.p1, p2=e.p2, angle=ang,
                                 text=e.txt if e.txt else "<>",
                                 dimstyle="ING", dxfattribs=dxf)
        dim.render()

    elif isinstance(e, Leader):
        msp.add_line(e.tip, e.elbow, dxfattribs={"layer": e.layer})
        if e.shelf > 0:
            p2 = (e.elbow[0] + e.side * e.shelf, e.elbow[1])
            msp.add_line(e.elbow, p2, dxfattribs={"layer": e.layer})
        else:
            p2 = e.elbow
        halign = "l" if e.side > 0 else "r"
        t = msp.add_text(e.s, dxfattribs={"style": "ING", "height": e.h,
                                          "layer": e.layer})
        t.set_placement(p2, align=_align(halign, "b"))

    elif isinstance(e, Table):
        _write_table(msp, e)

    else:
        raise TypeError(f"Entidad IR no soportada: {type(e)}")


def _solid_circle(msp, c, r, layer):
    h = msp.add_hatch(dxfattribs={"layer": layer})
    h.set_pattern_fill("SOLID")
    ep = h.paths.add_edge_path()
    ep.add_arc(center=c, radius=r, start_angle=0.0, end_angle=180.0, ccw=True)
    ep.add_arc(center=c, radius=r, start_angle=180.0, end_angle=360.0, ccw=True)


def _write_table(msp, tb: Table) -> None:
    x0, y0 = tb.pos
    th = tb.h_row
    n_rows = len(tb.rows) + (1 if tb.header else 0)
    total_w = sum(tb.col_w)
    h_total = n_rows * tb.row_h
    y_top = y0
    y_hdr = y_top - (tb.row_h if tb.header else 0)
    y_end = y_hdr - len(tb.rows) * tb.row_h

    # título centrado sobre la tabla
    if tb.title:
        msp.add_text(tb.title, dxfattribs={
            "style": "ING", "height": th * 1.15, "layer": ir.L_TABLA}
        ).set_placement((x0 + total_w / 2.0, y_top + 0.6 * th * 1.15),
                        align=TextEntityAlignment.BOTTOM_CENTER)

    # contorno
    msp.add_lwpolyline([(x0, y_top), (x0 + total_w, y_top),
                        (x0 + total_w, y_end), (x0, y_end)], close=True,
                       dxfattribs={"layer": ir.L_TABLA})
    # línea bajo encabezado
    if tb.header:
        msp.add_line((x0, y_hdr), (x0 + total_w, y_hdr),
                     dxfattribs={"layer": ir.L_TABLA})

    # líneas verticales
    x = x0
    for w in tb.col_w[:-1]:
        x += w
        msp.add_line((x, y_top), (x, y_end), dxfattribs={"layer": ir.L_TABLA})

    # textos de encabezado (posible doble línea con \n)
    if tb.header:
        x = x0
        for i, w in enumerate(tb.col_w):
            lines = tb.header[i].split("\n")
            n = len(lines)
            for k, s in enumerate(lines):
                yc = y_hdr - tb.row_h * (k + 1) / (n + 1)
                msp.add_text(s, dxfattribs={"style": "ING", "height": th,
                                            "layer": ir.L_TABLA}
                             ).set_placement((x + w / 2.0, yc),
                                             align=TextEntityAlignment.MIDDLE_CENTER)
            x += w

    # filas de datos
    for r, row in enumerate(tb.rows):
        ytr = y_hdr - r * tb.row_h           # techo de la fila
        if r > 0:
            msp.add_line((x0, ytr), (x0 + total_w, ytr),
                         dxfattribs={"layer": ir.L_TABLA})
        x = x0
        for c, w in enumerate(tb.col_w):
            if (r, c) in tb.sketches:
                scale = _sketch_scale(tb.sketches[(r, c)], w * 0.8,
                                      tb.row_h * 0.62)
                cx = x + w / 2.0
                cy = ytr - tb.row_h / 2.0
                for se in tb.sketches[(r, c)]:
                    _write_ent(msp, _place(se, cx, cy, scale))
            elif c < len(row) and row[c]:
                txt = row[c]
                ha = TextEntityAlignment.MIDDLE_CENTER
                if c == len(row) - 1 and txt.startswith("Σ"):
                    ha = TextEntityAlignment.MIDDLE_RIGHT
                msp.add_text(txt, dxfattribs={"style": "ING",
                                              "height": th,
                                              "layer": ir.L_TABLA}
                             ).set_placement((x + w / 2.0, ytr - tb.row_h / 2.0),
                                             align=ha)
            x += w


def _sketch_scale(ents, max_w: float, max_h: float) -> float:
    xs, ys = [], []
    for e in ents:
        for p in _ent_pts(e):
            xs.append(p[0])
            ys.append(p[1])
    if not xs:
        return 1.0
    w = max(max(xs) - min(xs), 1e-6)
    h = max(max(ys) - min(ys), 1e-6)
    return min(max_w / w, max_h / h, 50.0)


def _ent_pts(e):
    if isinstance(e, Line):
        return [e.p1, e.p2]
    if isinstance(e, Poly):
        return e.pts
    if isinstance(e, (Circle, Arc)):
        return [e.c]
    if isinstance(e, Filled):
        return e.pts
    return []


def _place(e, cx, cy, s):
    import copy
    e2 = copy.copy(e)
    if isinstance(e, Line):
        e2.p1 = (cx + e.p1[0] * s, cy + e.p1[1] * s)
        e2.p2 = (cx + e.p2[0] * s, cy + e.p2[1] * s)
    elif isinstance(e, Poly):
        e2.pts = [(cx + p[0] * s, cy + p[1] * s) for p in e.pts]
    elif isinstance(e, (Circle, Arc)):
        e2.c = (cx + e.c[0] * s, cy + e.c[1] * s)
        e2.r = e.r * s
    elif isinstance(e, Filled):
        e2.pts = [(cx + p[0] * s, cy + p[1] * s) for p in e.pts]
    return e2
