# -*- coding: utf-8 -*-
"""
cad.com_live — Conexión COM en vivo con AutoCAD / ZWCAD / BricsCAD.

Envía el dibujo (IR) directamente a la sesión CAD abierta a través de la
API COM/ActiveX (pywin32), sin pasar por archivo DXF. Las entidades se
crean en el espacio modelo del documento activo: líneas, polilíneas,
círculos, arcos, sólidos, textos, cotas asociativas nativas y capas.

Soportado:
- AutoCAD  (ProgID "AutoCAD.Application")
- ZWCAD    (ProgID "ZWCAD.Application", API COM idéntica a la de AutoCAD)
- BricsCAD (ProgID "BricscadApp.AcadApplication")

Requiere Windows + pywin32 (`pip install pywin32`) y el CAD abierto antes
de enviar. El resto del programa funciona sin esta dependencia: los
imports de win32 están dentro de las funciones.
"""

import math
import os

from core import ir
from core.ir import (Line, Circle, Arc, Poly, Filled, Text, Dim, Leader,
                     Table, Drawing)

PROGIDS = [
    ("AutoCAD.Application", "AutoCAD"),
    ("ZWCAD.Application", "ZWCAD"),
    ("BricscadApp.AcadApplication", "BricsCAD"),
]


# ------------------------------------------------------------- conexión --

def _com():
    """Importa pywin32 (solo Windows). Lanza RuntimeError con mensaje claro."""
    if os.name != "nt":
        raise RuntimeError(
            "La conexión COM en vivo solo está disponible en Windows. "
            "Use la exportación DXF y abra el archivo en AutoCAD/ZWCAD.")
    try:
        import pythoncom
        from win32com.client import GetActiveObject, VARIANT
        return pythoncom, GetActiveObject, VARIANT
    except ImportError:
        raise RuntimeError(
            "pywin32 no está instalado. Ejecute:\n"
            "    pip install pywin32\n"
            "y vuelva a intentar el envío en vivo.")


def detectar():
    """Busca una sesión CAD abierta. Devuelve (app, progid) o lanza
    RuntimeError con mensaje útil."""
    pythoncom, GetActiveObject, _ = _com()
    for pid, nombre in PROGIDS:
        try:
            app = GetActiveObject(pid)
            return app, pid
        except Exception:
            continue
    raise RuntimeError(
        "No se encontró AutoCAD, ZWCAD o BricsCAD abierto.\n"
        "Inicie el programa CAD (con al menos un documento activo) "
        "y reintente el envío en vivo.")


def _documento(app, abrir=None):
    """Devuelve el documento de trabajo: el indicado, el activo o uno nuevo."""
    if abrir:
        return app.Documents.Open(abrir)
    try:
        doc = app.ActiveDocument
        if doc is not None:
            return doc
    except Exception:
        pass
    return app.Documents.Add()


def _pt(VARIANT, pythoncom, p, z=0.0):
    """Punto IR (x, y) -> VARIANT array 3D para la API COM."""
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                   (float(p[0]), float(p[1]), float(z)))


def _flat(VARIANT, pythoncom, pts):
    vals = []
    for p in pts:
        vals.extend((float(p[0]), float(p[1])))
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, vals)


# ------------------------------------------------------------- capas --

def _capas(doc):
    for name, aci in ir.LAYER_COLORS.items():
        try:
            ly = doc.Layers.Add(name)
            ly.Color = int(aci)
        except Exception:
            continue
    for lt in ("CENTER", "HIDDEN"):
        try:
            doc.Linetypes.Load(lt)
        except Exception:
            pass  # ya cargado
    try:
        doc.Layers.Item(ir.L_EJE).Linetype = "CENTER"
        doc.Layers.Item(ir.L_OCULTO).Linetype = "HIDDEN"
    except Exception:
        pass


