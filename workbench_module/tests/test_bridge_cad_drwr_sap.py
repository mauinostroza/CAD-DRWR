"""Tests de las rutas SAP del puente CAD (bridge/cad_drwr_sap.py) y del
adaptador ModelLink, con un SapModel FALSO: sin SAP2000 ni Windows.

El `call` falso ejecuta `fn(modelo)` en el mismo hilo o simula el
vencimiento de 30 s del actor del puente anfitrión (la tarea sigue viva en
otro hilo y el llamador recibe HTTPException con detalle vacío).

Geometría de prueba (mm, z=0 salvo el pedestal):
  S1 = A-B-C-D (0..1500 x 0..3500), S2 = B-E-F-C (1500..3000 x 0..3500)
  -> fundación fusionada de 3000 x 3500 por la arista compartida B-C.
  S3 = P5-P6-P7-P8 (5000..6000 x 0..1000) -> zapata separada.
  Pedestal P1 (400 x 400) vertical sobre M = (1500, 1750), nodo interior
  de la malla de S1 y S2 en la arista compartida.
  T1 = A-E horizontal: no es pedestal.
"""

import json
import pathlib
import sys
import threading
import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

RAIZ = pathlib.Path(__file__).resolve().parents[1]  # workbench_module
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from bridge import cad_drwr, cad_drwr_sap  # noqa: E402
from bridge.cad_sap_link import (
    ControlTrabajo,
    ModelLink,  # noqa: E402
    TrabajoCancelado,
)

PREF = "/v1/sap/actions/cad/sap"
CONTRATO = RAIZ / "web" / "src" / "cad_drwr" / "bridge_contracts.cad_drwr.json"


# --------------------------------------------------- SapModel FALSO --


class Units:
    def __init__(self, valor=6):  # 6 = kN-m-°C
        self.valor = valor
        self.historial = []

    def GetPresentUnits(self):
        return self.valor

    def SetPresentUnits(self, unidad):
        self.historial.append(unidad)
        self.valor = unidad
        return 0


class GroupDef:
    """nombre -> (tipos, nombres) o una excepción que lanza GetAssignments."""

    def __init__(self, grupos):
        self._g = grupos

    def GetNameList(self):
        return (len(self._g), list(self._g), 0)

    def GetAssignments(self, nombre, *args):
        valor = self._g[nombre]
        if isinstance(valor, Exception):
            raise valor
        tipos, nombres = valor
        return (len(nombres), list(tipos), list(nombres), 0)


class PointObj:
    def __init__(self, coords):
        self._c = coords

    def GetCoordCartesian(self, nombre, *args):
        x, y, z = self._c[nombre]
        return (0, x, y, z)  # forma que prueba primero el puente


class AreaObj:
    def __init__(self, m, areas):
        self._m, self._a = m, areas

    def GetPoints(self, nombre, *args):
        if self._m.gate is not None:  # permite detener la lectura a mitad
            self._m.llegado.set()
            self._m.gate.wait(5)
        pts = self._a[nombre]["pts"]
        return (len(pts), list(pts), 0)

    def GetProperty(self, nombre, *args):
        return (self._a[nombre]["seccion"], 0)

    def GetElm(self, nombre, *args):
        elms = self._a[nombre]["elms"]
        return (len(elms), list(elms), 0)


class AreaElm:
    def __init__(self, elms):
        self._e = elms

    def GetPoints(self, nombre, *args):
        pts = self._e[nombre]
        return (len(pts), list(pts), 0)


class PropArea:
    def __init__(self, espesores):
        self._e = espesores

    def GetShell(self, nombre, *args):
        e = self._e[nombre]
        return (0, False, "C30", e, e, 0, "", "", 0)


class FrameObj:
    """nombre -> (punto_i, punto_j, seccion)."""

    def __init__(self, marcos):
        self._f = marcos

    def GetNameList(self):
        return (len(self._f), list(self._f), 0)

    def GetPoints(self, nombre, *args):
        pi, pj, _ = self._f[nombre]
        return (pi, pj, 0)

    def GetSection(self, nombre, *args):
        return (self._f[nombre][2], 0)

    def GetLocalAxes(self, nombre, *args):
        return (0.0, False, 0)


