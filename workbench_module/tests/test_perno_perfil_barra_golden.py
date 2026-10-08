"""Golden: el motor copiado (cad_drwr) debe reproducir el volcado del ORIGINAL
para perno_anclaje, perfil y forma_barra, y el autollenado de perfil.

Los golden se generan con scripts/golden_perno_perfil_barra.py (contra el
original de escritorio).
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WB = os.path.dirname(HERE)  # workbench_module
SCRIPTS = os.path.join(WB, "scripts")
GOLDEN = os.path.join(WB, "backend", "motor_calculo", "cad_drwr", "golden")
for _p in (WB, SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from golden_dump import dump  # noqa: E402
from backend.motor_calculo.cad_drwr.generators import (  # noqa: E402
    anchor_bolt, bar_shape, profile)

CONSTRUCTORES = {
    "perno_anclaje": anchor_bolt.build_anchor_bolt,
    "perfil": profile.build_profile,
    "forma_barra": bar_shape.build_bar_shape,
}
TOL = 1e-9


def _cargar(nombre):
    with open(os.path.join(GOLDEN, nombre), encoding="utf-8") as f:
        return json.load(f)


def _casos_volcado():
    out = []
    for prefijo, build in CONSTRUCTORES.items():
        for caso in _cargar(prefijo + ".json"):
            out.append(pytest.param(build, caso,
                                    id=f"{prefijo}:{caso['nombre']}"))
    return out


def _iguales(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
            and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(a - b) <= TOL
    return a == b


@pytest.mark.parametrize("build,caso", _casos_volcado())
def test_volcado_igual_al_original(build, caso):
    real = json.loads(json.dumps(dump(build(caso["params"]))))
    assert real == caso["drawing"]


@pytest.mark.parametrize(
    "caso",
    [pytest.param(c, id=f"{c['campo']}={c['valor']}")
     for c in _cargar("perfil_autofill.json")])
def test_autollenado_perfil_igual_al_original(caso):
    antes, campo, despues = caso["antes"], caso["campo"], caso["despues"]
    # on_change del Panel se ejecuta con el widget ya en el valor nuevo.
    entrada = {**antes, campo: caso["valor"]}
    devuelto = profile.autollenar(entrada, campo)

    for clave, valor in devuelto.items():
        assert clave in despues, clave
        assert _iguales(valor, despues[clave]), (clave, valor, despues[clave])

    cambiadas = {k for k in antes
                 if k != campo and k in despues
                 and not _iguales(antes[k], despues[k])}
    assert cambiadas - set(devuelto) == set()
