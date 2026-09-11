# -*- coding: utf-8 -*-
"""Especificación común del perno recto tipo PG.

La geometría y el cuadro de fabricación deben partir de los mismos valores.
Este módulo centraliza la conversión de parámetros de UI/plantilla y las
comprobaciones geométricas que no conviene dejar implícitas en el dibujo.
"""

from dataclasses import dataclass
import math


class PGSpecError(ValueError):
    """Parámetros de un PG incompatibles entre sí."""


@dataclass(frozen=True)
class PGSpec:
    d_mm: float
    d_display: str
    tipo_hilo: str
    h1: float
    h2: float
    W: float
    t: float
    b: float
    R: float
    P: float
    L: float
    n: int
    material: str
    nominal: str = ""

    @property
    def nominal_1in(self) -> bool:
        return self.nominal == '1 in'

    @property
    def nut_height(self):
        return 0.8 * self.d_mm

    @property
    def standard_washer_thickness(self):
        return max(4.0, 0.2 * self.d_mm)

    @property
    def upper_washer_bottom(self):
        return self.P - 0.5 * self.d_mm - 2 * self.nut_height - self.standard_washer_thickness


def _number(params, names, default):
    for name in names:
        if name in params and params[name] is not None and params[name] != "":
            try:
                return float(params[name])
            except (TypeError, ValueError) as exc:
                raise PGSpecError(f"{name} debe ser numérico") from exc
    return float(default)


def _nominal(params):
    raw = params.get("d_nominal", params.get("nominal_d",
                          params.get("nominal", params.get("diam_nominal", ""))))
    if isinstance(raw, bool):
        return '1 in' if raw else ''
    txt = str(raw).strip().lower()
    if txt in ('1', '1in', '1 in', '1"', '1 pulgadas', '1 pulgada'):
        return '1 in'
    if txt in ('métrico', 'metrico', 'mm', ''):
        return ''
    raise PGSpecError('Formato de diámetro no reconocido; use mm o 1 in')


def _diameter(params, nominal):
    raw = params.get("d_perno", params.get("d", 25.4))
    if isinstance(raw, str):
        txt = raw.strip().lower().replace('”', '"')
        if txt in ('1in', '1 in', '1"'):
            return 25.4
        txt = txt.replace('mm', '').strip()
        raw = txt
    try:
        d = float(raw)
    except (TypeError, ValueError) as exc:
        raise PGSpecError("d_perno debe ser numérico") from exc
    return 25.4 if nominal == '1 in' else d


def pg_spec_from_params(params: dict, *, validate: bool = True) -> PGSpec:
    """Normaliza un diccionario PG y devuelve la especificación única.

    ``Le``/``R`` y ``n``/``n_pernos`` se aceptan para conservar plantillas
    antiguas. ``permitir_h1_bajo_tc`` habilita explícitamente una rosca que
    cruza la rasante; de otro modo se rechaza para no esconder un dibujo
    incoherente detrás de un ``min``.
    """
    params = params or {}
    nominal = _nominal(params)
    d = _diameter(params, nominal)
    R = _number(params, ("R", "Le"), 850)
    P = _number(params, ("P",), 400)
    h1 = _number(params, ("h1",), 150)
    h2 = _number(params, ("h2",), 75)
    W = _number(params, ("W",), 75)
    t = _number(params, ("t", "t_golilla"), 20)
    b = _number(params, ("b", "b_golilla"), 50)
    L = _number(params, ("L",), R + P)
    n_raw = params.get("n", params.get("n_pernos", 48))
    try:
        n = int(n_raw)
        if float(n_raw) != n:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise PGSpecError("n debe ser entero") from exc
    material = str(params.get("material", "A307"))
    tipo_hilo = str(params.get("tipo_hilo", "8UN"))
    display = '1"' if nominal == '1 in' else f'{d:g}'

    spec = PGSpec(d, display, tipo_hilo, h1, h2, W, t, b, R, P, L, n,
                  material, nominal)
    if validate:
        validate_pg_spec(spec, allow_h1_below_tc=bool(
            params.get("permitir_h1_bajo_tc", params.get("allow_h1_below_tc", False))))
    return spec


def validate_pg_spec(spec: PGSpec, *, allow_h1_below_tc: bool = False):
    """Valida cotas que afectan a la posición de piezas del PG."""
    finite = (spec.d_mm, spec.h1, spec.h2, spec.W, spec.t, spec.b,
              spec.R, spec.P, spec.L)
    if not all(math.isfinite(v) for v in finite):
        raise PGSpecError("los parámetros PG deben ser finitos")
    if spec.d_mm <= 0:
        raise PGSpecError("d debe ser mayor que cero")
    for label, value in (("R", spec.R), ("P", spec.P), ("h1", spec.h1),
                         ("h2", spec.h2), ("W", spec.W), ("t", spec.t),
                         ("b", spec.b)):
        if value <= 0:
            raise PGSpecError(f"{label} debe ser mayor que cero")
    if spec.n <= 0:
        raise PGSpecError("n debe ser mayor que cero")
    if abs(spec.L - (spec.R + spec.P)) > 1e-6:
        raise PGSpecError("L debe ser igual a R + P")
    if not allow_h1_below_tc and spec.h1 > spec.P:
        raise PGSpecError("h1 no puede superar P sin permitir_h1_bajo_tc explícito")
    if spec.h1 > spec.P + spec.R:
        raise PGSpecError("h1 excede el largo total del perno")
    if spec.h2 > spec.R:
        raise PGSpecError("h2 no puede superar R")
    if spec.W <= spec.d_mm:
        raise PGSpecError("W debe superar el diámetro d")
    if spec.b + spec.t > spec.h2 + 1e-6:
        raise PGSpecError("b + t debe caber dentro de h2")
    if spec.h1 < spec.P - spec.upper_washer_bottom:
        raise PGSpecError("h1 no alcanza para la golilla, tuerca y contratuerca superiores")
    if spec.b < spec.nut_height:
        raise PGSpecError("b debe permitir que la tuerca inferior quede dentro del perno")
    if spec.upper_washer_bottom < 0:
        raise PGSpecError("P no alcanza para el conjunto superior")
    if spec.h1 + spec.h2 > spec.L:
        raise PGSpecError("Las roscas superior e inferior se superponen")
    return spec


def pg_table_rows(spec: PGSpec):
    """Filas verticales del cuadro PG, usando los mismos números del dibujo."""
    return [
        ["DIÁMETRO DE PERNO", "d", spec.d_display],
        ["TIPO DE HILO", "", spec.tipo_hilo],
        ["LARGO DE HILO", "h1", f"{spec.h1:g}"],
        ["LARGO DE HILO", "h2", f"{spec.h2:g}"],
        ["TAMAÑO GOLILLA", "W", f"{spec.W:g}"],
        ["ESPESOR GOLILLA", "t", f"{spec.t:g}"],
        ["VUELO / EXTREMO", "b", f"{spec.b:g}"],
        ["EMPOTRAMIENTO", "R", f"{spec.R:g}"],
        ["PROYECCIÓN", "P", f"{spec.P:g}"],
        ["LARGO PERNO", "L", f"{spec.L:g}"],
        ["CANTIDAD TOTAL", "n", str(spec.n)],
    ]