class PropFrame:
    def __init__(self, rectangulos):
        self._r = rectangulos

    def GetRectangle(self, nombre, *args):
        t3, t2 = self._r[nombre]
        return ("", "C30", t3, t2, 0, "", "", 0)

    def GetCircle(self, nombre, *args):
        return ("", "", 0.0, 0)


COORDS = {
    "A": (0.0, 0.0, 0.0),
    "B": (1500.0, 0.0, 0.0),
    "E": (3000.0, 0.0, 0.0),
    "C": (1500.0, 3500.0, 0.0),
    "D": (0.0, 3500.0, 0.0),
    "F": (3000.0, 3500.0, 0.0),
    "M": (1500.0, 1750.0, 0.0),
    "Mtop": (1500.0, 1750.0, 3000.0),
    "P5": (5000.0, 0.0, 0.0),
    "P6": (6000.0, 0.0, 0.0),
    "P7": (6000.0, 1000.0, 0.0),
    "P8": (5000.0, 1000.0, 0.0),
    "N9": (9000.0, 9000.0, 0.0),
}
AREAS = {
    "S1": {"pts": ["A", "B", "C", "D"], "seccion": "Z30", "elms": ["E1"]},
    "S2": {"pts": ["B", "E", "F", "C"], "seccion": "Z30", "elms": ["E2"]},
    "S3": {"pts": ["P5", "P6", "P7", "P8"], "seccion": "Z20", "elms": ["E3"]},
}
ELMS = {
    "E1": ["A", "B", "C", "D", "M"],
    "E2": ["B", "E", "F", "C", "M"],
    "E3": ["P5", "P6", "P7", "P8"],
}
GRUPOS = {
    "G_ZAP": ([5, 5, 5], ["S1", "S2", "S3"]),
    "G_NODOS": ([1], ["N9"]),  # sin shells
    "G_ROTO": RuntimeError("fallo simulado al leer asignaciones"),
}
MARCOS = {
    "P1": ("M", "Mtop", "PED400"),  # pedestal vertical
    "T1": ("A", "E", "VIGA"),  # horizontal: no cuenta
}


class SapModelFalso:
    def __init__(self, coords=None, gate=None):
        self.gate = gate
        self.llegado = threading.Event()
        self.Units = Units()
        self.GroupDef = GroupDef(GRUPOS)
        self.PointObj = PointObj(dict(COORDS if coords is None else coords))
        self.AreaObj = AreaObj(self, AREAS)
        self.AreaElm = AreaElm(ELMS)
        self.PropArea = PropArea({"Z30": 300.0, "Z20": 200.0})
        self.FrameObj = FrameObj(MARCOS)
        self.PropFrame = PropFrame({"PED400": (400.0, 400.0)})

    def GetPresentUnits(self):
        return self.Units.GetPresentUnits()

    def SetPresentUnits(self, unidad):
        return self.Units.SetPresentUnits(unidad)


# ------------------------------------------------------ calls falsos --


def call_directo(model):
    """Ejecuta fn(model) en el mismo hilo (el actor no se simula)."""

    def call(fn):
        return fn(model)

    return call


def call_que_vence(model, retardo=0.3):
    """Simula el timeout de 30 s: fn corre después en otro hilo y el llamador
    recibe HTTPException con detalle vacío, como en el puente anfitrión."""

    def call(fn):
        threading.Thread(target=lambda: (time.sleep(retardo), fn(model)), daemon=True).start()
        raise HTTPException(409, "")

    return call


def call_sin_sap(fn):
    raise HTTPException(409, "No active SAP2000 connection. Abra SAP2000 con el modelo cargado.")


def call_nunca_ejecuta(fn):
    """Vence el actor y la tarea nunca llega a ejecutarse."""
    raise HTTPException(409, "")


def cliente_con(call):
    app = FastAPI()
    cad_drwr_sap.install_routes(app, call)
    return TestClient(app)


# ------------------------------------------------------------ ayudas --


