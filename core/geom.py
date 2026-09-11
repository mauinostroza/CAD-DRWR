# -*- coding: utf-8 -*-
"""
core.geom — Utilidades geométricas compartidas.

- Hachurado de concreto por líneas a 45°.
- Barras dobladas (poly_bar): trazo de línea central con radios de doblez
  y cálculo de longitud de desarrollo (para el cuadro de despiece).
- Flechas, símbolos de nivel, líneas de rotura, símbolos de soldadura.
"""

import math
from . import ir
from .ir import PT, Line, Arc, Poly, Filled, Text, Circle

TOL = 1e-9


# ------------------------------------------------------------- primitivas ---

def pol(p: PT, ang_deg: float, dist: float) -> PT:
    a = math.radians(ang_deg)
    return (p[0] + dist * math.cos(a), p[1] + dist * math.sin(a))


def ang(p1: PT, p2: PT) -> float:
    return math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))


def dist(p1: PT, p2: PT) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def rot(p: PT, deg: float, about: PT = (0.0, 0.0)) -> PT:
    a = math.radians(deg)
    dx, dy = p[0] - about[0], p[1] - about[1]
    return (about[0] + dx * math.cos(a) - dy * math.sin(a),
            about[1] + dx * math.sin(a) + dy * math.cos(a))


def line_x(x: float, y1: float, y2: float, layer=ir.L_EJE) -> Line:
    return Line((x, y1), (x, y2), layer)


def line_y(y: float, x1: float, x2: float, layer=ir.L_EJE) -> Line:
    return Line((x1, y), (x2, y), layer)


def rect(x0: float, y0: float, x1: float, y1: float,
         layer=ir.L_CONC, closed=True) -> Poly:
    return Poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                closed=closed, layer=layer)


# ---------------------------------------------------------------- hachurado ---

def hatch_poly(pts, spacing: float, angle_deg: float = 45.0,
               layer=ir.L_HACH) -> list:
    """Hachurado por líneas paralelas recortadas contra un polígono simple.
    (Recorte por pares de intersecciones; funciona también en no convexos)."""
    out = []
    if len(pts) < 3 or spacing <= 0:
        return out
    a = math.radians(angle_deg)
    ca, sa = math.cos(-a), math.sin(-a)          # rota el polígono -angle
    rp = [(p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca) for p in pts]
    ys = [p[1] for p in rp]
    y0, y1 = min(ys), max(ys)
    n = int((y1 - y0) / spacing) + 2
    yc = y0 - (y0 % spacing if spacing else 0)
    for k in range(n):
        y = y0 + k * spacing
        xs = []
        j = len(rp) - 1
        for i in range(len(rp)):
            p1, p2 = rp[j], rp[i]
            if (p1[1] <= y < p2[1]) or (p2[1] <= y < p1[1]):
                t = (y - p1[1]) / (p2[1] - p1[1])
                xs.append(p1[0] + t * (p2[0] - p1[0]))
            j = i
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa, xb = xs[i], xs[i + 1]
            if xb - xa < TOL:
                continue
            ca2, sa2 = math.cos(a), math.sin(a)
            q1 = (xa * ca2 - y * sa2, xa * sa2 + y * ca2)
            q2 = (xb * ca2 - y * sa2, xb * sa2 + y * ca2)
            out.append(Line(q1, q2, layer))
    return out


# --------------------------------------------------------- barras dobladas ---

