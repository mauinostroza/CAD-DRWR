# -*- coding: utf-8 -*-
"""
app.preview — Vista previa 2D con zoom y paneo (QPainter).

Renderiza exactamente la misma IR que exporta el DXF.
Colores y grosores equivalentes a las capas del DXF.
"""

import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (QColor, QFont, QPainter, QPainterPath, QPen,
                           QBrush, QPixmap)
from PySide6.QtWidgets import QWidget

from core import ir
from core.ir import (Line, Circle, Arc, Poly, Filled, Text, Dim, Leader,
                     Table)
from core.dims import dim_parts
from core.bounds import drawing_bounds

BG = QColor("#23272e")
LAYER_QCOLOR = {
    ir.L_EJE: "#e05555",
    ir.L_CONC: "#f2f2f2",
    ir.L_ACERO: "#f7d84a",
    ir.L_ACOT: "#67d17c",
    ir.L_TXT: "#5ec8e8",
    ir.L_PERF: "#6a9fe0",
    ir.L_SOLD: "#e8955e",
    ir.L_HACH: "#8a8f98",
    ir.L_TABLA: "#f2f2f2",
    ir.L_OCULTO: "#8a8f98",
}
LAYER_WIDTH = {
    ir.L_EJE: 1.0, ir.L_CONC: 1.6, ir.L_ACERO: 2.6, ir.L_ACOT: 1.1,
    ir.L_TXT: 1.1, ir.L_PERF: 1.2, ir.L_SOLD: 1.2, ir.L_HACH: 0.8,
    ir.L_TABLA: 1.2, ir.L_OCULTO: 1.0,
}

ALIGN_H = {"l": Qt.AlignLeft, "c": Qt.AlignHCenter, "r": Qt.AlignRight}
ALIGN_V = {"b": Qt.AlignBottom, "m": Qt.AlignVCenter, "t": Qt.AlignTop}


