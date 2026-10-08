import io
import json
import zipfile

import pytest
from backend.auth import require_user  # noqa: E402
from backend.routers import cad_drwr as r
from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()
app.include_router(r.router)
# En el workbench `require_user` exige sesión: se sustituye por un usuario de prueba.
app.dependency_overrides[require_user] = lambda: type(
    "U", (), {"id": 1, "email": "t@e.st", "display_name": "T"}
)()
cl = TestClient(app)


def geom():
    z = {
        "nombre": "F1",
        "areas": [
            {
                "nombre": "A1",
                "seccion": "S",
                "espesor": 400.0,
                "pts_nombres": ["1", "2", "3", "4"],
                "pts": [[0, 0, 0], [3000, 0, 0], [3000, 3500, 0], [0, 3500, 0]],
            }
        ],
        "contorno": [[0, 0], [3000, 0], [3000, 3500], [0, 3500]],
        "pedestales": [
            {
                "frame": "C1",
                "largo": 400.0,
                "ancho": 400.0,
                "largo_en_x": True,
                "centro": [1500, 1750],
                "punto_pie": "M1",
            }
        ],
    }
    return {"nombre": "G1", "zapatas": [z]}


def test_estado_y_modulos():
    e = cl.get("/cad_drwr/estado").json()
    assert e["disponible"] and e["limites"]["entidades"] == 20000
    ms = cl.get("/cad_drwr/modulos").json()
    assert [m["id"] for m in ms] == [
        "placa_base",
        "pedestal",
        "losa",
        "perno_anclaje",
        "perfil",
        "forma_barra",
        "fundacion_sap",
    ]
    assert ms[-1]["interactivo"] and ms[0]["campos"] and ms[0]["defaults"]["_escala"] == 5.0


@pytest.mark.parametrize("mid", ["placa_base", "pedestal", "losa", "perno_anclaje", "perfil", "forma_barra"])
def test_dibujo_defaults(mid):
    d = cl.post("/cad_drwr/dibujo", json={"modulo": mid}).json()
    assert d["n_render"] > 10 and d["bounds"] and d["th"] > 0
    assert d["hash"] and d["modulo"] == mid


def test_cache_devuelve_lo_mismo():
    a = cl.post("/cad_drwr/dibujo", json={"modulo": "losa"}).json()
    b = cl.post("/cad_drwr/dibujo", json={"modulo": "losa"}).json()
    assert a == b


def test_422_parametros_invalidos():
    assert cl.post("/cad_drwr/dibujo", json={"modulo": "x"}).status_code == 422
    assert (
        cl.post("/cad_drwr/dibujo", json={"modulo": "placa_base", "params": {"t": 99999}}).status_code == 422
    )
    assert cl.post("/cad_drwr/dibujo", json={"modulo": "placa_base", "extra": 1}).status_code == 422


def test_fundacion_sin_geometria_es_422_en_castellano():
    x = cl.post("/cad_drwr/dibujo", json={"modulo": "fundacion_sap"})
    assert x.status_code == 422 and "SAP2000" in x.json()["detail"]


def test_fundacion_con_geometria():
    d = cl.post("/cad_drwr/dibujo", json={"modulo": "fundacion_sap", "params": {"_geom": geom()}}).json()
    assert d["n_render"] > 20


def test_fundacion_geometria_invalida():
    g = geom()
    g["zapatas"][0]["contorno"][0] = [float("nan") if False else 1e12, 0]
    x = cl.post("/cad_drwr/dibujo", json={"modulo": "fundacion_sap", "params": {"_geom": g}})
    assert x.status_code == 422
    g2 = geom()
    g2["zapatas"] = g2["zapatas"] * 300
    assert (
        cl.post("/cad_drwr/dibujo", json={"modulo": "fundacion_sap", "params": {"_geom": g2}}).status_code
        == 422
    )


def test_lamina_agrega_marco():
    base = cl.post("/cad_drwr/dibujo", json={"modulo": "perfil"}).json()
    lam = cl.post(
        "/cad_drwr/dibujo", json={"modulo": "perfil", "lamina": {"activa": True, "proyecto": "P"}}
    ).json()
    assert lam["n_render"] > base["n_render"]


def test_dxf_y_lote():
    pytest.importorskip("ezdxf")
    x = cl.post("/cad_drwr/dxf", json={"modulo": "perfil"})
    assert x.status_code == 200 and x.content.startswith(b"  0") or b"SECTION" in x.content[:200]
    z = cl.post("/cad_drwr/dxf-lote", json={"items": [{"modulo": "perfil"}, {"modulo": "fundacion_sap"}]})
    nombres = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert "perfil.dxf" in nombres and "ERRORES.txt" in nombres
    assert cl.post("/cad_drwr/dxf-lote", json={"items": []}).status_code == 422


def test_json_sin_nan():
    t = cl.post(
        "/cad_drwr/dibujo",
        content=json.dumps({"modulo": "perfil", "params": {"d": float("nan")}}),
        headers={"content-type": "application/json"},
    )
    assert t.status_code == 422