def poly_bar(pts, d: float, R_in: float, layer=ir.L_ACERO,
             width: float = 0.0):
    """Dibuja una barra doblada como línea central con arcos de doblez.

    pts  : vértices del recorrido (esquinas de la barra, línea central)
    d    : diámetro nominal de la barra (mm)
    R_in : radio interior de doblez (mm); radio de línea central = R_in + d/2

    Devuelve (entidades, longitud_de_desarrollo_en_mm).
    """
    # Las formas llegan también desde cuadros de despiece opcionales. Una
    # entrada vacía es una forma vacía, no un IndexError durante el render.
    if pts is None or len(pts) == 0:
        return [], 0.0
    if not math.isfinite(float(d)) or d <= 0:
        raise ValueError("el diámetro de barra debe ser positivo")
    if not math.isfinite(float(R_in)) or R_in < 0:
        raise ValueError("el radio interior de doblez no puede ser negativo")

    # depura puntos repetidos
    clean = [pts[0]]
    for p in pts[1:]:
        if dist(p, clean[-1]) > TOL:
            clean.append(p)
    pts = clean
    if len(pts) < 2:
        return [], 0.0

    Rm = R_in + d / 2.0
    if len(pts) == 2:
        L = dist(pts[0], pts[1])
        return [Line(pts[0], pts[1], layer, width)], L

    # Calcula primero todos los recortes. El algoritmo anterior recortaba un
    # tramo al 45% cuando no cabía el radio; eso dejaba el arco con centro y
    # extremos incompatibles, una discontinuidad que además contaminaba el
    # desarrollo. Aquí el radio pedido se conserva y se valida el recorrido
    # completo antes de emitir entidades.
    corners = []
    trim = [0.0] * len(pts)
    for i in range(1, len(pts) - 1):
        v = pts[i]
        p_prev, p_next = pts[i - 1], pts[i + 1]
        l1 = dist(p_prev, v)
        l2 = dist(v, p_next)
        if l1 < TOL or l2 < TOL:
            continue
        ux, uy = (v[0] - p_prev[0]) / l1, (v[1] - p_prev[1]) / l1
        wx, wy = (p_next[0] - v[0]) / l2, (p_next[1] - v[1]) / l2
        cr = ux * wy - uy * wx
        dt = ux * wx + uy * wy
        th = math.atan2(cr, dt)                      # ángulo con signo
        if abs(th) < math.radians(0.5):              # prácticamente recta
            continue
        if abs(th) >= math.radians(179.0):
            raise ValueError("doblez casi de 180 grados no es resoluble")
        Rm_i = Rm
        T = Rm_i * math.tan(abs(th) / 2.0)
        corners.append((i, ux, uy, wx, wy, cr, th, T))
        trim[i] = T

    for i in range(len(pts) - 1):
        available = dist(pts[i], pts[i + 1])
        used = trim[i] + trim[i + 1]
        if used > available + TOL:
            raise ValueError(
                "el radio solicitado no cabe en el tramo "
                f"{i + 1}: requiere {used:.3f} mm y hay {available:.3f} mm")

    ents: list = []
    dev = 0.0
    cur = pts[0]                       # punto actual del recorrido recortado
    for i, ux, uy, wx, wy, cr, th, T in corners:
        v = pts[i]
        t_in = (v[0] - T * ux, v[1] - T * uy)
        t_out = (v[0] + T * wx, v[1] + T * wy)
        # centro: a Rm del lado interior del doblez
        if cr > 0:    # giro antihorario -> centro a la izquierda de u
            nx, ny = -uy, ux
        else:         # horario -> centro a la derecha de u
            nx, ny = uy, -ux
        center = (t_in[0] + Rm_i * nx, t_in[1] + Rm_i * ny)

        ents.append(Line(cur, t_in, layer, width))
        dev += dist(cur, t_in)
        a1 = ang(center, t_in)
        a2 = ang(center, t_out)
        ents.append(Arc(center, Rm_i, a1, a2, ccw=(cr > 0), layer=layer))
        dev += Rm_i * abs(th)
        cur = t_out

    ents.append(Line(cur, pts[-1], layer, width))
    dev += dist(cur, pts[-1])
    return ents, dev


# ------------------------------------------------------------- símbolos ---

def arrow(tip: PT, ang_deg: float, size: float, layer=ir.L_ACOT) -> Filled:
    """Cabeza de flecha rellena; `tip` es la punta, apunta hacia ang_deg."""
    b1 = pol(tip, ang_deg + 180 - 12, size)
    b2 = pol(tip, ang_deg + 180 + 12, size)
    return Filled([tip, b1, b2], layer)


def tick(p: PT, ang_deg: float, size: float, layer=ir.L_ACOT) -> Line:
    """Marca oblicua (tick) alternativa para cotas."""
    return Line(pol(p, ang_deg + 90 + 45, size / 2),
                pol(p, ang_deg + 90 - 45, size / 2), layer)


def level_symbol(p: PT, h: float, txt: str, layer=ir.L_TXT) -> list:
    """Símbolo de nivel (triángulo + texto), p = punto en el nivel."""
    s = h * 0.9
    tri = Filled([(p[0] - s, p[1] + s), (p[0] + s, p[1] + s), (p[0], p[1])],
                 layer)
    l1 = Line((p[0] - 3 * s, p[1] + s), (p[0] + 3.2 * s, p[1] + s), layer)
    t1 = Text((p[0] - 3 * s, p[1] + s + h * 0.35), txt, h, 0, layer,
              ha="l", va="b")
    return [tri, l1, t1]