class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dwg = ir.Drawing()
        self.scale = 0.2           # px por mm
        self.center = (0.0, 0.0)   # mm
        self._drag = None
        self.setMinimumSize(420, 320)
        self.setMouseTracking(True)
        self.setAutoFillBackground(True)
        self.th = 12.0             # altura de texto de cota en mm (IR)

    # ------------------------------------------------------------- datos --
    def set_drawing(self, dwg: ir.Drawing):
        self.dwg = dwg
        for e in dwg.ents:
            if isinstance(e, Text) and e.h > 0:
                self.th = e.h
                break
        self.update()

    def fit(self):
        bounds = drawing_bounds(self.dwg)
        if bounds is None:
            self.center, self.scale = (0, 0), 0.2
            self.update()
            return
        x0, y0, x1, y1 = bounds
        w = max(x1 - x0, 1.0)
        h = max(y1 - y0, 1.0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        margin = 90
        self.scale = min((self.width() - margin) / w,
                         (self.height() - margin) / h)
        self.scale = max(self.scale, 1e-4)
        self.center = (cx, cy)
        self.update()

    # ---------------------------------------------------------- interacción --
    def wheelEvent(self, ev):
        delta = ev.angleDelta().y() / 120.0
        if abs(delta) < 1e-6:
            return
        old = self.scale
        self.scale *= 1.15 ** delta
        self.scale = max(min(self.scale, old * 1e4), old * 1e-4)
        # zoom hacia el cursor
        pos = ev.position()
        mmx = self.center[0] + (pos.x() - self.width() / 2) / old
        mmy = self.center[1] - (pos.y() - self.height() / 2) / old
        self.center = (mmx - (pos.x() - self.width() / 2) / self.scale,
                       mmy + (pos.y() - self.height() / 2) / self.scale)
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._drag = ev.position()

    def mouseMoveEvent(self, ev):
        if self._drag is not None:
            dx = (ev.position().x() - self._drag.x()) / self.scale
            dy = (ev.position().y() - self._drag.y()) / self.scale
            self.center = (self.center[0] - dx, self.center[1] + dy)
            self._drag = ev.position()
            self.update()

    def mouseReleaseEvent(self, ev):
        self._drag = None

    def mouseDoubleClickEvent(self, ev):
        self.fit()

    def resizeEvent(self, ev):
        self.fit()

    # -------------------------------------------------------------- render --
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.fillRect(self.rect(), BG)
        s, cx, cy = self.scale, self.center[0], self.center[1]

        def X(x): return (x - cx) * s + self.width() / 2
        def Y(y): return self.height() / 2 - (y - cy) * s

        for e in self.dwg.ents:
            if isinstance(e, Table):
                _draw_table(p, e, X, Y, s)
                continue
            col = QColor(LAYER_QCOLOR.get(e.layer, "#ffffff"))
            w = LAYER_WIDTH.get(e.layer, 1.0)
            if isinstance(e, Line):
                p.setPen(_pen(col, w, e.layer, e.width))
                p.drawLine(QPointF(X(e.p1[0]), Y(e.p1[1])),
                           QPointF(X(e.p2[0]), Y(e.p2[1])))
            elif isinstance(e, Poly):
                p.setPen(_pen(col, w, e.layer, e.width))
                path = QPainterPath(QPointF(X(e.pts[0][0]), Y(e.pts[0][1])))
                for pt in e.pts[1:]:
                    path.lineTo(QPointF(X(pt[0]), Y(pt[1])))
                if e.closed:
                    path.closeSubpath()
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)
            elif isinstance(e, Circle):
                r = e.r * s
                if e.filled:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QBrush(col))
                    p.drawEllipse(QPointF(X(e.c[0]), Y(e.c[1])), r, r)
                else:
                    p.setPen(_pen(col, w, e.layer))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(QPointF(X(e.c[0]), Y(e.c[1])), r, r)
            elif isinstance(e, Arc):
                r = e.r * s
                sweep = _sweep(e)
                p.setPen(_pen(col, w, e.layer))
                p.setBrush(Qt.NoBrush)
                rect = QRectF(X(e.c[0]) - r, Y(e.c[1]) - r, 2 * r, 2 * r)
                p.drawArc(rect, int(round(e.a1 * 16)),
                          int(round(sweep * 16)))
            elif isinstance(e, Filled):
                poly = [QPointF(X(pt[0]), Y(pt[1])) for pt in e.pts]
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(col))
                p.drawPolygon(poly)
            elif isinstance(e, Text):
                _draw_text(p, e, X, Y, s)
            elif isinstance(e, Dim):
                for sub in dim_parts(e, self.th):
                    if isinstance(sub, (Line, Filled, Text)):
                        if isinstance(sub, Line):
                            p.setPen(_pen(col, 1.0, sub.layer))
                            p.drawLine(QPointF(X(sub.p1[0]), Y(sub.p1[1])),
                                       QPointF(X(sub.p2[0]), Y(sub.p2[1])))
                        elif isinstance(sub, Filled):
                            poly = [QPointF(X(pt[0]), Y(pt[1]))
                                    for pt in sub.pts]
                            p.setPen(Qt.NoPen)
                            p.setBrush(QBrush(col))
                            p.drawPolygon(poly)
                        else:
                            _draw_text(p, sub, X, Y, s)
            elif isinstance(e, Leader):
                p.setPen(_pen(col, 1.1, e.layer))
                p.drawLine(QPointF(X(e.tip[0]), Y(e.tip[1])),
                           QPointF(X(e.elbow[0]), Y(e.elbow[1])))
                if e.shelf > 0:
                    p.drawLine(QPointF(X(e.elbow[0]), Y(e.elbow[1])),
                               QPointF(X(e.elbow[0] + e.side * e.shelf),
                                       Y(e.elbow[1])))
                sub = Text((e.elbow[0] + e.side * e.shelf, e.elbow[1] + e.h * 0.3),
                           e.s, e.h, 0, e.layer,
                           "l" if e.side > 0 else "r", "b")
                _draw_text(p, sub, X, Y, s)
        p.end()

    # utilidad para grabar capturas (validación)
    def grab_png(self, path: str):
        pm = QPixmap(self.size())
        self.render(pm)
        pm.save(path, "PNG")


def _pen(col, w, layer=ir.L_CONC, width_mm=0.0):
    pen = QPen(col)
    wpx = max(1.0, w + width_mm * 0.05)
    pen.setWidthF(wpx)
    if layer == ir.L_EJE:
        pen.setStyle(Qt.DashLine)
    elif layer == ir.L_OCULTO:
        pen.setStyle(Qt.DotLine)
    return pen


def _sweep(a: Arc) -> float:
    if a.ccw:
        return (a.a2 - a.a1) % 360.0 or 360.0
    return -((a.a1 - a.a2) % 360.0 or 360.0)


def _ent_pts(e):
    if isinstance(e, Line):
        return [e.p1, e.p2]
    if isinstance(e, (Poly, Filled)):
        return e.pts
    if isinstance(e, (Circle, Arc)):
        return [e.c, (e.c[0] + e.r, e.c[1]), (e.c[0] - e.r, e.c[1]),
                (e.c[0], e.c[1] + e.r), (e.c[0], e.c[1] - e.r)]
    if isinstance(e, Text):
        return [e.pos]
    if isinstance(e, Dim):
        return [e.p1, e.p2, e.base]
    if isinstance(e, Leader):
        return [e.tip, e.elbow]
    if isinstance(e, Table):
        x0, y0 = e.pos
        w = sum(e.col_w)
        rows = len(e.rows) + (1 if e.header else 0)
        return [(x0, y0), (x0 + w, y0), (x0, y0 - rows * e.row_h),
                (x0 + w, y0 - rows * e.row_h)]
    return []


