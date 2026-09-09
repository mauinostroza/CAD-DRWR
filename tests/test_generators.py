# -*- coding: utf-8 -*-
import math
import unittest

from core.bounds import drawing_bounds
from core.ir import Dim, Leader, Line, Poly, Table, Text
from core.geom import stirrup_pts
from generators.foundation_sap import build_foundation
from generators import MODULES
from generators.data import factor_escala


def default_params(panel_class):
    params = {}
    for row in panel_class.SPEC:
        key, kind = row[0], row[2]
        if kind == "combo":
            params[key] = row[4]
        elif kind in ("int", "float"):
            params[key] = row[5]
        elif kind == "chk":
            params[key] = row[3]
    params["_escala"] = factor_escala(params.get("escala", "1:50"))
    return params


class GeneratorSmokeTests(unittest.TestCase):
    def test_all_default_drawings_have_valid_bounds(self):
        for module in MODULES:
            with self.subTest(module=module.nombre):
                drawing = module.builder(default_params(module.panel))
                bounds = drawing_bounds(drawing)
                self.assertIsNotNone(bounds)
                self.assertTrue(all(math.isfinite(v) for v in bounds))
                self.assertGreater(bounds[2], bounds[0])
                self.assertGreater(bounds[3], bounds[1])

    def test_slab_spacing_labels_have_correct_units(self):
        slab = next(m for m in MODULES if m.prefix == "losa")
        drawing = slab.builder(default_params(slab.panel))
        labels = [e.s for e in drawing.ents if isinstance(e, (Leader, Text))]
        spacing = [s for s in labels if "c/" in s]
        self.assertTrue(spacing)
        self.assertTrue(all(" cm " in s for s in spacing))
        self.assertTrue(all(" m " not in s for s in spacing))

    def test_long_pedestal_uses_graphical_break(self):
        pedestal = next(m for m in MODULES if m.prefix == "pedestal")
        params = default_params(pedestal.panel)
        params["H"] = 600
        drawing = pedestal.builder(params)
        height = drawing_bounds(drawing)[3] - drawing_bounds(drawing)[1]
        self.assertLess(height, 3500)

    def test_stirrup_closes_contour_with_centered_inward_hooks(self):
        pts = stirrup_pts(220, 320, 8, 20)
        perimeter = pts[1:-1]
        self.assertEqual(min(x for x, _ in perimeter), 0)
        self.assertEqual(max(x for x, _ in perimeter), 220)
        self.assertEqual(min(y for _, y in perimeter), 0)
        self.assertEqual(max(y for _, y in perimeter), 320)
        # Ambos extremos quedan dentro del estribo y el cierre en la cara.
        self.assertLess(pts[0][0], 220)
        self.assertLess(pts[-1][0], 220)
        self.assertEqual(pts[1][0], 220)
        self.assertEqual(pts[-2][0], 220)

    def test_pg_bolt_has_fabrication_table_and_square_washer(self):
        bolt = next(m for m in MODULES if m.prefix == "perno_anclaje")
        params = default_params(bolt.panel)
        drawing = bolt.builder(params)
        tables = [e for e in drawing.ents if isinstance(e, Table)]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].title, 'PERNO TIPO "PG"')
        symbols = [row[1] for row in tables[0].rows]
        self.assertEqual(symbols, ["d", "", "h1", "h2", "W", "t", "b",
                                   "R", "P", "L", ""])
        self.assertTrue(any(isinstance(e, Poly) and e.layer == "ACERO"
                            and e.closed for e in drawing.ents))

    def test_foundation_views_are_identified_and_dimensioned(self):
        """Las referencias de corte deben corresponder a las elevaciones."""
        params = {
            "_escala": 5.0,
            "espesor_default": 400.0,
            "_geom": {"zapatas": [{
                "nombre": "F-01",
                "contorno": [(0, 0, 0), (3000, 0, 0),
                             (3000, 2200, 0), (0, 2200, 0)],
                "pedestales": [{"centro": (1500, 1100), "largo": 500,
                                "ancho": 400, "largo_en_x": True,
                                "frame": "C1", "aproximado": False}],
                "areas": [{"pts": [(0, 0, 0), (3000, 0, 0),
                                    (3000, 2200, 0), (0, 2200, 0)],
                           "espesor": 400, "seccion": "Z-400"}],
            }]},
        }
        drawing = build_foundation(params)
        labels = [e.s for e in drawing.ents if isinstance(e, Text)]
        self.assertIn("F-01 — PLANTA", labels)
        self.assertTrue(any("CORTE A-A" in s for s in labels))
        self.assertTrue(any("CORTE B-B" in s for s in labels))
        self.assertGreaterEqual(sum(isinstance(e, Dim) for e in drawing.ents),
                                6)
        # Dos ejes de corte se dibujan antes de exportar, no solo como texto.
        self.assertGreaterEqual(sum(isinstance(e, Line) and e.layer == "EJE"
                                     for e in drawing.ents), 2)


if __name__ == "__main__":
    unittest.main()
