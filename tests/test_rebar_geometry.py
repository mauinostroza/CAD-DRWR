"""Invariantes geométricas de estribos y ganchos."""
import math
import unittest

from core import ir
from core.geom import dist, stirrup_pts, poly_bar


class StirrupGeometryTests(unittest.TestCase):
    def test_projected_hoop_has_exact_135_hooks_and_full_free_legs(self):
        b, h, d, r_in = 220.0, 320.0, 8.0, 20.0
        pts = stirrup_pts(b, h, d, r_in)
        ents, _ = poly_bar(pts, d, r_in)

        # Los dos extremos libres quedan tras el recorte tangente con Lh.
        lines = [e for e in ents if isinstance(e, ir.Line)]
        self.assertAlmostEqual(dist(lines[0].p1, lines[0].p2), 75.0, places=7)
        self.assertAlmostEqual(dist(lines[-1].p1, lines[-1].p2), 75.0, places=7)

        arcs = [e for e in ents if isinstance(e, ir.Arc)]
        hook_arcs = [a for a in arcs
                     if abs(abs((a.a2 - a.a1 + 180) % 360 - 180) - 135) < 1e-7]
        self.assertEqual(len(hook_arcs), 2)
        self.assertEqual(len(arcs), 5)

        # La proyección contiene toda la cara derecha: los dos pasajes se
        # traslapan entre los puntos de cierre, sin la abertura de un C.
        # Los dos arcos de gancho abrazan la misma esquina; los extremos
        # de todas las rectas coinciden con los del arco adyacente.
        self.assertAlmostEqual(dist(hook_arcs[0].c, hook_arcs[1].c), 0, places=7)
        self.assertEqual(hook_arcs[0].c, (b - 24, h - 24))
        for before, after in zip(ents, ents[1:]):
            end = before.p2 if isinstance(before, ir.Line) else (
                before.c[0] + before.r * math.cos(math.radians(before.a2)),
                before.c[1] + before.r * math.sin(math.radians(before.a2)))
            start = after.p1 if isinstance(after, ir.Line) else (
                after.c[0] + after.r * math.cos(math.radians(after.a1)),
                after.c[1] + after.r * math.sin(math.radians(after.a1)))
            self.assertLess(dist(end, start), 1e-7)

    def test_rejects_geometry_that_cannot_keep_requested_radius_and_hook(self):
        with self.assertRaisesRegex(ValueError, "altura insuficiente"):
            stirrup_pts(220.0, 60.0, 12.0, 30.0)
        with self.assertRaisesRegex(ValueError, "ancho insuficiente"):
            stirrup_pts(100.0, 400.0, 12.0, 30.0)


if __name__ == "__main__":
    unittest.main()
