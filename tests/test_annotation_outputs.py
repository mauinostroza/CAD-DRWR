"""Regresiones de fidelidad entre anotaciones IR, DXF y COM."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import ezdxf

from core import ir
from core.annotations import expand_annotations, leader_parts, table_parts
from core.dims import DimBuilder, dim_parts
from cad.com_live import _aplanar, _dim
from cad.dxf_out import write_dxf


class AnnotationOutputTests(unittest.TestCase):
    def test_dimension_keeps_own_height_with_large_title_and_translation(self):
        ents = [ir.Text((0, 50), 'TÍTULO', 30)]
        DimBuilder(ents, 3).h_total(0, 25, 0, -10, ext_from=2)
        self.assertEqual(len(ents), 2)  # sin líneas testigo duplicadas
        dim = ents[-1]
        self.assertEqual(dim.p1, (0, 2))
        self.assertEqual([e.h for e in dim_parts(dim, 30)
                          if isinstance(e, ir.Text)], [3])
        drawing = ir.translate(ir.Drawing(ents=ents), 500, 200)
        self.assertEqual(drawing.ents[-1].text_height, 3)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dim.dxf'
            write_dxf(drawing, str(path))
            doc = ezdxf.readfile(path)
            dim_dxf = doc.modelspace().query('DIMENSION')[0]
            self.assertEqual(dim_dxf.override().get('dimtxt'), 3)
            self.assertFalse(doc.audit().has_errors)

    def test_table_header_is_inside_header_row_in_both_exports(self):
        tb = ir.Table((0, 0), [60, 30], 12, ['NOMBRE', 'VALOR'],
                      [['dato', '12']], 'TÍTULO', 3,
                      title_boxed=True, col_align=['l', 'c'])
        drawing = ir.Drawing(ents=[tb])
        parts = list(expand_annotations(drawing.ents))
        self.assertEqual(parts, _aplanar(drawing))
        header = next(e for e in parts if isinstance(e, ir.Text) and e.s == 'NOMBRE')
        data = next(e for e in parts if isinstance(e, ir.Text) and e.s == 'dato')
        self.assertEqual(header.pos[1], -18)
        self.assertEqual(data.pos[1], -30)
        self.assertEqual(data.ha, 'l')
        shifted = ir.translate(drawing, 100, 0).ents[0]
        self.assertTrue(shifted.title_boxed)
        self.assertEqual(shifted.col_align, ['l', 'c'])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'table.dxf'
            write_dxf(drawing, str(path))
            doc = ezdxf.readfile(path)
            exported = {e.dxf.text: e for e in doc.modelspace().query('TEXT')}
            self.assertEqual(exported['NOMBRE'].dxf.align_point.y, -18)
            self.assertEqual(exported['dato'].dxf.align_point.y, -30)

    def test_leader_has_arrow_and_same_text_position_after_com_flattening(self):
        lead = ir.Leader((0, 0), (20, 20), 'NOTA', 3, shelf=10)
        expected = leader_parts(lead)
        self.assertTrue(any(isinstance(e, ir.Filled) and e.pts[0] == lead.tip
                            for e in expected))
        self.assertEqual(expected, _aplanar(ir.Drawing(ents=[lead])))

    def test_com_uses_text_override_for_symbolic_dimension(self):
        created = SimpleNamespace()
        msp = SimpleNamespace(AddDimRotated=lambda *args: created)
        _dim(msp, ir.Dim((0, 0), (0, 850), (-20, 0), True,
                         txt='R', text_height=3), lambda p: p)
        self.assertEqual(created.TextOverride, 'R')
        self.assertEqual(created.TextHeight, 3)
        self.assertEqual(created.ScaleFactor, 1)


if __name__ == '__main__':
    unittest.main()
