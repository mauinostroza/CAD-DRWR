"""Genera las muestras PG y pedestal con los parámetros reales de la interfaz.

Uso: QT_QPA_PLATFORM=offscreen python scripts/render_reference_details.py
Requiere las dependencias de requirements.txt; no inicia workflows ni CAD.
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from app.preview import PreviewWidget
from cad.dxf_out import write_dxf
from generators.anchor_bolt import AnchorBoltPanel, build_anchor_bolt
from generators.pedestal import PedestalPanel, build_pedestal
import ezdxf


def main():
    app = QApplication.instance() or QApplication([])
    pg = AnchorBoltPanel()
    pedestal = PedestalPanel()
    pedestal.w["preset"].setCurrentText("Referencia 20")
    target = ROOT / "samples"
    for name, builder, panel in (("pg_referencia", build_anchor_bolt, pg),
                                 ("pedestal_referencia", build_pedestal, pedestal)):
        drawing = builder(panel.params())
        path = target / (name + ".dxf")
        write_dxf(drawing, str(path))
        reopened = ezdxf.readfile(path)
        if reopened.audit().has_errors:
            raise RuntimeError(f"DXF inválido: {path}")
        widget = PreviewWidget()
        widget.resize(1500, 1000)
        widget.set_drawing(drawing)
        widget.fit()
        widget.grab_png(str(target / (name + ".png")))
        print(f"{name}: {len(drawing.ents)} entidades, DXF auditado OK")


if __name__ == "__main__":
    main()