def _draw_text(p: QPainter, e: Text, X, Y, s):
    px = max(5, int(round(e.h * s)))
    f = QFont("DejaVu Sans")
    f.setPixelSize(px)
    p.setFont(f)
    p.setPen(QPen(QColor(LAYER_QCOLOR.get(e.layer, "#ffffff"))))
    p.save()
    p.translate(X(e.pos[0]), Y(e.pos[1]))
    if e.rot:
        p.rotate(-e.rot)
    # rectángulo de alineación relativo al punto de anclaje
    M = 5000
    if e.ha == "l":
        rx, rw, fl_h = 0.0, M, Qt.AlignLeft
    elif e.ha == "r":
        rx, rw, fl_h = -M, M, Qt.AlignRight
    else:
        rx, rw, fl_h = -M, 2 * M, Qt.AlignHCenter
    if e.va == "b":
        ry, rh, fl_v = -M / 2, M / 2, Qt.AlignBottom
    elif e.va == "t":
        ry, rh, fl_v = 0.0, M / 2, Qt.AlignTop
    else:
        ry, rh, fl_v = -M / 2, M, Qt.AlignVCenter
    p.drawText(QRectF(rx, ry, rw, rh), fl_h | fl_v, e.s)
    p.restore()


def _draw_table(p: QPainter, tb: Table, X, Y, s):
    x0, y0 = tb.pos                      # esquina sup. izq. en mm
    col_x = [X(x0)]
    x = x0
    for w in tb.col_w:
        x += w
        col_x.append(X(x))
    y_top = Y(y0)
    y_hdr_mm = y0 - (tb.row_h if tb.header else 0)
    y_hdr = Y(y_hdr_mm)
    y_end = Y(y_hdr_mm - len(tb.rows) * tb.row_h)
    col = QColor(LAYER_QCOLOR[ir.L_TABLA])
    pen = _pen(col, 1.2, ir.L_TABLA)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(col_x[0], y_top, col_x[-1] - col_x[0], y_end - y_top))
    if tb.title:
        sub = Text((x0 + sum(tb.col_w) / 2,
                    y0 + (tb.h_row or tb.row_h * 0.4) * 1.1),
                   tb.title, (tb.h_row or tb.row_h * 0.4) * 1.15,
                   0, ir.L_TABLA, "c", "b")
        _draw_text(p, sub, X, Y, s)
    if tb.header:
        p.drawLine(QPointF(col_x[0], y_hdr), QPointF(col_x[-1], y_hdr))
    for cx in col_x[1:-1]:
        p.drawLine(QPointF(cx, y_top), QPointF(cx, y_end))
    # encabezados
    if tb.header:
        for i, w in enumerate(tb.col_w):
            lines = tb.header[i].split("\n")
            xc_mm = x0 + sum(tb.col_w[:i]) + tb.col_w[i] / 2
            for k, line_s in enumerate(lines):
                yy = y0 - tb.row_h * (k + 1) / (len(lines) + 1)
                sub = Text((xc_mm, yy), line_s, tb.h_row, 0,
                           ir.L_TABLA, "c", "m")
                _draw_text(p, sub, X, Y, s)
    # filas de datos
    for r, row in enumerate(tb.rows):
        ytr_mm = y_hdr_mm - r * tb.row_h
        ytr = Y(ytr_mm)
        if r > 0:
            p.drawLine(QPointF(col_x[0], ytr), QPointF(col_x[-1], ytr))
        for c, w in enumerate(tb.col_w):
            xc_mm = x0 + sum(tb.col_w[:c]) + tb.col_w[c] / 2
            if (r, c) in tb.sketches:
                _draw_sketch(p, tb.sketches[(r, c)], X(xc_mm),
                             Y(ytr_mm - tb.row_h / 2),
                             tb.col_w[c] * s * 0.8, tb.row_h * s * 0.62)
            elif c < len(row) and row[c]:
                sub = Text((xc_mm, ytr_mm - tb.row_h / 2), row[c],
                           tb.h_row, 0, ir.L_TABLA, "c", "m")
                _draw_text(p, sub, X, Y, s)


def _draw_sketch(p, ents, cx_px, cy_px, max_w_px, max_h_px):
    pts = []
    for e in ents:
        pts.extend(_ent_pts(e))
    if not pts:
        return
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    w = max(max(xs) - min(xs), 1e-6)
    h = max(max(ys) - min(ys), 1e-6)
    sc = min(max_w_px / w, max_h_px / h, 60.0)
    for e in ents:
        col = QColor(LAYER_QCOLOR.get(e.layer, "#fff"))
        if isinstance(e, Line):
            p.setPen(_pen(col, 1.4))
            p.drawLine(QPointF(cx_px + e.p1[0] * sc, cy_px - e.p1[1] * sc),
                       QPointF(cx_px + e.p2[0] * sc, cy_px - e.p2[1] * sc))
        elif isinstance(e, Arc):
            r = e.r * sc
            sweep = _sweep(e)
            p.setPen(_pen(col, 1.4))
            rect = QRectF(cx_px + e.c[0] * sc - r, cy_px - e.c[1] * sc - r,
                          2 * r, 2 * r)
            p.drawArc(rect, int(round(e.a1 * 16)), int(round(sweep * 16)))
