"""Arnés de pruebas: el workbench aporta ``backend.auth``; aquí se simula."""

import pathlib
import sys
import types

RAIZ = pathlib.Path(__file__).resolve().parents[1]
for ruta in (RAIZ, RAIZ / "scripts"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

if "backend.auth" not in sys.modules:
    try:
        import backend.auth  # noqa: F401
    except ImportError:
        mod = types.ModuleType("backend.auth")

        def require_user():
            return types.SimpleNamespace(id=1, email="test@example.com", display_name="Test")

        mod.require_user = require_user
        sys.modules["backend.auth"] = mod


# `bridge.actions` es del workbench: el arnés usa un sustituto con `split_return`.
try:
    import bridge.actions  # noqa: F401
except ImportError:
    import _stub_bridge_actions

    sys.modules["bridge.actions"] = _stub_bridge_actions