def _vars_cota(doc, dwg):
    """Variables de estilo de cota equivalentes al dimstyle del DXF."""
    from cad.dxf_out import _infer_th, _infer_ltscale
    th = _infer_th(dwg)
    pares = [
        ("DIMTXT", th), ("DIMASZ", 0.85 * th), ("DIMEXE", 0.45 * th),
        ("DIMEXO", 0.30 * th), ("DIMGAP", 0.35 * th), ("DIMTAD", 1),
        ("DIMJUST", 0), ("DIMDEC", 0), ("DIMZIN", 8), ("DIMLUNIT", 2),
        ("LTSCALE", _infer_ltscale(dwg)),
    ]
    for k, v in pares:
        try:
            doc.SetVariable(k, v)
        except Exception:
            pass


# -------------------------------------------------------- alineación texto --

# enum acAlignment de AutoCAD/ZWCAD
_ALTXT = {
    ("l", "b"): 12, ("c", "b"): 13, ("r", "b"): 14,
    ("l", "m"): 9, ("c", "m"): 10, ("r", "m"): 11,
    ("l", "t"): 6, ("c", "t"): 7, ("r", "t"): 8,
}


def _texto(msp, e, VPT):
    t = msp.AddText(e.s, VPT(e.pos, 0.0), float(e.h))
    try:
        t.Rotation = math.radians(e.rot)
    except Exception:
        pass
    al = _ALTXT.get((e.ha, e.va), 0)
    try:
        if al in (0, 1, 2):          # usa punto de inserción
            t.InsertionPoint = VPT(e.pos, 0.0)
        else:                        # alineaciones de bloque: punto de alineación
            t.Alignment = al
            t.TextAlignmentPoint = VPT(e.pos, 0.0)
    except Exception:
        try:
            t.InsertionPoint = VPT(e.pos, 0.0)
        except Exception:
            pass
    try:
        t.Layer = e.layer
    except Exception:
        pass
    return t


# ----------------------------------------------------------- entidades --

def _emit(msp, e, VPT, VF, pythoncom, VARIANT):
    """Crea una entidad IR primitiva en el espacio modelo COM."""
    if isinstance(e, Line):
        if e.width > 0:
            pl = msp.AddLightWeightPolyline(VF([e.p1, e.p2]))
            pl.ConstantWidth = float(e.width)
        else:
            msp.AddLine(VPT(e.p1), VPT(e.p2))

    elif isinstance(e, Poly):
        if len(e.pts) < 2:
            return
        pl = msp.AddLightWeightPolyline(VF(e.pts))
        pl.Closed = bool(e.closed)
        if e.width > 0:
            pl.ConstantWidth = float(e.width)

    elif isinstance(e, Circle):
        c = msp.AddCircle(VPT(e.c), float(e.r))
        c.Layer = e.layer
        if e.filled:
            try:
                h = msp.AddHatch(0, "SOLID", True)
                from win32com.client import VARIANT as V
                loop = V(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [c])
                h.AppendOuterLoop(loop)
                h.Layer = e.layer
                h.Evaluate()
            except Exception:
                pass  # queda el círculo sin relleno
        return

    elif isinstance(e, Arc):
        a1, a2 = (e.a1, e.a2) if e.ccw else (e.a2, e.a1)
        if a2 < a1:
            a2 += 360.0
        msp.AddArc(VPT(e.c), float(e.r), math.radians(a1), math.radians(a2))

    elif isinstance(e, Filled):
        p = e.pts
        if len(p) == 3:
            msp.AddSolid(VPT(p[0]), VPT(p[1]), VPT(p[2]), VPT(p[2]))
        elif len(p) >= 4:
            msp.AddSolid(VPT(p[0]), VPT(p[1]), VPT(p[3]), VPT(p[2]))

    elif isinstance(e, Text):
        _texto(msp, e, VPT)
        return

    else:
        return  # no primitiva: se maneja aparte
    try:
        msp.Item(msp.Count - 1).Layer = e.layer
    except Exception:
        pass


