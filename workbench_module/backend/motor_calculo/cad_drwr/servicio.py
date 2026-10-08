"""Capa de servicio: parámetros -> dibujo IR, con validación de límites.

Código nuevo (no copia del escritorio). El router solo traduce HTTP.
"""

import math

from .core import ir
from .core.layout_review import annotation_overlaps
from .core.sheet import compose_sheet
from .generators import POR_ID, ParamError, normalizar
from .serializar import MAX_ENTIDADES

MAX_ZAPATAS = 200
MAX_PUNTOS = 5000
MAX_AREAS_ZAPATA = 500
MAX_PEDESTALES_ZAPATA = 200


class ErrorDibujo(ValueError):
    """Error esperable del usuario (se responde 422 con este mensaje)."""


def _finito(v, ruta):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ErrorDibujo(f"_geom: {ruta} debe ser un número finito")
    if abs(v) > 1e9:
        raise ErrorDibujo(f"_geom: {ruta} fuera de rango")


def _punto(p, ruta):
    if not isinstance(p, (list, tuple)) or len(p) < 2:
        raise ErrorDibujo(f"_geom: {ruta} debe ser un punto [x, y]")
    for i, v in enumerate(p[:3]):
        _finito(v, f"{ruta}[{i}]")


def validar_geom(geom):
    """Valida la geometría SAP2000 (FundacionGeom.to_dict) y la devuelve normalizada."""
    from .sap_geom import FundacionGeom

    if not isinstance(geom, dict):
        raise ErrorDibujo("_geom: formato inválido")
    zapatas = geom.get("zapatas")
    if not isinstance(zapatas, list):
        raise ErrorDibujo("_geom: falta la lista de zapatas")
    if len(zapatas) > MAX_ZAPATAS:
        raise ErrorDibujo(f"_geom: demasiadas zapatas (máximo {MAX_ZAPATAS})")
    for i, z in enumerate(zapatas):
        if not isinstance(z, dict):
            raise ErrorDibujo(f"_geom: zapata {i} inválida")
        contorno = z.get("contorno", [])
        if not isinstance(contorno, list) or len(contorno) > MAX_PUNTOS:
            raise ErrorDibujo(f"_geom: contorno de la zapata {i} inválido o demasiado grande")
        for j, p in enumerate(contorno):
            _punto(p, f"zapatas[{i}].contorno[{j}]")
        areas = z.get("areas", [])
        if not isinstance(areas, list) or len(areas) > MAX_AREAS_ZAPATA:
            raise ErrorDibujo(f"_geom: áreas de la zapata {i} inválidas o demasiado numerosas")
        for a in areas:
            if (
                not isinstance(a, dict)
                or not isinstance(a.get("pts", []), list)
                or len(a.get("pts", [])) > MAX_PUNTOS
            ):
                raise ErrorDibujo(f"_geom: área inválida en la zapata {i}")
            for j, p in enumerate(a.get("pts", [])):
                _punto(p, f"zapatas[{i}].areas.pts[{j}]")
            if a.get("espesor") is not None:
                _finito(a["espesor"], f"zapatas[{i}].areas.espesor")
        ped = z.get("pedestales", [])
        if not isinstance(ped, list) or len(ped) > MAX_PEDESTALES_ZAPATA:
            raise ErrorDibujo(f"_geom: pedestales de la zapata {i} inválidos")
        for p in ped:
            if not isinstance(p, dict):
                raise ErrorDibujo(f"_geom: pedestal inválido en la zapata {i}")
            for k in ("largo", "ancho"):
                _finito(p.get(k), f"zapatas[{i}].pedestales.{k}")
            _punto(p.get("centro"), f"zapatas[{i}].pedestales.centro")
    try:
        # Normaliza: completa los campos opcionales que el dibujo indexa.
        return FundacionGeom.from_dict(geom).to_dict()
    except (KeyError, TypeError, ValueError) as exc:
        raise ErrorDibujo(f"_geom: estructura incompleta ({exc})") from exc


def construir(modulo_id, params, lamina=None):
    """Devuelve (Drawing, params_normalizados)."""
    modulo = POR_ID.get(modulo_id)
    if modulo is None:
        raise ErrorDibujo(f"Módulo desconocido: {modulo_id}")
    try:
        p = normalizar(modulo, params)
    except ParamError as exc:
        raise ErrorDibujo(str(exc)) from exc
    if modulo.interactivo and p.get("_geom") is not None:
        p["_geom"] = validar_geom(p["_geom"])
    try:
        dwg = modulo.build(p)
    except ErrorDibujo:
        raise
    except (ValueError, KeyError, ZeroDivisionError, IndexError, TypeError) as exc:
        raise ErrorDibujo(f"No se pudo generar el dibujo: {exc}") from exc
    if lamina and lamina.get("activa"):
        try:
            escala = float(str(p.get("escala", "1:25")).split(":")[-1])
            dwg = compose_sheet(
                dwg,
                scale=escala,
                title=modulo.nombre,
                project=lamina.get("proyecto", ""),
                number=lamina.get("numero_plano", ""),
                revision=lamina.get("revision", ""),
            )
        except ValueError as exc:
            raise ErrorDibujo(str(exc)) from exc
    if len(dwg.ents) > MAX_ENTIDADES:
        raise ErrorDibujo(f"El dibujo tiene demasiadas entidades (máximo {MAX_ENTIDADES})")
    return dwg, p


def solapes(dwg):
    """Pares de textos que podrían solaparse (estimación geométrica)."""
    return [[a, b] for a, b in annotation_overlaps(dwg)][:50]


__all__ = ["ErrorDibujo", "construir", "solapes", "validar_geom", "ir"]