def contrato():
    return json.loads(CONTRATO.read_text(encoding="utf-8"))["routes"]


def claves(ruta):
    return sorted(contrato()[f"POST {PREF}{ruta}"]["keys"])


def claves_base_status():
    """Claves de status que siempre están; resultado/error dependen del estado."""
    spec = contrato()[f"POST {PREF}/foundation/status"]
    return sorted(set(spec["keys"]) - set(spec["opcionales"]))


def arrancar(cli, grupo="G_ZAP"):
    r = cli.post(PREF + "/foundation/start", json={"grupo": grupo})
    assert r.status_code == 200, r.text
    return r.json()["job"]


def esperar_fin(cli, job, limite=5.0):
    t0 = time.monotonic()
    while True:
        r = cli.post(PREF + "/foundation/status", json={"job": job})
        assert r.status_code == 200, r.text
        d = r.json()
        if d["estado"] != "en_curso":
            return d
        if time.monotonic() - t0 > limite:
            raise AssertionError(f"el trabajo no terminó: {d}")
        time.sleep(0.01)


def solo_msg(r):
    detalle = r.json()["detail"]
    assert isinstance(detalle, list) and detalle, r.text
    return detalle[0]["msg"]


# ------------------------------------------------------ ModelLink (a) --


def test_model_link_fija_y_restaura_unidades():
    m = SapModelFalso()
    link = ModelLink(m, ControlTrabajo())
    assert link.is_connected is True
    original = link.set_units_mm()
    assert original == 6
    assert m.Units.valor == 9  # N-mm-°C
    link.restore_units(original)
    assert m.Units.valor == 6
    assert m.Units.historial == [9, 6]


def test_model_link_cuenta_operaciones():
    control = ControlTrabajo()
    link = ModelLink(SapModelFalso(), control)
    link.get_sap_model()
    link.get_sap_model()
    assert control.hechas == 2


def test_model_link_cancelacion_lanza_y_la_restauracion_sigue():
    m = SapModelFalso()
    control = ControlTrabajo()
    link = ModelLink(m, control)
    m.Units.valor = 9  # como tras set_units_mm
    control.cancelar()
    with pytest.raises(TrabajoCancelado):
        link.get_sap_model()
    assert control.hechas == 0
    link.restore_units(6)  # debe ejecutarse igual
    assert m.Units.valor == 6


def test_trabajo_cancelado_no_se_traga_con_except_exception():
    assert not issubclass(TrabajoCancelado, Exception)


# ------------------------------------------- rutas con call directo (b) --


def test_groups_solo_grupos_con_shells_y_tolera_un_grupo_roto():
    cli = cliente_con(call_directo(SapModelFalso()))
    r = cli.post(PREF + "/groups", json={})
    assert r.status_code == 200, r.text
    assert r.json() == {"grupos": [{"nombre": "G_ZAP", "n_shells": 3}]}
    assert sorted(r.json()) == claves("/groups")


def test_flujo_feliz_dos_zapatas_contorno_y_pedestal():
    cli = cliente_con(call_directo(SapModelFalso()))
    job = arrancar(cli)
    d = esperar_fin(cli, job)
    assert d["estado"] == "listo", d
    assert d["etapa"] == "finalizado"
    assert d["total"] is None
    assert d["hechas"] > 0
    assert sorted(d) == sorted(claves_base_status() + ["resultado"])

    zapatas = d["resultado"]["zapatas"]
    assert d["resultado"]["nombre"] == "G_ZAP"
    assert len(zapatas) == 2

    fusionada, aislada = zapatas
    assert fusionada["nombre"] == "P1"  # nombrada por su pedestal
    assert len(fusionada["areas"]) == 2
    assert {a["espesor"] for a in fusionada["areas"]} == {300.0}
    # Contorno exterior de 4 esquinas reales (sin B ni C colineales).
    assert len(fusionada["contorno"]) == 4
    assert {tuple(p) for p in fusionada["contorno"]} == {
        (0.0, 0.0),
        (3000.0, 0.0),
        (3000.0, 3500.0),
        (0.0, 3500.0),
    }

    assert len(fusionada["pedestales"]) == 1
    pd = fusionada["pedestales"][0]
    assert pd["frame"] == "P1"
    assert pd["largo"] == 400.0 and pd["ancho"] == 400.0
    assert pd["centro"] == [1500.0, 1750.0]
    assert pd["punto_pie"] == "M"
    assert pd["aproximado"] is False

    assert aislada["nombre"] == "F2"
    assert aislada["pedestales"] == []
    assert aislada["areas"][0]["espesor"] == 200.0
    assert len(aislada["contorno"]) == 4


