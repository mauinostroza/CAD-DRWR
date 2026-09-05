# -*- coding: utf-8 -*-
import math
import unittest

from core.bounds import drawing_bounds
from core.ir import Leader, Text
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


if __name__ == "__main__":
    unittest.main()