def break_line(p1: PT, p2: PT, amp: float, layer=ir.L_CONC) -> list:
    """Línea de rotura (corte) con zigzag al centro."""
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    a = ang(p1, p2)
    n = pol((mx, my), a, -amp * 1.5)
    s = pol((mx, my), a, amp * 1.5)
    z1 = pol(n, a + 90, amp)
    z2 = pol(s, a + 90, -amp)
    return [Poly([p1, n, z1, s, z2, p2], closed=False, layer=layer)]


def weld_symbol(tip: PT, elbow: PT, h: float, layer=ir.L_SOLD) -> list:
    """Símbolo básico de soldadura de filete (triángulos a ambos lados)."""
    out = [Line(tip, elbow, layer)]
    sh = h * 3.5
    side = 1 if elbow[0] >= tip[0] else -1
    p2 = (elbow[0] + side * sh, elbow[1])
    out.append(Line(elbow, p2, layer))
    t = h * 0.9
    for dx in (0.9 * h, 2.2 * h):
        base_x = elbow[0] + side * dx
        out.append(Filled([(base_x, elbow[1]),
                           (base_x + side * t, elbow[1]),
                           (base_x, elbow[1] - t)], layer))
    return out


def stirrup_pts(b: float, h: float, d: float, R_in: float) -> list:
    """Recorrido de línea central de un estribo proyectado cerrado.

    ``b`` y ``h`` son las dimensiones exteriores de la línea central, con
    origen en la esquina inferior izquierda.  La barra recorre el perímetro
    completo con cierre en esquina superior derecha. Los dos ganchos de
    135° envuelven la misma esquina y sus colas son paralelas hacia el núcleo.

    Cada tramo terminal se entrega a :func:`poly_bar` con ``Lh + T135``. El
    recorte tangente consume ``T135`` y deja exactamente ``Lh`` recto y libre;
    por ello no se acorta el gancho para hacer caber el radio.
    """
    if not all(math.isfinite(float(v)) for v in (b, h, d, R_in)):
        raise ValueError("las dimensiones del estribo deben ser finitas")
    if b <= 0 or h <= 0:
        raise ValueError("las dimensiones del estribo deben ser positivas")
    if d <= 0 or R_in < 0:
        raise ValueError("el diámetro y radio del estribo no son válidos")
    Lh = max(6.0 * d, 75.0)                    # largo de gancho (6d >= 75)
    Rm = R_in + d / 2.0
    T135 = Rm * math.tan(math.radians(135 / 2.0))
    if h < 2 * Rm - TOL:
        raise ValueError("altura insuficiente para estribo y ganchos a 135 grados")
    k = math.sqrt(0.5)
    tail = Lh + T135
    # Los vértices son intersecciones VIRTUALES de tangentes. Desplazarlos
    # T135-Rm sitúa ambos centros de arco en (b-Rm,h-Rm), sin círculos en
    # mitad de la cara ni ganchos que dejen las barras de esquina fuera.
    if b < max(2 * Rm, k * tail) - TOL:
        raise ValueError("ancho insuficiente para los ganchos de 135 grados")
    if h < k * tail - TOL:
        raise ValueError("altura insuficiente para los ganchos de 135 grados")
    v_top = (b + T135 - Rm, h)
    v_right = (b, h + T135 - Rm)
    return [(v_top[0] - k * tail, v_top[1] - k * tail), v_top,
            (0, h), (0, 0), (b, 0), v_right,
            (v_right[0] - k * tail, v_right[1] - k * tail)]


def corte_poligono(pts, eje: str, valor: float) -> list:
    """Corte real de un polígono simple (posiblemente no convexo) por la
    recta x=valor (eje='x') o y=valor (eje='y').

    Devuelve una lista de tramos (a, b) ordenados a lo largo del eje
    transversal donde la recta atraviesa material del polígono — mismo
    barrido de aristas + emparejado par-impar que usa `hatch_poly` para
    una línea horizontal, generalizado al eje pedido sin rotar el
    polígono. Un polígono con forma en L o combinada puede devolver más
    de un tramo (huecos entre partes que la recta no atraviesa)."""
    if len(pts) < 3:
        return []
    i_corte, i_transv = (0, 1) if eje == "x" else (1, 0)
    cortes = []
    j = len(pts) - 1
    for i in range(len(pts)):
        p1, p2 = pts[j], pts[i]
        c1, c2 = p1[i_corte], p2[i_corte]
        if (c1 <= valor < c2) or (c2 <= valor < c1):
            t = (valor - c1) / (c2 - c1)
            cortes.append(p1[i_transv] + t * (p2[i_transv] - p1[i_transv]))
        j = i
    cortes.sort()
    tramos = []
    for i in range(0, len(cortes) - 1, 2):
        a, b = cortes[i], cortes[i + 1]
        if b - a > TOL:
            tramos.append((a, b))
    return tramos


