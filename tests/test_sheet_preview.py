import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow
from core import ir
from core.sheet import compose_sheet
from cad.dxf_out import write_dxf
import ezdxf


class SheetPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_edit_keeps_camera_and_invalid_input_clears_geometry(self):
        w = MainWindow()
        w.preview.center, w.preview.scale = (123, 456), .7
        w.refresh()
        self.assertEqual(w.preview.center, (123, 456))
        self.assertEqual(w.preview.scale, .7)
        w.panels[0].w["g"].setValue(1200)
        w.refresh()
        self.assertFalse(w.preview.dwg.ents)
        w.close()

    def test_sheet_keeps_metadata_and_native_dimensions_in_dxf(self):
        d = ir.Drawing(ents=[ir.rect(-100, -50, 100, 50),
                            ir.Dim((-100,0),(100,0),(0,70),text_height=5)])
        sheet = compose_sheet(d, project="Proyecto A", number="E-01", revision="B")
        notes = "\n".join(e.s for e in sheet.ents if isinstance(e, ir.Text))
        self.assertIn("Proyecto A", notes)
        self.assertIn("E-01", notes)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sheet.dxf"
            write_dxf(sheet, str(path))
            doc = ezdxf.readfile(path)
            self.assertFalse(doc.audit().has_errors)
            self.assertEqual(len(doc.modelspace().query("DIMENSION")), 1)