def _dim(msp, e, VPT):
    ang = math.pi / 2.0 if e.vertical else 0.0
    dim = msp.AddDimRotated(VPT(e.p1), VPT(e.p2), VPT(e.base), ang)
    try:
        dim.Layer = e.layer
    except Exception:
        pass
    if e.txt:
        try:
            dim.TextString = e.txt
        except Exception:
            pass
    # Fuerza la línea entre puntos cuando AutoCAD desplaza flechas/texto.
    try:
        dim.Fit = 1
    except Exception:
        pass
    return dim


def _aplanar(dwg: Drawing):
    """Expande Leader y Table en primitivas IR (misma geometría que el
    escritor DXF) para que el backend COM solo trate entidades simples.
    Las cotas (Dim) se preservan para crearlas nativas y asociativas."""
    out = []
    for e in dwg.ents:
        if isinstance(e, Leader):
            out.append(Line(e.tip, e.elbow, layer=e.layer))
            if e.shelf > 0:
                p2 = (e.elbow[0] + e.side * e.shelf, e.elbow[1])
                out.append(Line(e.elbow, p2, layer=e.layer))
            else:
                p2 = e.elbow
            ha = "l" if e.side > 0 else "r"
            out.append(Text(p2, e.s, e.h, rot=0.0, layer=e.layer,
                            ha=ha, va="b"))
        elif isinstance(e, Table):
            out.extend(_tabla_prims(e))
        else:
            out.append(e)
    return out


def _tabla_prims(tb: Table):
    """Convierte una tabla IR en líneas/textos/bocetos IR."""
    from cad.dxf_out import _sketch_scale, _place
    prims = []
    x0, y0 = tb.pos
    th = tb.h_row
    n_rows = len(tb.rows) + (1 if tb.header else 0)
    total_w = sum(tb.col_w)
    y_top = y0
    y_hdr = y_top - (tb.row_h if tb.header else 0)
    y_end = y_hdr - len(tb.rows) * tb.row_h

    if tb.title:
        prims.append(Text((x0 + total_w / 2.0, y_top + 0.6 * th * 1.15),
                          tb.title, th * 1.15, layer=ir.L_TABLA,
                          ha="c", va="b"))

    prims.append(Poly([(x0, y_top), (x0 + total_w, y_top),
                       (x0 + total_w, y_end), (x0, y_end)],
                      closed=True, layer=ir.L_TABLA))
    if tb.header:
        prims.append(Line((x0, y_hdr), (x0 + total_w, y_hdr),
                          layer=ir.L_TABLA))
    x = x0
    for w in tb.col_w[:-1]:
        x += w
        prims.append(Line((x, y_top), (x, y_end), layer=ir.L_TABLA))

    if tb.header:
        x = x0
        for i, w in enumerate(tb.col_w):
            lines = tb.header[i].split("\n")
            n = len(lines)
            for k, s in enumerate(lines):
                yc = y_hdr - tb.row_h * (k + 1) / (n + 1)
                prims.append(Text((x + w / 2.0, yc), s, th,
                                  layer=ir.L_TABLA, ha="c", va="m"))
            x += w

    for r, row in enumerate(tb.rows):
        ytr = y_hdr - r * tb.row_h
        if r > 0:
            prims.append(Line((x0, ytr), (x0 + total_w, ytr),
                              layer=ir.L_TABLA))
        x = x0
        for c, w in enumerate(tb.col_w):
            if (r, c) in tb.sketches:
                scale = _sketch_scale(tb.sketches[(r, c)], w * 0.8,
                                      tb.row_h * 0.62)
                cx = x + w / 2.0
                cy = ytr - tb.row_h / 2.0
                for se in tb.sketches[(r, c)]:
                    prims.append(_place(se, cx, cy, scale))
            elif c < len(row) and row[c]:
                txt = row[c]
                ha = "c"
                va = "m"
                if c == len(row) - 1 and txt.startswith("Σ"):
                    ha = "r"
                prims.append(Text((x + w / 2.0, ytr - tb.row_h / 2.0), txt,
                                  th, layer=ir.L_TABLA, ha=ha, va=va))
            x += w
    return prims


