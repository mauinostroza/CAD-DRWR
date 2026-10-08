import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.motor_calculo.cad_drwr import serializar as s  # noqa: E402
from backend.motor_calculo.cad_drwr.core import ir  # noqa: E402
from backend.motor_calculo.cad_drwr.core.bounds import drawing_bounds  # noqa: E402


def _dibujo():
    d = ir.Drawing()
    d.ents += [
        ir.Line((0, 0), (100, 0), ir.L_CONC, 2.0),
        ir.Circle((10, 10), 5, ir.L_ACERO, True),
        ir.Arc((0, 0), 20, 0, 90, False, ir.L_ACERO),
        ir.Poly([(0, 0), (10, 0), (10, 10)], True, ir.L_CONC),
        ir.Filled([(0, 0), (1, 0), (0, 1)], ir.L_ACOT),
        ir.Text((5, 5), "HOLA", 3.5, 90, ir.L_TXT, "l", "b"),
        ir.Dim((0, 0), (100, 0), (50, -20), False, ir.L_ACOT, "100", 3.0),
        ir.Leader((0, 0), (10, 10), "NOTA", 3.0, shelf=20),
        ir.Table((0, 0), [20, 20], 8, ["A", "B"], [["1", "2"]], "T"),
    ]
    return d


def test_ida_y_vuelta_entidades_simples():
    for e in _dibujo().ents[:7]:
        j = json.loads(json.dumps(s.entidad_a_json(e)))
        assert s.entidad_a_json(s.entidad_desde_json(j)) == j


def test_render_aplana_cotas_tablas_y_llamadas():
    out = s.dibujo_a_json(_dibujo())
    tipos = {e["t"] for e in out["render"]}
    assert "dim" not in tipos and tipos <= {"line", "circle", "arc", "poly", "filled", "text"}
    assert out["n_render"] > out["n_cad"] - 3
    assert any(e["t"] == "dim" for e in out["cad"])
    assert not any(e["t"] in ("leader", "table") for e in out["cad"])


def test_bounds_y_th_coherentes():
    d = _dibujo()
    out = s.dibujo_a_json(d)
    b = drawing_bounds(d)
    assert out["bounds"] == [round(v, 3) for v in b]
    assert out["th"] == 3.0


def test_th_coincide_con_dxf_out_si_hay_ezdxf():
    try:
        from backend.motor_calculo.cad_drwr.dxf_out import _infer_th
    except Exception:
        return
    d = _dibujo()
    assert s.inferir_th(d) == _infer_th(d)
    d2 = ir.Drawing(ents=[ir.Text((0, 0), "x", 7.0)])
    assert s.inferir_th(d2) == _infer_th(d2) == 7.0
    assert s.inferir_th(ir.Drawing()) == _infer_th(ir.Drawing()) == 15.0


def test_dibujo_vacio():
    out = s.dibujo_a_json(ir.Drawing())
    assert out["bounds"] is None and out["render"] == [] and out["cad"] == []


def test_tipo_desconocido():
    try:
        s.entidad_desde_json({"t": "x"})
    except ValueError:
        return
    raise AssertionError("debía lanzar ValueError")
