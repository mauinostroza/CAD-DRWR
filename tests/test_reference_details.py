"""Casos de referencia entregados por el usuario: PG y pedestal armado."""
import math
import tempfile
import unittest
from pathlib import Path

import ezdxf

from cad.dxf_out import write_dxf
from core import ir
from core.geom import dist, poly_bar, stirrup_pts
from generators.anchor_bolt import build_anchor_bolt
from generators.pedestal import _bar_layout, _perimeter_bars, build_pedestal


PG_REF = {
    "d_perno": 25.4, "d_nominal": "1 in", "tipo": "PG (recto con golilla)",
    "Le": 850, "P": 400, "h1": 150, "h2": 75, "W": 75,
    "t_golilla": 20, "b_golilla": 50, "tipo_hilo": "8UN", "n": 48,
    "material": "A307", "tabla": True, "escala": "1:25", "_escala": 2.5,
}


class ReferenceDetailTests(unittest.TestCase):
    def test_poly_bar_has_exact_arc_tangencies_or_rejects_short_geometry(self):
        pts = stirrup_pts(220, 320, 8, 20)
        ents, _ = poly_bar(pts, 8, 20)
        arcs = [e for e in ents if isinstance(e, ir.Arc)]
        lines = [e for e in ents if isinstance(e, ir.Line)]
        self.assertEqual(len(arcs), 5)
        for arc in arcs:
            p1 = (arc.c[0] + arc.r * math.cos(math.radians(arc.a1)),
                  arc.c[1] + arc.r * math.sin(math.radians(arc.a1)))
            p2 = (arc.c[0] + arc.r * math.cos(math.radians(arc.a2)),
                  arc.c[1] + arc.r * math.sin(math.radians(arc.a2)))
            self.assertAlmostEqual(dist(arc.c, p1), arc.r, places=7)
            self.assertAlmostEqual(dist(arc.c, p2), arc.r, places=7)
            self.assertTrue(any(dist(q, p1) < 1e-7 or dist(q, p2) < 1e-7
                                for line in lines for q in (line.p1, line.p2)))
        with self.assertRaises(ValueError):
            poly_bar([(0, 0), (8, 0), (8, 8)], 16, 40)

    def test_reference_pedestal_has_twenty_bars_and_closed_inner_lacing(self):
        layout = _bar_layout({"preset": "Referencia 20"}, 8)
        bars = _perimeter_bars(220, 145, layout)
        self.assertEqual(layout, {"top": 7, "bottom": 7, "left": 3, "right": 3})
        self.assertEqual(len(bars), 20)
        p = {"b": 55, "h": 40, "H": 250, "r": 4, "n_barras": "8",
             "preset": "Referencia 20", "lazos_interiores": True,
             "d_barra": 18, "d_estribo": 8, "e_estribo": 15,
             "elevacion": True, "ancho_zap": 130, "alto_zap": 30,
             "traslape": 45, "largo_barra": 3.2, "escala": "1:25", "_escala": 2.5}
        drawing = build_pedestal(p)
        circles = [e for e in drawing.ents if isinstance(e, ir.Circle) and e.filled]
        self.assertEqual(len(circles), 20)
        labels = [e.s for e in drawing.ents if isinstance(e, ir.Leader)]
        self.assertTrue(any("ARRANQUES 20Ø" in s for s in labels))

    def test_pg_reference_uses_all_parameters_in_table_and_writes_clean_dxf(self):
        drawing = build_anchor_bolt(PG_REF)
        table = next(e for e in drawing.ents if isinstance(e, ir.Table))
        self.assertTrue(table.title_boxed)
        self.assertEqual(table.rows[-1], ["CANTIDAD TOTAL", "n", "48"])
        self.assertEqual(table.rows[0][-1], '1"')
        dims = [e.txt for e in drawing.ents if isinstance(e, ir.Dim)]
        self.assertEqual(set(["d", "h1", "h2", "W", "t", "b"]) - set(dims), set())
        texts = [e.s for e in drawing.ents if isinstance(e, ir.Leader)]
        self.assertTrue(any("SOLDADURA" in s for s in texts))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pg.dxf"
            write_dxf(drawing, str(path))
            doc = ezdxf.readfile(path)
            self.assertFalse(doc.audit().has_errors)
            self.assertEqual(len(doc.modelspace().query("DIMENSION")), len(dims))


if __name__ == "__main__":
    unittest.main()
