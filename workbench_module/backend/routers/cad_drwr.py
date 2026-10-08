"""Router del módulo CAD-DRWR (StructGenCAD): dibujos de detalles estructurales.

Prefijo ``/cad_drwr``. El cálculo es barato y sin estado; el dibujo viaja como
JSON (primitivas para SVG y entidades para el CAD). La conexión con
ZWCAD/AutoCAD/SAP2000 NO pasa por aquí: la hace el puente local.
"""

import hashlib
import io
import json
import tempfile
import zipfile
from collections import OrderedDict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.auth import require_user
from backend.motor_calculo.cad_drwr import serializar
from backend.motor_calculo.cad_drwr.generators import MODULOS, campos, defaults
from backend.motor_calculo.cad_drwr.servicio import (
    MAX_PUNTOS, MAX_ZAPATAS, ErrorDibujo, construir, solapes)

router = APIRouter(prefix="/cad_drwr", tags=["cad_drwr"], dependencies=[Depends(require_user)])

MOTOR_ID = "cad_drwr@structgencad"
MAX_LOTE = 7
_CACHE_MAX = 64
_cache: "OrderedDict[str, dict]" = OrderedDict()


class _Base(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")


class LaminaIn(_Base):
    activa: bool = False
    proyecto: str = Field("", max_length=200)
    numero_plano: str = Field("", max_length=100)
    revision: str = Field("", max_length=50)


class DibujoIn(_Base):
    modulo: str = Field(max_length=50)
    params: dict = Field(default_factory=dict)
    lamina: LaminaIn | None = None


class ItemLote(_Base):
    modulo: str = Field(max_length=50)
    params: dict = Field(default_factory=dict)


class LoteIn(_Base):
    items: list[ItemLote] = Field(min_length=1, max_length=MAX_LOTE)
    lamina: LaminaIn | None = None


def _ezdxf_ok() -> bool:
    try:
        import ezdxf  # noqa: F401
        return True
    except ImportError:
        return False


def _construir(modulo, params, lamina):
    try:
        return construir(modulo, params, lamina.model_dump() if lamina else None)
    except ErrorDibujo as exc:
        raise HTTPException(422, str(exc)) from exc


def _clave(modulo, params, lamina):
    raw = json.dumps([modulo, params, lamina.model_dump() if lamina else None],
                     sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


@router.get("/estado")
def estado() -> dict:
    dxf = _ezdxf_ok()
    return {
        "disponible": True,
        "detalle": "" if dxf else "Falta ezdxf: la vista previa funciona, la exportación DXF no.",
        "motor": MOTOR_ID,
        "dxf": dxf,
        "limites": {"entidades": serializar.MAX_ENTIDADES, "zapatas": MAX_ZAPATAS,
                    "puntos": MAX_PUNTOS, "lote_zip": MAX_LOTE},
    }


@router.get("/modulos")
def modulos() -> list[dict]:
    return [{"id": m.id, "nombre": m.nombre, "campos": campos(m.spec),
             "defaults": defaults(m), "interactivo": m.interactivo} for m in MODULOS]


@router.post("/dibujo")
def dibujo(datos: DibujoIn) -> dict:
    clave = _clave(datos.modulo, datos.params, datos.lamina)
    if clave in _cache:
        _cache.move_to_end(clave)
        return _cache[clave]
    dwg, p = _construir(datos.modulo, datos.params, datos.lamina)
    out = serializar.dibujo_a_json(dwg)
    out.update({"modulo": datos.modulo, "hash": clave, "solapes": solapes(dwg)})
    _cache[clave] = out
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return out


def _dxf_bytes(dwg) -> bytes:
    if not _ezdxf_ok():
        raise HTTPException(503, "Falta ezdxf en el servidor: no se puede exportar DXF.")
    from backend.motor_calculo.cad_drwr.dxf_out import write_dxf
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "dibujo.dxf"
        write_dxf(dwg, str(ruta))
        return ruta.read_bytes()


@router.post("/dxf")
def dxf(datos: DibujoIn) -> Response:
    dwg, _ = _construir(datos.modulo, datos.params, datos.lamina)
    return Response(_dxf_bytes(dwg), media_type="application/dxf",
                    headers={"Content-Disposition": f'attachment; filename="{datos.modulo}.dxf"'})


@router.post("/dxf-lote")
def dxf_lote(datos: LoteIn) -> Response:
    buf = io.BytesIO()
    errores = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for it in datos.items:
            try:
                dwg, _ = construir(it.modulo, it.params,
                                   datos.lamina.model_dump() if datos.lamina else None)
                zf.writestr(f"{it.modulo}.dxf", _dxf_bytes(dwg))
            except ErrorDibujo as exc:
                errores.append(f"{it.modulo}: {exc}")
        if errores:
            zf.writestr("ERRORES.txt", "\n".join(errores))
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="detalles_dxf.zip"'})
