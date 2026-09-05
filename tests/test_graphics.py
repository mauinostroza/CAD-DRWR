# -*- coding: utf-8 -*-
import unittest

from core.bounds import drawing_bounds, entity_bounds
from core.dims import dim_parts
from core.ir import Dim, Drawing, Leader, Line, Table, Text
from core.labels import rebar_spacing


class GraphicBoundsTests(unittest.TestCase):
    def test_leader_bounds_include_shelf_and_label(self):
        leader = Leader((0, 0), (10, 10), "TEXTO LARGO", 5,
                        shelf=20, side=1)
        x0, y0, x1, y1 = entity_bounds(leader)
        self.assertLessEqual(x0, 0)
        self.assertGreater(x1, 30)
        self.assertGreater(y1, 10)

    def test_drawing_bounds_include_text_width(self):
        drawing = Drawing(ents=[Line((0, 0), (10, 0)),
                                Text((10, 0), "ANOTACIÓN", 5, ha="l")])
        self.assertGreater(drawing_bounds(drawing)[2], 35)

    def test_table_bounds_include_title(self):
        table = Table((0, 0), [20, 20], 15, ["A", "B"], [["1", "2"]],
                      "CUADRO", 5)
        self.assertGreater(entity_bounds(table)[3], 0)


class DimensionTests(unittest.TestCase):
    def test_narrow_dimension_extends_line_outside(self):
        dim = Dim((0, 0), (8, 0), (4, -10), txt="8")
        parts = dim_parts(dim, 10)
        horizontal = [e for e in parts if isinstance(e, Line)
                      and e.p1[1] == -10 and e.p2[1] == -10]
        self.assertTrue(any(e.p1[0] < 0 and e.p2[0] > 8 for e in horizontal))


class LabelTests(unittest.TestCase):
    def test_rebar_spacing_uses_centimetres(self):
        self.assertEqual(rebar_spacing(12, 200, "inferior"),
                         "Ø12 c/20.0 cm (INFERIOR)")
        self.assertNotIn("20.0 m", rebar_spacing(12, 200, "inferior"))


if __name__ == "__main__":
    unittest.main()