# ------------------------------------------------ contornos de malla (SAP2000) --

def agrupar_por_adyacencia(listas_nombres: list) -> list:
    """Agrupa shells en componentes conexas por adyacencia de arista.

    `listas_nombres[i]` es la lista ordenada de nombres de joint (esquinas)
    del shell `i`. Dos shells están en la misma componente si comparten al
    menos una arista (par de joints consecutivos, en cualquier orden) —
    edificios/fundaciones con varios shells sueltos en un mismo grupo de
    SAP2000 quedan separados en distintas componentes. Devuelve una lista
    de listas de índices (Union-Find)."""
    n = len(listas_nombres)
    aristas = []
    for nombres in listas_nombres:
        k = len(nombres)
        aristas.append({frozenset((nombres[i], nombres[(i + 1) % k]))
                        for i in range(k)})

    padre = list(range(n))

    def find(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            padre[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if aristas[i] & aristas[j]:
                union(i, j)

    grupos = {}
    for i in range(n):
        grupos.setdefault(find(i), []).append(i)
    return list(grupos.values())


def contorno_exterior(listas_nombres: list) -> list:
    """Contorno exterior único de un grupo de shells ya verificado como una
    sola componente conexa (ver `agrupar_por_adyacencia`).

    Cuenta cuántas veces aparece cada arista (par de joints, sin importar
    el orden) entre todos los shells: una arista compartida por dos shells
    es interior y se cancela; las que aparecen una sola vez son de borde.
    Encadena esas aristas de borde por nombre de joint (se asume un grafo
    de grado 2 — un solo lazo cerrado, sin huecos) y devuelve el contorno
    como lista ordenada de nombres de joint."""
    from collections import Counter, defaultdict
    conteo = Counter()
    for nombres in listas_nombres:
        k = len(nombres)
        for i in range(k):
            conteo[frozenset((nombres[i], nombres[(i + 1) % k]))] += 1

    vecinos = defaultdict(list)
    for arista, c in conteo.items():
        if c == 1:
            a, b = tuple(arista)
            vecinos[a].append(b)
            vecinos[b].append(a)
    if not vecinos:
        return []

    inicio = next(iter(vecinos))
    recorrido = [inicio]
    visitadas = set()
    actual = inicio
    while True:
        siguiente = None
        for v in vecinos[actual]:
            clave = frozenset((actual, v))
            if clave not in visitadas:
                siguiente = v
                visitadas.add(clave)
                break
        if siguiente is None or (siguiente == inicio and len(recorrido) > 2):
            break
        recorrido.append(siguiente)
        actual = siguiente
    return recorrido


def simplificar_colineales(pts: list, tol: float = 2.0) -> list:
    """Elimina de un polígono cerrado los vértices colineales con sus
    vecinos dentro de `tol` mm de distancia perpendicular, dejando solo
    las esquinas reales del contorno (pasadas repetidas hasta estabilizar,
    para limpiar cadenas de varios puntos colineales seguidos)."""
    out = list(pts)
    cambiado = True
    while cambiado and len(out) > 3:
        cambiado = False
        nuevo = []
        n = len(out)
        for i in range(n):
            a, b, c = out[i - 1], out[i], out[(i + 1) % n]
            dx, dy = c[0] - a[0], c[1] - a[1]
            largo = math.hypot(dx, dy)
            if largo < TOL:
                cambiado = True
                continue
            d = abs((b[0] - a[0]) * dy - (b[1] - a[1]) * dx) / largo
            if d <= tol:
                cambiado = True
                continue
            nuevo.append(b)
        out = nuevo
    return out


def thread_zigzag(p0: PT, length: float, w: float, pitch: float,
                  layer=ir.L_ACERO) -> list:
    """Rosca esquemática de perno: zigzag a lo largo de +Y desde p0."""
    pts = [p0]
    y = p0[1]
    side = 1
    while y < p0[1] + length:
        y = min(y + pitch / 2, p0[1] + length)
        pts.append((p0[0] + side * w / 2, y))
        side = -side
    return [Poly(pts, closed=False, layer=layer, width=0.0)]