# ------------------------------------------------------------- API pública --

def enviar_dibujo(dwg: Drawing, abrir: str = None, origen=None) -> str:
    """Envía el dibujo IR a la sesión CAD abierta (COM en vivo).

    Si `abrir` es una ruta .dxf, en su lugar abre ese archivo en el CAD.
    Si `origen` es un punto (x, y), el dibujo se desplaza para que su
    origen local quede en ese punto (p.ej. el resultado de `pedir_punto`,
    un clic en pantalla del usuario).
    Devuelve un resumen legible para la barra de estado.
    """
    pythoncom, GetActiveObject, VARIANT = _com()
    app, pid = detectar()
    pythoncom.CoInitialize()
    try:
        doc = _documento(app, abrir)
        _capas(doc)

        if origen is not None:
            dwg = ir.translate(dwg, origen[0], origen[1])

        prims = _aplanar(dwg) if not abrir else []
        if prims:
            _vars_cota(doc, dwg)

        msp = doc.ModelSpace

        def VPT(p, z=0.0):
            return _pt(VARIANT, pythoncom, p, z)

        def VF(pts):
            return _flat(VARIANT, pythoncom, pts)

        n = 0
        errs = 0
        for e in prims:
            if isinstance(e, Dim):
                try:
                    _dim(msp, e, VPT)
                    n += 1
                except Exception:
                    errs += 1
                continue
            try:
                _emit(msp, e, VPT, VF, pythoncom, VARIANT)
                n += 1
            except Exception:
                errs += 1

        try:
            doc.Regen(1)
        except Exception:
            try:
                doc.Regen()
            except Exception:
                pass
        try:
            app.ZoomExtents()
        except Exception:
            pass

        if abrir:
            return f"{pid} — documento abierto: {doc.Name}"
        resumen = f"{pid} — documento: {doc.Name} — {n} entidades creadas"
        if errs:
            resumen += f" ({errs} omitidas)"
        return resumen
    finally:
        pythoncom.CoUninitialize()


def abrir_dxf_en_cad(path: str) -> str:
    """Exporta indirectamente: abre un archivo DXF existente en el CAD vivo."""
    if not os.path.isfile(path):
        raise RuntimeError(f"No existe el archivo:\n{path}")
    return enviar_dibujo(Drawing(), abrir=path)


def pedir_punto(mensaje: str = "Especifique el punto de inserción del dibujo: "):
    """Activa el documento del CAD y pide al usuario un clic en pantalla
    (comando nativo GetPoint). Devuelve (x, y) en coordenadas de modelo
    del CAD. Lanza RuntimeError si no hay CAD/documento o si se cancela
    (Esc / botón derecho)."""
    pythoncom, GetActiveObject, VARIANT = _com()
    app, pid = detectar()
    pythoncom.CoInitialize()
    try:
        doc = _documento(app)
        try:
            app.Visible = True
            app.WindowState = 3  # acMax: trae la ventana del CAD al frente
        except Exception:
            pass
        try:
            doc.Activate()
        except Exception:
            pass
        try:
            pt = doc.Utility.GetPoint(None, mensaje)
        except Exception:
            raise RuntimeError(
                "No se especificó ningún punto (selección cancelada).")
        return (float(pt[0]), float(pt[1]))
    finally:
        pythoncom.CoUninitialize()


def estado() -> str:
    """Prueba de conexión para el botón 'Detectar CAD'."""
    app, pid = detectar()
    ver = ""
    try:
        ver = app.Version
    except Exception:
        pass
    doc_name = ""
    try:
        doc_name = app.ActiveDocument.Name
    except Exception:
        pass
    return f"{pid}  |  versión {ver}  |  documento: {doc_name or '(ninguno)'}"
