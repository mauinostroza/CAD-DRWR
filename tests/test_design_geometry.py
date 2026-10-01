import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.ir import Dim, Leader, Poly, Table, Text
from generators.base_plate import BasePlatePanel, build_base_plate
from generators.slab import SlabPanel, build_slab


class DesignGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_baseplate_projection_has_explicit_plate_top_datum(self):
        params = BasePlatePanel().params()
        params.update({"B": 500, "N": 800, "w_conc": 700,
                       "bf": 200, "d": 300, "g": 350, "p": 500,
                       "cartelas": True, "ls": 80, "ts": 12})
        drawing = build_base_plate(params)
        labels = [e.s for e in drawing.ents if isinstance(e, Text)]
        dims = [e.txt for e in drawing.ents if isinstance(e, Dim)]
        self.assertTrue(any("P = 100 mm desde cara superior de placa" in s
                            for s in labels))
        self.assertIn("P = 100", dims)
        # The separate anchor detail is referenced to concrete top, hence it
        # includes the 20 mm grout plus the 12 mm plate before user P.
        self.assertIn("P HORMIGÓN = 132", dims)
        self.assertIn("B = 500", dims)
        self.assertIn("PEDESTAL = 700", dims)
        p_dim = next(e for e in drawing.ents
                     if isinstance(e, Dim) and e.txt == "P = 100")
        self.assertAlmostEqual(p_dim.p1[0], p_dim.p2[0])
        self.assertAlmostEqual(p_dim.p1[0], p_dim.base[0] - 40 * params["_escala"])
        # The X-Z elevation width is B, not N; its bolt projection reference
        # and plate leader therefore sit relative to B.
        ex = 500 + 150 * params["_escala"]
        self.assertAlmostEqual(p_dim.p1[0], ex + 250)
        cartela_boxes = []
        for ent in drawing.ents:
            if not isinstance(ent, Poly) or not ent.closed or ent.layer != "CONCRETO":
                continue
            xs = [pt[0] for pt in ent.pts]
            ys = [pt[1] for pt in ent.pts]
            box = (min(xs), max(xs), min(ys), max(ys))
            if abs((box[1] - box[0]) - 80) < 1e-6 and abs((box[3] - box[2]) - 12) < 1e-6:
                cartela_boxes.append(box)
        self.assertEqual(len(cartela_boxes), 4)
        expected_y = {-(params["d"] / 2 - params["tf"] / 2),
                      params["d"] / 2 - params["tf"] / 2}
        self.assertEqual({round((box[2] + box[3]) / 2, 1)
                          for box in cartela_boxes},
                         {round(y, 1) for y in expected_y})
        self.assertTrue(any(abs(box[0] - params["bf"] / 2) < 1e-6 and
                            abs(box[1] - (params["bf"] / 2 + params["ls"])) < 1e-6
                            for box in cartela_boxes))
        self.assertTrue(any(abs(box[0] + (params["bf"] / 2 + params["ls"])) < 1e-6 and
                            abs(box[1] + params["bf"] / 2) < 1e-6
                            for box in cartela_boxes))
        plate_leader = next(e for e in drawing.ents
                            if isinstance(e, Leader) and e.s.startswith("PLACA e"))
        self.assertAlmostEqual(plate_leader.tip[1], 20 + params["t"] / 2)

        table = next(e for e in drawing.ents if isinstance(e, Table))
        self.assertEqual(table.rows[0][3], "100")

    def test_baseplate_design_notes_are_explicitly_unspecified_by_default(self):
        drawing = build_base_plate(BasePlatePanel().params())
        notes = "\n".join(e.s for e in drawing.ents if isinstance(e, Text))
        self.assertIn("PLACA BASE No especificado", notes)
        self.assertIn("PERNOS 4x Ø19 No especificado", notes)
        self.assertIn("GROUT: resistencia no especificada", notes)
        self.assertNotIn("A307", notes)
        self.assertNotIn("21 MPa", notes)

    def test_baseplate_schedule_uses_selected_bolt_specification(self):
        params = BasePlatePanel().params()
        params["material_perno"] = "F1554 Gr.55"
        drawing = build_base_plate(params)
        tables = [e for e in drawing.ents if isinstance(e, Table)]
        self.assertEqual(tables[0].rows[0][4], "F1554 Gr.55")

    def test_baseplate_rejects_anchor_pattern_outside_plate(self):
        params = BasePlatePanel().params()
        params["g"] = params["B"] + 10
        with self.assertRaisesRegex(ValueError, "agujeros de perno exceden"):
            build_base_plate(params)

    def test_baseplate_manual_dimensions_survive_other_edits(self):
        panel = BasePlatePanel()
        panel.w["g"].setValue(300)
        panel.w["p"].setValue(420)
        panel.w["B"].setValue(500)
        panel.w["N"].setValue(600)
        panel.w["cartelas"].setChecked(False)
        self.assertEqual(panel.params()["g"], 300)
        self.assertEqual(panel.params()["p"], 420)
        self.assertEqual(panel.params()["B"], 500)
        self.assertEqual(panel.params()["N"], 600)

    def test_slab_bar_quantities_and_effective_spacing_match_widths(self):
        panel = SlabPanel()
        params = panel.params()
        params.update({"ancho_reparto": 250, "s1": 20, "s2": 25,
                       "s3": 15, "sup": True})
        drawing = build_slab(params)
        table = next(e for e in drawing.ents if isinstance(e, Table))
        rows = {row[0]: row for row in table.rows}

        width_mm = params["ancho_reparto"] * 10
        cover_mm = params["r"] * 10
        d1, d2, d3 = map(float, (params["d1"], params["d2"], params["d3"]))
        q1_span = width_mm - 2 * cover_mm - d1
        q1_expected = int(__import__("math").ceil(
            q1_span / (params["s1"] * 10))) + 1
        q3_span = width_mm - 2 * cover_mm - d3
        q3_per_support = int(__import__("math").ceil(
            q3_span / (params["s3"] * 10))) + 1
        span_centres = (params["L"] * 10 + 2 * params["bw"] * 10
                        - 2 * cover_mm - d2)
        q2_expected = int(__import__("math").ceil(
            span_centres / (params["s2"] * 10))) + 1
        self.assertEqual(int(rows["B1"][3]), q1_expected)
        self.assertEqual(int(rows["B2"][3]), q2_expected)
        self.assertEqual(int(rows["B3"][3]), 2 * q3_per_support)
        self.assertLessEqual(q1_span / (q1_expected - 1),
                             params["s1"] * 10)
        self.assertLessEqual(span_centres / (q2_expected - 1), params["s2"] * 10)
        self.assertAlmostEqual(float(rows["B2"][4]),
                               (width_mm - 2 * cover_mm) / 1000,
                               places=2)

    def test_slab_requires_distribution_width_and_fits_basic_cover(self):
        panel = SlabPanel()
        params = panel.params()
        params["ancho_reparto"] = 4
        with self.assertRaisesRegex(ValueError, "ancho de distribución"):
            build_slab(params)

    def test_slab_rejects_thickness_that_cannot_fit_bar_layers(self):
        params = SlabPanel().params()
        params.update({"t": 8, "r": 2.5, "d1": "16", "d2": "12",
                       "d3": "10", "sup": True})
        with self.assertRaisesRegex(ValueError, "paquete de armaduras"):
            build_slab(params)


if __name__ == "__main__":
    unittest.main()
