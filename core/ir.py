# -*- coding: utf-8 -*-
"""
core.ir — Representación intermedia (IR) del dibujo.

Todos los generadores construyen un `Drawing` compuesto por entidades IR.
Tanto la vista previa (QPainter) como el escritor DXF (ezdxf) consumen
exactamente la misma IR, garantizando que "lo que se ve es lo que se exporta".

Unidades: milímetros, coordenadas X-Y matemáticas (Y hacia arriba).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

PT = Tuple[float, float]

# ---------------------------------------------------------------- capas ---
L_EJE = "EJE"            # líneas de eje (center lines)
L_CONC = "CONCRETO"      # contornos de concreto / placa / perfil
L_ACERO = "ACERO"        # barras de refuerzo, pernos
L_ACOT = "ACOTADO"       # cotas y flechas
L_TXT = "TEXTOS"         # rótulos, notas, etiquetas
L_PERF = "PERFORACIONES" # perforaciones de placas
L_SOLD = "SOLDADURA"     # símbolos de soldadura
L_HACH = "HACHURADO"     # hachurado de concreto
L_TABLA = "TABLAS"       # cuadros / tablas
L_OCULTO = "OCULTO"      # líneas ocultas

# Colores ACI (AutoCAD Color Index) por capa
LAYER_COLORS = {
    L_EJE: 1,        # rojo
    L_CONC: 7,       # blanco
    L_ACERO: 2,      # amarillo
    L_ACOT: 3,       # verde
    L_TXT: 4,        # cian
    L_PERF: 5,       # azul
    L_SOLD: 30,      # naranja
    L_HACH: 8,       # gris
    L_TABLA: 7,      # blanco
    L_OCULTO: 8,     # gris
}

# -----------------------------------------------------------------------


@dataclass
class Line:
    p1: PT
    p2: PT
    layer: str = L_CONC
    width: float = 0.0


@dataclass
class Circle:
    c: PT
    r: float
    layer: str = L_ACERO
    filled: bool = False


@dataclass
class Arc:
    c: PT
    r: float
    a1: float          # ángulo inicial (grados)
    a2: float          # ángulo final (grados)
    ccw: bool = True   # barrido antihorario de a1 -> a2
    layer: str = L_ACERO


@dataclass
class Poly:
    pts: List[PT]
    closed: bool = False
    layer: str = L_CONC
    width: float = 0.0


@dataclass
class Filled:
    """Polígono relleno: flechas de cota, puntos de barra, símbolos."""
    pts: List[PT]
    layer: str = L_ACOT


@dataclass
class Text:
    pos: PT
    s: str
    h: float                       # altura (en mm de modelo, ya escalada)
    rot: float = 0.0               # grados antihorario
    layer: str = L_TXT
    ha: str = "c"                  # 'l' | 'c' | 'r'
    va: str = "m"                  # 'b' | 'm' | 't'


@dataclass
class Dim:
    """Cota lineal asociativa. p1/p2 sobre la geometría, `base` sobre la
    línea de cota. vertical=False -> cota horizontal."""
    p1: PT
    p2: PT
    base: PT
    vertical: bool = False
    layer: str = L_ACOT
    txt: Optional[str] = None      # texto ya formateado (unidades incluidas)


@dataclass
class Leader:
    """Línea de referencia: flecha en `tip`, codo en `elbow`, texto encima
    de un shelf horizontal de longitud `shelf` hacia `side` (+1 derecha)."""
    tip: PT
    elbow: PT
    s: str
    h: float
    layer: str = L_TXT
    shelf: float = 0.0
    side: int = 1


@dataclass
class Table:
    """Tabla genérica. `pos` = esquina superior izquierda.
    sketches[(fila, col)] = lista de entidades IR con origen relativo al
    centro de la celda (para dibujos de forma en el cuadro de despiece)."""
    pos: PT
    col_w: List[float]
    row_h: float
    header: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    title: str = ""
    h_row: float = 0.0             # altura de texto celdas (0 -> auto)
    sketches: dict = field(default_factory=dict)


@dataclass
class Drawing:
    title: str = ""
    ents: List[object] = field(default_factory=list)


# ------------------------------------------------------------- utilidades ---

def add(d: Drawing, *ents) -> None:
    d.ents.extend(ents)


def fmt_mm(v: float) -> str:
    """Formato entero para cotas en milímetros."""
    iv = int(round(v))
    return str(iv)


def fmt_m(v_mm: float, dec: int = 2) -> str:
    """Formato decimal en metros (entrada en mm)."""
    return f"{v_mm / 1000.0:.{dec}f}"


def fmt_cm(v_mm: float, dec: int = 1) -> str:
    return f"{v_mm / 10.0:.{dec}f}"


def rect(x0: float, y0: float, x1: float, y1: float,
         layer: str = L_CONC) -> "Poly":
    """Rectángulo por esquinas opuestas."""
    return Poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                closed=True, layer=layer)


def translate(dwg: Drawing, dx: float, dy: float) -> Drawing:
    """Devuelve una copia de `dwg` con todas las entidades desplazadas
    (dx, dy) mm. Usado para ubicar el dibujo en un punto elegido por el
    usuario (p.ej. un clic en pantalla dentro del CAD) antes de enviarlo."""
    def tp(p: PT) -> PT:
        return (p[0] + dx, p[1] + dy)

    def te(e):
        if isinstance(e, Line):
            return Line(tp(e.p1), tp(e.p2), e.layer, e.width)
        if isinstance(e, Circle):
            return Circle(tp(e.c), e.r, e.layer, e.filled)
        if isinstance(e, Arc):
            return Arc(tp(e.c), e.r, e.a1, e.a2, e.ccw, e.layer)
        if isinstance(e, Poly):
            return Poly([tp(p) for p in e.pts], e.closed, e.layer, e.width)
        if isinstance(e, Filled):
            return Filled([tp(p) for p in e.pts], e.layer)
        if isinstance(e, Text):
            return Text(tp(e.pos), e.s, e.h, e.rot, e.layer, e.ha, e.va)
        if isinstance(e, Dim):
            return Dim(tp(e.p1), tp(e.p2), tp(e.base), e.vertical, e.layer,
                       e.txt)
        if isinstance(e, Leader):
            return Leader(tp(e.tip), tp(e.elbow), e.s, e.h, e.layer,
                         e.shelf, e.side)
        if isinstance(e, Table):
            return Table(tp(e.pos), list(e.col_w), e.row_h,
                        list(e.header), [list(r) for r in e.rows],
                        e.title, e.h_row, dict(e.sketches))
        return e

    return Drawing(dwg.title, [te(e) for e in dwg.ents])
