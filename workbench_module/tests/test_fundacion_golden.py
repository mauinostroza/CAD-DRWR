# -*- coding: utf-8 -*-
"""Paridad de fundaciones: el destino debe reproducir el golden del ORIGINAL."""
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

from golden_dump import dump  # noqa: E402
from backend.motor_calculo.cad_drwr.generators.foundation_sap import (  # noqa: E402
    build_foundation)
from backend.motor_calculo.cad_drwr.sap_geom import FundacionGeom  # noqa: E402

GOLDEN = os.path.join(WORKBENCH, "backend", "motor_calculo", "cad_drwr",
                      "golden", "fundacion_sap.json")

with open(GOLDEN, encoding="utf-8") as _fh:
    CASOS = json.load(_fh)

GEOMS = [c for c in CASOS if c["params"]["_geom"] is not None]


def _json_rt(obj):
    return json.loads(json.dumps(obj))


@pytest.mark.parametrize("caso", CASOS, ids=[c["nombre"] for c in CASOS])
def test_build_foundation_paridad(caso):
    params = caso["params"]
    if "error" in caso:
        with pytest.raises(ValueError) as exc:
            build_foundation(params)
        assert str(exc.value) == caso["error"]
        return
    assert _json_rt(dump(build_foundation(params))) == caso["drawing"]


@pytest.mark.parametrize("caso", GEOMS, ids=[c["nombre"] for c in GEOMS])
def test_geometria_round_trip(caso):
    d = caso["params"]["_geom"]
    assert FundacionGeom.from_dict(d).to_dict() == d
