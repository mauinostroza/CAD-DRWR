# -*- coding: utf-8 -*-
"""
core.dims — Constructor de acotado con niveles (cadenas + cota total).

Produce entidades `Dim` (cotas asociativas nativas en el DXF) y dibuja
líneas de extensión/aguja coherentes en la vista previa.
"""

from . import ir
from .ir import Dim, Line, Text
from .geom import arrow

GAP_K = 0.30     # separación geometría -> inicio línea de extensión (x th)
OV_K = 0.45      # exceso de la línea de extensión sobre la línea de cota
AR_K = 0.85      # tamaño de flecha respecto a la altura de texto
OFF_K = 0.70     # separación del texto sobre la línea de cota


def uses_outside_arrows(d: Dim, th: float) -> bool:
    """Indica si una cota no tiene espacio para texto y flechas interiores."""
    span = (abs(d.p2[1] - d.p1[1]) if d.vertical
            else abs(d.p2[0] - d.p1[0]))
    txt = d.txt or ir.fmt_mm(span)
    asz = AR_K * th
    return span < max(2.4 * asz, 0.68 * th * len(txt) + asz)


class DimBuilder:
    def __init__(self, ents: list, th: float):
        """th: altura de texto de cota EN MODELO (mm), ya escalada."""
        self.ents = ents
        self.th = th
        self.asz = AR_K * th
        self.ov = OV_K * th
        self.g0 = GAP_K * th

    # ------------------------------------------------------- horizontales --
    def h_chain(self, xs, y_geom: float, y_dim: float,
                fmt=ir.fmt_mm, texts=None, ext_from=None):
        """Cadena de cotas horizontales entre xs consecutivos."""
        texts = texts or [None] * (len(xs) - 1)
        y_ext_from = ext_from if ext_from is not None else y_geom
        for x in xs:
            ya = y_ext_from + (self.g0 if y_dim > y_geom else -self.g0)
            yb = y_dim + (self.ov if y_dim > y_geom else -self.ov)
            self.ents.append(Line((x, ya), (x, yb), ir.L_ACOT))
        for i in range(len(xs) - 1):
            t = texts[i] if i < len(texts) else None
            self.ents.append(Dim((xs[i], y_geom), (xs[i + 1], y_geom),
                                 ((xs[i] + xs[i + 1]) / 2.0, y_dim),
                                 txt=t if t is not None else fmt(abs(xs[i + 1] - xs[i]))))

    def h_total(self, x1: float, x2: float, y_geom: float, y_dim: float,
                fmt=ir.fmt_mm, txt=None, ext_from=None, texts=None):
        if txt is None and texts:
            txt = texts[0]
        self.h_chain([x1, x2], y_geom, y_dim, fmt, [txt],
                     ext_from=ext_from if ext_from is not None else y_geom)

    # ---------------------------------------------------------- verticales --
    def v_chain(self, ys, x_geom: float, x_dim: float,
                fmt=ir.fmt_mm, texts=None, ext_from=None):
        texts = texts or [None] * (len(ys) - 1)
        x_ext_from = ext_from if ext_from is not None else x_geom
        for y in ys:
            xa = x_ext_from + (self.g0 if x_dim > x_geom else -self.g0)
            xb = x_dim + (self.ov if x_dim > x_geom else -self.ov)
            self.ents.append(Line((xa, y), (xb, y), ir.L_ACOT))
        for i in range(len(ys) - 1):
            t = texts[i] if i < len(texts) else None
            self.ents.append(Dim((x_geom, ys[i]), (x_geom, ys[i + 1]),
                                 (x_dim, (ys[i] + ys[i + 1]) / 2.0),
                                 vertical=True,
                                 txt=t if t is not None else fmt(abs(ys[i + 1] - ys[i]))))

    def v_total(self, y1: float, y2: float, x_geom: float, x_dim: float,
                fmt=ir.fmt_mm, txt=None, ext_from=None, texts=None):
        if txt is None and texts:
            txt = texts[0]
        self.v_chain([y1, y2], x_geom, x_dim, fmt, [txt],
                     ext_from=ext_from if ext_from is not None else x_geom)


# ------------------------------------------------- dibujo de cotas (preview) --

def dim_parts(d: Dim, th: float) -> list:
    """Descompone una cota en entidades básicas para la vista previa."""
    asz = AR_K * th
    ov = OV_K * th
    g0 = GAP_K * th
    out = []
    p1, p2, base = d.p1, d.p2, d.base
    if not d.vertical:
        y_dim = base[1]
        y_geo = p1[1]
        sgn = 1.0 if y_dim > y_geo else -1.0
        for x, y in (p1, p2):
            out.append(Line((x, y + sgn * g0), (x, y_dim + sgn * ov), ir.L_ACOT))
        x1, x2 = p1[0], p2[0]
        txt = d.txt if d.txt else ir.fmt_mm(abs(x2 - x1))
        outside = uses_outside_arrows(d, th)
        if outside:
            out.append(Line((x1 - 1.8 * asz, y_dim),
                            (x2 + 1.8 * asz, y_dim), ir.L_ACOT))
            out.append(arrow((x1, y_dim), 0.0, asz))
            out.append(arrow((x2, y_dim), 180.0, asz))
        else:
            out.append(Line((x1, y_dim), (x2, y_dim), ir.L_ACOT))
            out.append(arrow((x1, y_dim), 180.0, asz))
            out.append(arrow((x2, y_dim), 0.0, asz))
        out.append(Text(((x1 + x2) / 2.0, y_dim + OFF_K * th), txt, th,
                        0, ir.L_ACOT, "c", "b"))
    else:
        x_dim = base[0]
        x_geo = p1[0]
        sgn = 1.0 if x_dim > x_geo else -1.0
        for x, y in (p1, p2):
            out.append(Line((x + sgn * g0, y), (x_dim + sgn * ov, y), ir.L_ACOT))
        y1, y2 = p1[1], p2[1]
        txt = d.txt if d.txt else ir.fmt_mm(abs(y2 - y1))
        outside = uses_outside_arrows(d, th)
        if outside:
            out.append(Line((x_dim, y1 - 1.8 * asz),
                            (x_dim, y2 + 1.8 * asz), ir.L_ACOT))
            out.append(arrow((x_dim, y1), 90.0, asz))
            out.append(arrow((x_dim, y2), 270.0, asz))
        else:
            out.append(Line((x_dim, y1), (x_dim, y2), ir.L_ACOT))
            out.append(arrow((x_dim, y1), 270.0, asz))
            out.append(arrow((x_dim, y2), 90.0, asz))
        out.append(Text((x_dim - OFF_K * th, (y1 + y2) / 2.0), txt, th,
                        90, ir.L_ACOT, "c", "b"))
    return out
