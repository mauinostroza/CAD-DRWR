import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend.motor_calculo.cad_drwr import generators as g  # noqa: E402
from scripts.golden_dump import dump  # noqa: E402

GOLDEN = RAIZ / "backend/motor_calculo/cad_drwr/golden"


@pytest.mark.parametrize("m", [m for m in g.MODULOS if not m.interactivo], ids=lambda m: m.id)
def test_defaults_coinciden_con_la_ui_del_escritorio(m):
    caso = json.loads((GOLDEN / f"{m.id}.json").read_text(encoding="utf-8"))[0]
    assert caso["nombre"] == "ui_defaults"
    d = g.defaults(m)
    for k, v in caso["params"].items():
        if isinstance(v, float):
            assert d[k] == pytest.approx(v), k
        else:
            assert d[k] == v, k
    assert set(d) == set(caso["params"])


@pytest.mark.parametrize("m", [m for m in g.MODULOS if not m.interactivo], ids=lambda m: m.id)
def test_dibujo_con_defaults_igual_al_golden(m):
    caso = json.loads((GOLDEN / f"{m.id}.json").read_text(encoding="utf-8"))[0]
    out = dump(m.build(g.normalizar(m, {})))
    assert json.loads(json.dumps(out)) == caso["drawing"]


def test_normalizar_rangos_y_tipos():
    m = g.POR_ID["placa_base"]
    assert g.normalizar(m, {"t": 14})["t"] == 14.0
    with pytest.raises(g.ParamError):
        g.normalizar(m, {"t": 5000})
    with pytest.raises(g.ParamError):
        g.normalizar(m, {"n_pernos": "5"})
    with pytest.raises(g.ParamError):
        g.normalizar(m, {"cartelas": "si"})
    with pytest.raises(g.ParamError):
        g.normalizar(m, {"t": float("nan")})
    with pytest.raises(g.ParamError):
        g.normalizar(m, {"t": True})
    # claves desconocidas se ignoran
    assert "zzz" not in g.normalizar(m, {"zzz": 1})


def test_escala_derivada():
    m = g.POR_ID["pedestal"]
    assert g.normalizar(m, {"escala": "1:50"})["_escala"] == 5.0


def test_campos_tipados():
    for m in g.MODULOS:
        for c in g.campos(m.spec):
            assert c["kind"] in ("combo", "int", "float", "chk")
