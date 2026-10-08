"""Serialización JSON de la IR para el navegador y para el puente CAD.

Dos vistas del mismo dibujo:
- ``render``: primitivas ya aplanadas (tablas, llamadas y cotas expandidas)
  que el navegador pinta tal cual en SVG.
- ``cad``: entidades para ZWCAD/AutoCAD; igual que ``render`` pero conserva
  las cotas (``dim``) para crearlas como cotas nativas asociativas.

Es código nuevo (no copia del escritorio) y no depende de ezdxf.
"""

from .core import ir
from .core.annotations import expand_annotations
from .core.bounds import drawing_bounds
from .core.dims import dim_parts

DECIMALES = 3
MAX_ENTIDADES = 20000


def _r(v):
    return round(float(v), DECIMALES)


def _p(pt):
    return [_r(pt[0]), _r(pt[1])]


def inferir_th(dwg):
    """Altura de texto de cota; misma regla que ``dxf_out._infer_th``."""
    for e in dwg.ents:
        if isinstance(e, ir.Dim) and e.text_height > 0:
            return e.text_height
    for e in dwg.ents:
        if isinstance(e, ir.Text) and e.h > 0:
            return e.h
    return 15.0


def entidad_a_json(e):
    if isinstance(e, ir.Line):
        return {"t": "line", "a": _p(e.p1), "b": _p(e.p2), "l": e.layer, "w": _r(e.width)}
    if isinstance(e, ir.Circle):
        return {"t": "circle", "c": _p(e.c), "r": _r(e.r), "l": e.layer, "f": bool(e.filled)}
    if isinstance(e, ir.Arc):
        return {
            "t": "arc",
            "c": _p(e.c),
            "r": _r(e.r),
            "a1": _r(e.a1),
            "a2": _r(e.a2),
            "ccw": bool(e.ccw),
            "l": e.layer,
        }
    if isinstance(e, ir.Poly):
        return {"t": "poly", "p": [_p(p) for p in e.pts], "z": bool(e.closed), "l": e.layer, "w": _r(e.width)}
    if isinstance(e, ir.Filled):
        return {"t": "filled", "p": [_p(p) for p in e.pts], "l": e.layer}
    if isinstance(e, ir.Text):
        return {
            "t": "text",
            "p": _p(e.pos),
            "s": e.s,
            "h": _r(e.h),
            "rot": _r(e.rot),
            "l": e.layer,
            "ha": e.ha,
            "va": e.va,
        }
    if isinstance(e, ir.Dim):
        return {
            "t": "dim",
            "a": _p(e.p1),
            "b": _p(e.p2),
            "base": _p(e.base),
            "v": bool(e.vertical),
            "l": e.layer,
            "txt": e.txt,
            "th": _r(e.text_height),
        }
    raise TypeError(f"Entidad IR no serializable: {type(e).__name__}")


def entidad_desde_json(d):
    t = d["t"]
    pt = lambda v: (float(v[0]), float(v[1]))  # noqa: E731
    if t == "line":
        return ir.Line(pt(d["a"]), pt(d["b"]), d["l"], float(d.get("w", 0.0)))
    if t == "circle":
        return ir.Circle(pt(d["c"]), float(d["r"]), d["l"], bool(d.get("f", False)))
    if t == "arc":
        return ir.Arc(
            pt(d["c"]), float(d["r"]), float(d["a1"]), float(d["a2"]), bool(d.get("ccw", True)), d["l"]
        )
    if t == "poly":
        return ir.Poly([pt(p) for p in d["p"]], bool(d.get("z", False)), d["l"], float(d.get("w", 0.0)))
    if t == "filled":
        return ir.Filled([pt(p) for p in d["p"]], d["l"])
    if t == "text":
        return ir.Text(
            pt(d["p"]),
            str(d["s"]),
            float(d["h"]),
            float(d.get("rot", 0.0)),
            d["l"],
            d.get("ha", "c"),
            d.get("va", "m"),
        )
    if t == "dim":
        return ir.Dim(
            pt(d["a"]),
            pt(d["b"]),
            pt(d["base"]),
            bool(d.get("v", False)),
            d["l"],
            d.get("txt"),
            float(d.get("th", 0.0)),
        )
    raise ValueError(f"Tipo de entidad desconocido: {t!r}")


def ents_desde_json(lista):
    return [entidad_desde_json(d) for d in lista]


def primitivas_render(dwg, th=None):
    """Entidades planas para SVG: tablas/llamadas expandidas y cotas en partes."""
    th = th if th is not None else inferir_th(dwg)
    out = []
    for e in expand_annotations(dwg.ents):
        if isinstance(e, ir.Dim):
            out.extend(dim_parts(e, th))
        else:
            out.append(e)
    return out


def entidades_cad(dwg):
    """Entidades para el CAD: tablas/llamadas expandidas, cotas conservadas."""
    return list(expand_annotations(dwg.ents))


def dibujo_a_json(dwg):
    th = inferir_th(dwg)
    render = [entidad_a_json(e) for e in primitivas_render(dwg, th)]
    cad = [entidad_a_json(e) for e in entidades_cad(dwg)]
    b = drawing_bounds(dwg)
    return {
        "th": _r(th),
        "bounds": [_r(v) for v in b] if b else None,
        "render": render,
        "cad": cad,
        "n_render": len(render),
        "n_cad": len(cad),
    }
