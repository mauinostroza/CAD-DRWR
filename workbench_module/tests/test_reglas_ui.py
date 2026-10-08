"""Reglas de interfaz (sin Qt) frente al golden generado desde el ORIGINAL.

Golden: backend/motor_calculo/cad_drwr/golden/reglas_ui.json
(scripts/golden_reglas_ui.py, con QT_QPA_PLATFORM=offscreen).
"""

import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WORKBENCH = os.path.abspath(os.path.join(HERE, ".."))
SCRIPTS = os.path.join(WORKBENCH, "scripts")
for _p in (WORKBENCH, SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.motor_calculo.cad_drwr.generators.data import factor_escala  # noqa: E402
from backend.motor_calculo.cad_drwr.generators.reglas_ui import (  # noqa: E402
    autollenar_ui,
    habilitados,
)

GOLDEN = os.path.join(WORKBENCH, "backend", "motor_calculo", "cad_drwr", "golden", "reglas_ui.json")

with open(GOLDEN, encoding="utf-8") as _fh:
    CASOS = json.load(_fh)

TOL = 1e-9


def _id(caso):
    return f"{caso['modulo']}-{caso['nombre']}"


def _aplicado(caso):
    """Estado con el cambio del usuario y lo que añade el autollenado.

    ``_escala`` no lo produce el autollenado: lo deriva ``panel.params()`` de
    ``escala``. Aquí se deriva igual (factor_escala) tras fusionar, para que la
    comparación con el golden cubra también esa derivación.
    """
    antes = caso["params_antes"]
    con_cambio = dict(antes)
    con_cambio[caso["campo"]] = caso["valor"]
    extra = autollenar_ui(caso["modulo"], con_cambio, caso["campo"], previo=antes)
    final = {**con_cambio, **extra}
    if "escala" in final:
        final["_escala"] = factor_escala(final["escala"])
    return con_cambio, extra, final


@pytest.mark.parametrize("caso", CASOS, ids=[_id(c) for c in CASOS])
def test_habilitados_paridad(caso):
    assert habilitados(caso["modulo"], caso["params_despues"]) == caso["habilitados"]


@pytest.mark.parametrize("caso", CASOS, ids=[_id(c) for c in CASOS])
def test_autollenar_paridad(caso):
    _, _, final = _aplicado(caso)
    esperado = caso["params_despues"]
    assert set(final) == set(esperado), set(final) ^ set(esperado)
    for clave, val in esperado.items():
        obtenido = final[clave]
        # int y float no son intercambiables: el tipo debe ser el del widget.
        assert type(obtenido) is type(val), (clave, obtenido, val)
        if isinstance(val, float):
            assert abs(obtenido - val) <= TOL, (clave, obtenido, val)
        else:
            assert obtenido == val, (clave, obtenido, val)
    # _escala se deriva de escala; debe coincidir en todos los casos.
    assert final["_escala"] == esperado["_escala"]


@pytest.mark.parametrize("caso", CASOS, ids=[_id(c) for c in CASOS])
def test_autollenar_solo_devuelve_cambios(caso):
    con_cambio, extra, _ = _aplicado(caso)
    for clave, val in extra.items():
        assert not (
            clave in con_cambio
            and type(con_cambio[clave]) is type(val)
            and (
                con_cambio[clave] == val
                if not isinstance(val, float)
                else abs(con_cambio[clave] - val) <= TOL
            )
        ), f"{clave} no cambia y no debería devolverse"


def test_referencia_no_se_reaplica_sin_transicion():
    p = {"preset": "Referencia 20", "b": 70.0}
    assert autollenar_ui("pedestal", p, "preset", previo=dict(p)) == {}
    assert autollenar_ui("pedestal", p, "b", previo=dict(p)) == {}
    assert autollenar_ui("pedestal", p, "preset", previo=None) == {}


def test_habilitados_modulo_sin_reglas_devuelve_todo_habilitado():
    p = CASOS[0]["params_despues"]
    res = habilitados("losa", p)
    assert res and all(res.values())


def test_fundacion_no_aplica():
    with pytest.raises(ValueError):
        habilitados("fundacion_sap", {})