def test_timeout_del_actor_la_tarea_sigue_y_queda_listo():
    cli = cliente_con(call_que_vence(SapModelFalso(), retardo=0.3))
    job = arrancar(cli)
    d = cli.post(PREF + "/foundation/status", json={"job": job}).json()
    assert d["estado"] == "en_curso"
    assert d["etapa"] == "leyendo"
    fin = esperar_fin(cli, job)
    assert fin["estado"] == "listo", fin
    assert len(fin["resultado"]["zapatas"]) == 2


def test_espera_del_actor_vencida_da_error(monkeypatch):
    monkeypatch.setattr(cad_drwr_sap, "ESPERA_TIMEOUT_S", 0.2)
    cli = cliente_con(call_nunca_ejecuta)
    fin = esperar_fin(cli, arrancar(cli))
    assert fin["estado"] == "error"
    assert "no terminó en 0.2 s" in fin["error"]


def test_falta_de_conexion_da_error_con_el_texto_real():
    cli = cliente_con(call_sin_sap)
    fin = esperar_fin(cli, arrancar(cli))
    assert fin["estado"] == "error"
    assert fin["error"].startswith("No active SAP2000 connection.")
    assert sorted(fin) == sorted(claves_base_status() + ["error"])


def test_error_de_la_lectura_muestra_el_mensaje_real():
    cli = cliente_con(call_directo(SapModelFalso()))
    fin = esperar_fin(cli, arrancar(cli, grupo="G_NODOS"))
    assert fin["estado"] == "error"
    assert fin["error"] == "El grupo 'G_NODOS' no tiene shells asignados."


def test_resultado_no_serializable_a_json_es_error():
    coords = dict(COORDS)
    coords["P5"] = (float("nan"), 0.0, 0.0)  # llega al contorno de F2
    cli = cliente_con(call_directo(SapModelFalso(coords=coords)))
    fin = esperar_fin(cli, arrancar(cli))
    assert fin["estado"] == "error"
    assert fin["error"].startswith("El resultado no es JSON válido")
    assert "resultado" not in fin


def test_cancelacion_cooperativa_restaura_unidades():
    gate = threading.Event()
    m = SapModelFalso(gate=gate)
    cli = cliente_con(call_directo(m))
    job = arrancar(cli)
    assert m.llegado.wait(5), "la lectura no llegó a la operación de bloqueo"
    r = cli.post(PREF + "/foundation/cancel", json={"job": job})
    assert r.status_code == 200 and r.json() == {"cancelado": True}
    gate.set()
    fin = esperar_fin(cli, job)
    assert fin["estado"] == "cancelado"
    assert fin["hechas"] >= 1
    assert "error" not in fin and "resultado" not in fin
    assert m.Units.historial == [9, 6]  # restaurada pese a cancelar
    assert m.Units.valor == 6


