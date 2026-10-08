"""Geometría única de tablas y llamadas para preview, DXF y COM."""

import copy
import math

from . import ir
from .geom import arrow


def leader_parts(e):
    end = (e.elbow[0] + e.side * e.shelf, e.elbow[1])
    parts = [ir.Line(e.tip, e.elbow, e.layer)]
    if e.tip != e.elbow:
        angle = math.degrees(math.atan2(e.tip[1] - e.elbow[1],
                                        e.tip[0] - e.elbow[0]))
        parts.append(arrow(e.tip, angle, 0.85 * e.h, e.layer))
    if e.shelf:
        parts.append(ir.Line(e.elbow, end, e.layer))
    lines = str(e.s).splitlines() or [""]
    for i, line in enumerate(lines):
        parts.append(ir.Text((end[0], end[1] + (0.3 + (len(lines) - 1 - i) * 1.25) * e.h),
                             line, e.h, layer=e.layer,
                             ha="l" if e.side > 0 else "r", va="b"))
    return parts


def _sketch_points(e):
    if isinstance(e, ir.Line):
        return [e.p1, e.p2]
    if isinstance(e, (ir.Poly, ir.Filled)):
        return e.pts
    if isinstance(e, (ir.Arc, ir.Circle)):
        # Cota conservadora: incluye el radio, nunca sólo el centro.
        return [(e.c[0] - e.r, e.c[1] - e.r),
                (e.c[0] + e.r, e.c[1] + e.r)]
    return []


def fit_sketch(ents, cx, cy, width, height):
    pts = [p for e in ents for p in _sketch_points(e)]
    if not pts:
        return []
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    scale = min(width / max(x1 - x0, 1e-6),
                height / max(y1 - y0, 1e-6), 50.0)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2

    def point(p):
        return cx + (p[0] - mx) * scale, cy + (p[1] - my) * scale

    out = []
    for e in ents:
        e = copy.copy(e)
        if isinstance(e, ir.Line):
            e.p1, e.p2 = point(e.p1), point(e.p2)
            e.width *= scale
        elif isinstance(e, (ir.Poly, ir.Filled)):
            e.pts = [point(p) for p in e.pts]
            if isinstance(e, ir.Poly):
                e.width *= scale
        elif isinstance(e, (ir.Arc, ir.Circle)):
            e.c, e.r = point(e.c), e.r * scale
        out.append(e)
    return out


def table_parts(tb):
    x0, y0 = tb.pos
    th = tb.h_row or tb.row_h * 0.4
    width = sum(tb.col_w)
    has_title_row = bool(tb.title and tb.title_boxed)
    y_header = y0 - (tb.row_h if has_title_row else 0)
    y_data = y_header - (tb.row_h if tb.header else 0)
    bottom = y_data - len(tb.rows) * tb.row_h
    out = [ir.rect(x0, bottom, x0 + width, y0, ir.L_TABLA)]
    if tb.title:
        if has_title_row:
            out.append(ir.Line((x0, y_header), (x0 + width, y_header), ir.L_TABLA))
            pos, va = (x0 + width / 2, y0 - tb.row_h / 2), "m"
        else:
            pos, va = (x0 + width / 2, y0 + 0.69 * th), "b"
        out.append(ir.Text(pos, tb.title, th * 1.15, layer=ir.L_TABLA, va=va))
    x = x0
    for w in tb.col_w[:-1]:
        x += w
        out.append(ir.Line((x, y_header), (x, bottom), ir.L_TABLA))
    if tb.header:
        out.append(ir.Line((x0, y_data), (x0 + width, y_data), ir.L_TABLA))
        x = x0
        for col, w in enumerate(tb.col_w):
            lines = tb.header[col].split("\n") if col < len(tb.header) else []
            for i, text in enumerate(lines):
                y = y_header - tb.row_h * (i + 1) / (len(lines) + 1)
                out.append(ir.Text((x + w / 2, y), text, th, layer=ir.L_TABLA))
            x += w
    for row, values in enumerate(tb.rows):
        top = y_data - row * tb.row_h
        if row:
            out.append(ir.Line((x0, top), (x0 + width, top), ir.L_TABLA))
        x = x0
        for col, w in enumerate(tb.col_w):
            cy = top - tb.row_h / 2
            if (row, col) in tb.sketches:
                out.extend(fit_sketch(tb.sketches[(row, col)], x + w / 2, cy,
                                      w * 0.8, tb.row_h * 0.62))
            elif col < len(values) and values[col]:
                align = tb.col_align[col] if col < len(tb.col_align) else "c"
                tx = x + (0.5 * th if align == "l" else
                          w - 0.5 * th if align == "r" else w / 2)
                lines = str(values[col]).split("\n")
                for i, text in enumerate(lines):
                    ty = cy + ((len(lines) - 1) / 2 - i) * 1.25 * th
                    out.append(ir.Text((tx, ty), text, th, layer=ir.L_TABLA,
                                       ha=align))
            x += w
    return out


def expand_annotations(ents):
    for e in ents:
        if isinstance(e, ir.Table):
            yield from table_parts(e)
        elif isinstance(e, ir.Leader):
            yield from leader_parts(e)
        else:
            yield e
