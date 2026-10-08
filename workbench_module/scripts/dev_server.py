"""Servidor de desarrollo del arnés: monta el router /cad_drwr bajo /api con auth simulada.

Uso: PYTHONPATH=workbench_module python workbench_module/scripts/dev_server.py [puerto]
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))
import conftest  # noqa: E402,F401  (simula backend.auth)

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from backend.routers import cad_drwr  # noqa: E402

app = FastAPI()
app.include_router(cad_drwr.router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
