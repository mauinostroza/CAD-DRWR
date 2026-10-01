"""Renderiza detalles y reabre todos los DXF para revisión local."""
import os
import sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication
from generators import MODULES
from app.preview import PreviewWidget
from cad.dxf_out import write_dxf
import ezdxf

app = QApplication.instance() or QApplication([])
target = ROOT / "samples"
target.mkdir(exist_ok=True)
for module in MODULES:
    if not hasattr(module.panel, "SPEC"):
        continue
    panel = module.panel()
    drawing = module.builder(panel.params())
    path = target / (module.prefix + ".dxf")
    write_dxf(drawing, str(path))
    if ezdxf.readfile(path).audit().has_errors:
        raise RuntimeError(str(path))
    preview = PreviewWidget()
    preview.resize(1600, 1100)
    preview.set_drawing(drawing)
    preview.fit()
    preview.grab_png(str(target / (module.prefix + ".png")))
    print(module.prefix, "DXF auditado y preview renderizada")
