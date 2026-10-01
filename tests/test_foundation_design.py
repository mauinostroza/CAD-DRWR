import unittest

from core import ir
from generators.foundation_sap import _posicion_corte, _dibujar_zapata_elevacion
from core.dims import DimBuilder


class FoundationDesignTests(unittest.TestCase):
    def fixture(self):
        return {"nombre": "F1", "contorno": [(0,0),(2000,0),(2000,1000),(0,1000)],
                "areas": [{"pts": [(0,0,0),(2000,0,0),(2000,1000,0),(0,1000,0)],
                           "espesor": 300, "seccion": "Z"}],
                "pedestales": [{"centro": (300,500), "largo": 200, "ancho": 200,
                                "largo_en_x": True},
                               {"centro": (1700,500), "largo": 200, "ancho": 200,
                                "largo_en_x": True}]}

    def test_cut_goes_through_actual_pedestal_not_average(self):
        self.assertEqual(_posicion_corte(self.fixture(), "x"), 300)

    def test_cut_does_not_show_unintersected_pedestal_as_section(self):
        d = ir.Drawing()
        _dibujar_zapata_elevacion(d, DimBuilder(d.ents, 15), self.fixture(),
                                  "x", 0, 0, 5, 15, 300)
        steel = [e for e in d.ents if isinstance(e, ir.Poly) and e.layer == ir.L_ACERO]
        self.assertEqual(len(steel), 1)
        labels = [e.s for e in d.ents if isinstance(e, ir.Text)]
        self.assertIn("CONTINUACIÓN ESQUEMÁTICA", labels)
        self.assertNotIn("N.P. ±0.00", labels)
