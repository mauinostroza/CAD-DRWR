"""Marco y cajetín paramétricos para detalles, sin certificar su diseño."""

from . import ir
from .bounds import drawing_bounds


def compose_sheet(drawing, scale=25, project="", number="", revision="", title=""):
    if scale <= 0:
        raise ValueError("La escala debe ser positiva")
    bounds = drawing_bounds(drawing)
    if bounds is None:
        raise ValueError("No hay dibujo para componer la lámina")
    x0, y0, x1, y1 = bounds
    margin, box_h, text_h = 10 * scale, 32 * scale, 2.5 * scale
    rows = [
        f"PROYECTO: {project or 'POR DEFINIR'}",
        f"PLANO: {number or 'POR DEFINIR'}  |  REVISIÓN: {revision or 'POR DEFINIR'}",
        f"{title}  |  GEOMETRÍA EN mm  |  ESCALAS SEGÚN CADA VISTA; RESPETAR COTAS",
        "BORRADOR — REVISIÓN ESTRUCTURAL Y DE FABRICACIÓN PENDIENTE",
    ]
    width = max(x1 - x0 + 2 * margin, 200 * scale, max(len(row) for row in rows) * text_h * 0.75 + 8 * scale)
    height = y1 - y0 + 2 * margin + box_h
    result = ir.translate(drawing, margin - x0, margin + box_h - y0)
    result.ents.extend([ir.rect(0, 0, width, height, ir.L_TABLA), ir.rect(0, 0, width, box_h, ir.L_TABLA)])
    for i, row in enumerate(rows):
        result.ents.append(
            ir.Text((4 * scale, box_h - (i + 1) * 7 * scale), row, text_h, layer=ir.L_TABLA, ha="l")
        )
    return result
