# -*- coding: utf-8 -*-
"""Golden: el motor copiado (cad_drwr) debe reproducir el volcado del ORIGINAL
para placa base, pedestal y losa, y el autollenado de perfil de placa base.

Los golden se generan con scripts/golden_placa_pedestal_losa.py (contra el
original de escritorio).
"""
import copy
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
    base_plate, pedestal, slab)

CONSTRUCTORES = {
    "placa_base": base_plate.build_base_plate,
    "pedestal": pedestal.build_pedestal,
    "losa": slab.build_slab,
}
# Claves derivadas de otras (no las escribe el autollenado).
DERIVADAS = {"_escala"}


def _cargar(nombre):
    with open(os.path.join(GOLDEN, nombre), encoding="utf-8") as fh:
        return json.load(fh)


def _json_rt(obj):
    return json.loads(json.dumps(obj))


CASOS = [
    (prefijo, caso)
    for prefijo in CONSTRUCTORES
    for caso in _cargar(f"{prefijo}.json")
]


@pytest.mark.parametrize(
    "prefijo,caso", CASOS, ids=[f"{p}-{c['nombre']}" for p, c in CASOS])
def test_ir_igual_al_original(prefijo, caso):
    build = CONSTRUCTORES[prefijo]
    drawing = build(copy.deepcopy(caso["params"]))
    assert _json_rt(dump(drawing)) == caso["drawing"]


AUTOFILL = _cargar("placa_base_autofill.json")


@pytest.mark.parametrize(
    "caso", AUTOFILL,
    ids=[f"{c['campo']}={c['valor']}" for c in AUTOFILL])
def test_autollenado_placa_base_igual_al_original(caso):
    antes, campo, despues = caso["antes"], caso["campo"], caso["despues"]
    # on_change del Panel se ejecuta con el widget ya en el valor nuevo.
    entrada = {**antes, campo: caso["valor"]}
    devuelto = base_plate.autollenar(entrada, campo)

    for clave, valor in devuelto.items():
        assert clave in despues, clave
        assert abs(despues[clave] - valor) <= 1e-9, (clave, valor, despues[clave])

    cambiadas = {k for k in antes
                 if k not in (campo, *DERIVADAS) and k in despues
                 and antes[k] != despues[k]}
    assert cambiadas - set(devuelto) == set()
    assert set(devuelto) - cambiadas == set()
