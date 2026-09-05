# -*- coding: utf-8 -*-
"""Cajas envolventes de entidades IR, incluyendo anotaciones.

El visor usa estas cajas para no recortar textos, líderes ni títulos de tabla.
La estimación de texto es deliberadamente conservadora y no depende de Qt.
"""

import math

from .ir import (Arc, Circle, Dim, Filled, Leader, Line, Poly, Table, Text)
from .dims import dim_parts


def _text_size(text: str, height: float):
    lines = str(text).splitlines() or [""]
    return max(len(line) for line in lines) * height * 0.68, len(lines) * height * 1.25


def _text_bounds(e: Text):
    w, h = _text_size(e.s, e.h)
    if e.ha == "l":
        x0, x1 = e.pos[0], e.pos[0] + w
    elif e.ha == "r":
        x0, x1 = e.pos[0] - w, e.pos[0]
    else:
        x0, x1 = e.pos[0] - w / 2, e.pos[0] + w / 2
    if e.va == "b":
        y0, y1 = e.pos[1], e.pos[1] + h
    elif e.va == "t":
        y0, y1 = e.pos[1] - h, e.pos[1]
    else:
        y0, y1 = e.pos[1] - h / 2, e.pos[1] + h / 2
    if not e.rot:
        return x0, y0, x1, y1
    a = math.radians(e.rot)
    ca, sa = math.cos(a), math.sin(a)
    corners = []
    for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
        dx, dy = x - e.pos[0], y - e.pos[1]
        corners.append((e.pos[0] + dx * ca - dy * sa,
                        e.pos[1] + dx * sa + dy * ca))
    return _from_points(corners)


def _from_points(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def entity_bounds(e, dim_text_height=3.0):
    if isinstance(e, Line):
        return _from_points([e.p1, e.p2])
    if isinstance(e, (Poly, Filled)):
        return _from_points(e.pts) if e.pts else None
    if isinstance(e, (Circle, Arc)):
        x, y = e.c
        return x - e.r, y - e.r, x + e.r, y + e.r
    if isinstance(e, Text):
        return _text_bounds(e)
    if isinstance(e, Dim):
        # Usa la misma descomposición que el visor: incluye líneas de
        # extensión, texto rotado y las flechas exteriores de cotas estrechas.
        return union_bounds(entity_bounds(part, dim_text_height)
                            for part in dim_parts(e, dim_text_height))
    if isinstance(e, Leader):
        end = (e.elbow[0] + e.side * e.shelf, e.elbow[1])
        label = Text((end[0], end[1] + e.h * 0.3), e.s, e.h,
                     ha="l" if e.side > 0 else "r", va="b")
        return union_bounds([_from_points([e.tip, e.elbow, end]),
                             _text_bounds(label)])
    if isinstance(e, Table):
        x0, y0 = e.pos
        width = sum(e.col_w)
        rows = len(e.rows) + (1 if e.header else 0)
        bottom = y0 - rows * e.row_h
        top = y0
        if e.title:
            th = (e.h_row or e.row_h * 0.4) * 1.15
            top += th * 1.9
        return x0, bottom, x0 + width, top
    return None


def union_bounds(boxes):
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def drawing_bounds(drawing):
    heights = [e.h for e in drawing.ents if isinstance(e, Text) and e.h > 0]
    dim_text_height = max(heights, default=3.0)
    return union_bounds(entity_bounds(e, dim_text_height) for e in drawing.ents)
