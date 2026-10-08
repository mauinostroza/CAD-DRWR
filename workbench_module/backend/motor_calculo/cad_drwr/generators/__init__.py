"""Registro de módulos de dibujo (sin Qt) y utilidades de parámetros.

Cada módulo expone ``SPEC`` (lista de tuplas, formato del escritorio) y una
función ``build_*`` que recibe el diccionario de parámetros y devuelve la IR.
Aquí se convierte SPEC en campos tipados, se calculan los valores por defecto
(incluido el autollenado inicial que en el escritorio hacía el panel) y se
validan/normalizan los parámetros que llegan por la API.
"""

from collections import namedtuple

from . import anchor_bolt, bar_shape, base_plate, foundation_sap, pedestal, profile, slab
from .data import factor_escala

Modulo = namedtuple("Modulo", "id nombre spec build autollenar interactivo")


def _m(id_, nombre, mod, build, interactivo=False):
    return Modulo(id_, nombre, mod.SPEC, build, getattr(mod, "autollenar", None), interactivo)


MODULOS = [
    _m("placa_base", "Placa Base", base_plate, base_plate.build_base_plate),
    _m("pedestal", "Pedestal", pedestal, pedestal.build_pedestal),
    _m("losa", "Losa", slab, slab.build_slab),
    _m("perno_anclaje", "Perno de Anclaje", anchor_bolt, anchor_bolt.build_anchor_bolt),
    _m("perfil", "Perfil Estructural", profile, profile.build_profile),
    _m("forma_barra", "Forma de Barra", bar_shape, bar_shape.build_bar_shape),
    _m("fundacion_sap", "Fundación SAP2000", foundation_sap, foundation_sap.build_foundation, True),
]
POR_ID = {m.id: m for m in MODULOS}


class ParamError(ValueError):
    """Parámetro inválido; ``campo`` identifica la clave."""

    def __init__(self, campo, mensaje):
        super().__init__(f"{campo}: {mensaje}")
        self.campo = campo
        self.mensaje = mensaje


def campos(spec):
    """SPEC (tuplas) -> lista de diccionarios tipados para el formulario."""
    out = []
    for row in spec:
        key, label, kind = row[0], row[1], row[2]
        if kind == "combo":
            opts = [str(o) for o in row[3]]
            default = str(row[4]) if len(row) > 4 and str(row[4]) in opts else opts[0]
            out.append({"key": key, "label": label, "kind": "combo", "options": opts, "value": default})
        elif kind == "int":
            out.append(
                {
                    "key": key,
                    "label": label,
                    "kind": "int",
                    "min": row[3],
                    "max": row[4],
                    "value": row[5],
                    "step": row[6] if len(row) > 6 else 1,
                    "suffix": row[7] if len(row) > 7 else "",
                }
            )
        elif kind == "float":
            out.append(
                {
                    "key": key,
                    "label": label,
                    "kind": "float",
                    "min": row[3],
                    "max": row[4],
                    "value": row[5],
                    "decimals": row[6] if len(row) > 6 else 1,
                    "step": row[7] if len(row) > 7 else 1,
                    "suffix": row[8] if len(row) > 8 else "",
                }
            )
        elif kind == "chk":
            out.append({"key": key, "label": label, "kind": "chk", "value": bool(row[3])})
        else:
            raise ValueError(f"Tipo de campo desconocido: {kind!r}")
    return out


def defaults(modulo):
    """Valores iniciales reales de la interfaz (SPEC + autollenado inicial)."""
    p = {c["key"]: c["value"] for c in campos(modulo.spec)}
    if modulo.autollenar:
        p.update(modulo.autollenar(p, None))
    if modulo.interactivo:
        p.update(foundation_sap.PARAMS_DEFAULT)
    p["_escala"] = factor_escala(str(p.get("escala", "1:50")))
    return p


def normalizar(modulo, params):
    """Completa con defaults, convierte tipos y comprueba rangos.

    Lanza ``ParamError``. Las claves desconocidas se ignoran, salvo las
    reservadas (``_geom``) del módulo interactivo.
    """
    base = defaults(modulo)
    params = params or {}
    out = dict(base)
    for c in campos(modulo.spec):
        k = c["key"]
        if k not in params:
            continue
        v = params[k]
        if c["kind"] == "combo":
            if str(v) not in c["options"]:
                raise ParamError(k, f"valor no permitido: {v!r}")
            out[k] = str(v)
        elif c["kind"] in ("int", "float"):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ParamError(k, "debe ser un número")
            if v != v or v in (float("inf"), float("-inf")):
                raise ParamError(k, "debe ser un número finito")
            if not (c["min"] <= v <= c["max"]):
                raise ParamError(k, f"fuera de rango [{c['min']}, {c['max']}]")
            out[k] = int(round(v)) if c["kind"] == "int" else float(v)
        else:
            if not isinstance(v, bool):
                raise ParamError(k, "debe ser verdadero o falso")
            out[k] = v
    if modulo.interactivo:
        for k in ("escala", "fundacion"):
            if k in params:
                out[k] = str(params[k])
        if "espesor_default" in params:
            out["espesor_default"] = float(params["espesor_default"])
        if params.get("_geom") is not None:
            out["_geom"] = params["_geom"]
    out["_escala"] = factor_escala(str(out.get("escala", "1:50")))
    return out