def test_segundo_trabajo_concurrente_409_y_luego_se_puede_iniciar():
    gate = threading.Event()
    m = SapModelFalso(gate=gate)
    cli = cliente_con(call_directo(m))
    job = arrancar(cli)
    assert m.llegado.wait(5)
    r = cli.post(PREF + "/foundation/start", json={"grupo": "G_ZAP"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Ya hay una lectura de SAP2000 en curso"
    gate.set()
    assert esperar_fin(cli, job)["estado"] == "listo"
    assert arrancar(cli)  # ya no hay activo


def test_job_desconocido_409():
    cli = cliente_con(call_directo(SapModelFalso()))
    for ruta, cuerpo in (("/foundation/status", {"job": "nope"}), ("/foundation/cancel", {"job": "nope"})):
        r = cli.post(PREF + ruta, json=cuerpo)
        assert r.status_code == 409
        assert r.json()["detail"] == "El trabajo no existe o venció"


def test_cancelar_trabajo_terminado_409():
    cli = cliente_con(call_directo(SapModelFalso()))
    job = arrancar(cli)
    esperar_fin(cli, job)
    r = cli.post(PREF + "/foundation/cancel", json={"job": job})
    assert r.status_code == 409
    assert r.json()["detail"] == ("El trabajo ya terminó (estado: listo); no se puede cancelar")


def test_trabajo_terminado_vence_tras_el_ttl(monkeypatch):
    cli = cliente_con(call_directo(SapModelFalso()))
    job = arrancar(cli)
    assert esperar_fin(cli, job)["estado"] == "listo"
    monkeypatch.setattr(cad_drwr_sap, "TTL_TRABAJO_S", 0.0)
    time.sleep(0.01)
    r = cli.post(PREF + "/foundation/status", json={"job": job})
    assert r.status_code == 409
    assert r.json()["detail"] == "El trabajo no existe o venció"


def test_groups_con_vencimiento_del_actor_da_409_con_texto():
    cli = cliente_con(call_nunca_ejecuta)
    r = cli.post(PREF + "/groups", json={})
    assert r.status_code == 409
    assert "SAP2000 no respondió a tiempo" in r.json()["detail"]


def test_entrada_invalida_422_en_espanol():
    cli = cliente_con(call_directo(SapModelFalso()))
    r = cli.post(PREF + "/foundation/start", json={"grupo": ""})
    assert r.status_code == 422
    assert "Texto demasiado corto" in solo_msg(r)
    r = cli.post(PREF + "/foundation/start", json={"grupo": "G", "x": 1})
    assert r.status_code == 422
    assert solo_msg(r) == "Campo no admitido"
    r = cli.post(PREF + "/foundation/status", json={"job": "a" * 65})
    assert r.status_code == 422


# ----------------------------------------- integración desde cad_drwr (c) --


def test_install_routes_monta_sap_solo_con_call():
    sin_call = FastAPI()
    cad_drwr.install_routes(sin_call)
    r = TestClient(sin_call).post(PREF + "/groups", json={})
    assert r.status_code == 404

    con_call = FastAPI()
    cad_drwr.install_routes(con_call, call_directo(SapModelFalso()))
    assert TestClient(con_call).post(PREF + "/groups", json={}).status_code == 200


def test_contrato_sap_coincide_con_las_claves_reales():
    gate = threading.Event()
    m = SapModelFalso(gate=gate)
    con_call = FastAPI()
    cad_drwr.install_routes(con_call, call_directo(m))
    cli = TestClient(con_call)

    rutas_sap = {
        f"POST {ruta}"
        for ruta, ops in con_call.openapi()["paths"].items()
        if ruta.startswith(PREF) and "post" in ops
    }
    assert rutas_sap == {r for r in contrato() if "/cad/sap/" in r}

    assert sorted(cli.post(PREF + "/groups", json={}).json()) == claves("/groups")

    job = cli.post(PREF + "/foundation/start", json={"grupo": "G_ZAP"}).json()
    assert sorted(job) == claves("/foundation/start")
    assert m.llegado.wait(5)

    en_curso = cli.post(PREF + "/foundation/status", json={"job": job["job"]}).json()
    assert sorted(en_curso) == claves_base_status()

    cancel = cli.post(PREF + "/foundation/cancel", json={"job": job["job"]}).json()
    assert sorted(cancel) == claves("/foundation/cancel")
    gate.set()
    cancelado = esperar_fin(cli, job["job"])
    assert cancelado["estado"] == "cancelado"
    assert sorted(cancelado) == claves_base_status()

    listo = esperar_fin(cli, arrancar(cli))  # segundo trabajo, sin bloqueo
    assert listo["estado"] == "listo"
    assert sorted(listo) == sorted(claves_base_status() + ["resultado"])
