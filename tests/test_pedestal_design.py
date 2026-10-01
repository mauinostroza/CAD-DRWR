"""Coherencia geométrica de pedestal; no certificación normativa."""
import unittest

from core.ir import Table, Text
from generators.pedestal import (PedestalPanel, build_pedestal, _starter_path,
                                 _b1_length, _starter_axis)


def params():
    return {r[0]: r[4] if r[2] == 'combo' else r[3] if r[2] == 'chk' else r[5]
            for r in PedestalPanel.SPEC}


class PedestalDesignTests(unittest.TestCase):
    def test_b1_tracks_geometry(self):
        p = params()
        p.update(H=180, r=5)
        self.assertEqual(_b1_length(p), 1750)
        table = next(e for e in build_pedestal(p).ents if isinstance(e, Table))
        self.assertEqual(table.rows[0][4], '1.75')
        # El boceto/despiece debe recibir la longitud real; no un segmento
        # ficticio de 1 mm con celdas sobreescritas después.
        sketch = table.sketches[(0, 1)]
        self.assertAlmostEqual(abs(sketch[0].p2[1] - sketch[0].p1[1]), 1750)

    def test_legacy_manual_is_explicit(self):
        p = params()
        p.pop('modo_b1')
        self.assertEqual(_b1_length(p), 3200)
        texts = [e.s for e in build_pedestal(p).ents if isinstance(e, Text)]
        self.assertTrue(any('B1 MANUAL' in s for s in texts))

    def test_cover_is_to_bar_surface(self):
        p = params()
        p['r_zapata'] = 70
        self.assertEqual(_starter_path(p)[0][1], -300 + 70 + 9)
        p.pop('r_zapata')
        self.assertEqual(_starter_path(p)[0][1], -240)

    def test_starter_outside_footing_is_rejected(self):
        p = params()
        p.update(ancho_zap=30, gancho_arranque=200)
        with self.assertRaisesRegex(ValueError, 'recubrimiento lateral'):
            build_pedestal(p)

    def test_lap_outside_pedestal_is_rejected(self):
        p = params()
        p.update(H=40, traslape=45)
        with self.assertRaisesRegex(ValueError, 'traslape'):
            build_pedestal(p)

    def test_material_notes_are_editable(self):
        p = params()
        p.update(fc=35, fy=500)
        texts = [e.s for e in build_pedestal(p).ents if isinstance(e, Text)]
        self.assertTrue(any("f'c = 35 MPa" in s and 'fy = 500 MPa' in s for s in texts))

    def test_contact_lap_axes_are_distinct(self):
        self.assertEqual(_starter_axis(-93, 18), -75)
        self.assertEqual(_starter_axis(93, 18), 75)

    def test_nonfinite_material_is_rejected(self):
        p = params()
        p['fc'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'materiales'):
            build_pedestal(p)


if __name__ == '__main__':
    unittest.main()
