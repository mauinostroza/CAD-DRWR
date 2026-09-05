# -*- coding: utf-8 -*-
"""
generators.profile — Perfiles estructurales de acero (secciones transversales).

I/W, H (HEA), canal C, ángulo L, T y caja HSS con acotado completo,
ejecucentros y propiedades aproximadas (área y peso lineal).
"""

from .panels import SpecPanel
from .data import W_DB, HE_DB, ESCALAS
from core import ir
from core.ir import Line, Poly, Text
from core.geom import line_x, line_y
from core.dims import DimBuilder


# ----------------------------------------------------------------- panel --
class ProfilePanel(SpecPanel):
    SPEC = [
        ("tipo", "Tipo de perfil", "combo",
         ["Perfil I / W", "Perfil H (HEA)", "Canal C", "Ángulo L",
          "T", "Caja HSS"], "Perfil I / W"),
        ("serie", "Serie comercial", "combo",
         ["—"] + list(W_DB) + list(HE_DB), "W250X25"),
        ("d", "Alto d (mm)", "float", 20, 1200, 257, 0, 5, ""),
        ("bf", "Ancho bf (mm)", "float", 20, 600, 101, 0, 5, ""),
        ("tw", "Espesor t / tw", "float", 2, 60, 5.8, 1, 0.5, ""),
        ("tf", "Espesor ala tf", "float", 2, 80, 8.4, 1, 0.5, ""),
        ("escala", "Escala de acotado", "combo", ESCALAS, "1:20"),
    ]

    def on_change(self):
        if getattr(self, "_busy", False):
            return
        self._busy = True
        serie = self.w["serie"].currentText()
        if serie in W_DB:
            s = W_DB[serie]
            self.set_many({"d": s["d"], "bf": s["bf"],
                           "tw": s["tw"], "tf": s["tf"]})
        elif serie in HE_DB:
            s = HE_DB[serie]
            self.set_many({"d": s["d"], "bf": s["bf"],
                           "tw": s["tw"], "tf": s["tf"]})
        self._busy = False


# -------------------------------------------------------------- generador --
def build_profile(p: dict) -> ir.Drawing:
    d = ir.Drawing()
    f = p.get("_escala", 2.0)
    th = 3.0 * f
    db = DimBuilder(d.ents, th)
    D, BF, TW, TF = p["d"], p["bf"], p["tw"], p["tf"]
    tipo = p["tipo"]

    if tipo in ("Perfil I / W", "Perfil H (HEA)"):
        pts = [(-BF / 2, D / 2), (BF / 2, D / 2), (BF / 2, D / 2 - TF),
               (TW / 2, D / 2 - TF), (TW / 2, -D / 2 + TF),
               (BF / 2, -D / 2 + TF), (BF / 2, -D / 2), (-BF / 2, -D / 2),
               (-BF / 2, -D / 2 + TF), (-TW / 2, -D / 2 + TF),
               (-TW / 2, D / 2 - TF), (-BF / 2, D / 2 - TF)]
        A = 2 * BF * TF + (D - 2 * TF) * TW
        d.ents.append(Poly(pts, closed=True))
        db.h_chain([-BF / 2, -TW / 2, TW / 2, BF / 2], -D / 2,
                   -D / 2 - 40 * f, ext_from=-D / 2)
        db.h_total(-BF / 2, BF / 2, -D / 2, -D / 2 - 75 * f, ext_from=-D / 2)
        db.v_chain([-D / 2, -D / 2 + TF, D / 2 - TF, D / 2], BF / 2,
                   BF / 2 + 40 * f, ext_from=BF / 2)
        db.v_total(-D / 2, D / 2, BF / 2, BF / 2 + 75 * f, ext_from=BF / 2)

    elif tipo == "Canal C":
        pts = [(-BF / 2, -D / 2), (BF / 2, -D / 2), (BF / 2, -D / 2 + TF),
               (-BF / 2 + TW, -D / 2 + TF), (-BF / 2 + TW, D / 2 - TF),
               (BF / 2, D / 2 - TF), (BF / 2, D / 2), (-BF / 2, D / 2)]
        A = D * BF - (D - 2 * TF) * (BF - TW)
        d.ents.append(Poly(pts, closed=True))
        db.h_chain([-BF / 2, -BF / 2 + TW, BF / 2], -D / 2,
                   -D / 2 - 40 * f, ext_from=-D / 2)
        db.h_total(-BF / 2, BF / 2, -D / 2, -D / 2 - 75 * f, ext_from=-D / 2)
        db.v_chain([-D / 2, -D / 2 + TF, D / 2 - TF, D / 2], BF / 2,
                   BF / 2 + 40 * f, ext_from=BF / 2)
        db.v_total(-D / 2, D / 2, BF / 2, BF / 2 + 75 * f, ext_from=BF / 2)

    elif tipo == "Ángulo L":
        a, b, t = D, BF, TW
        dx, dy = -a / 2, -b / 2
        pts = [(dx, dy), (dx + a, dy), (dx + a, dy + t),
               (dx + t, dy + t), (dx + t, dy + b), (dx, dy + b)]
        A = t * (a + b - t)
        d.ents.append(Poly(pts, closed=True))
        db.h_chain([dx, dx + t, dx + a], dy, dy - 40 * f, ext_from=dy)
        db.h_total(dx, dx + a, dy, dy - 75 * f, ext_from=dy)
        db.v_chain([dy, dy + t, dy + b], dx + a, dx + a + 40 * f,
                   ext_from=dx + a)
        db.v_total(dy, dy + b, dx + a, dx + a + 75 * f, ext_from=dx + a)

    elif tipo == "T":
        pts = [(-BF / 2, D / 2), (BF / 2, D / 2), (BF / 2, D / 2 - TF),
               (TW / 2, D / 2 - TF), (TW / 2, -D / 2),
               (-TW / 2, -D / 2), (-TW / 2, D / 2 - TF), (-BF / 2, D / 2 - TF)]
        A = BF * TF + (D - TF) * TW
        d.ents.append(Poly(pts, closed=True))
        db.h_chain([-BF / 2, -TW / 2, TW / 2, BF / 2], -D / 2,
                   -D / 2 - 40 * f, ext_from=-D / 2)
        db.h_total(-BF / 2, BF / 2, -D / 2, -D / 2 - 75 * f, ext_from=-D / 2)
        db.v_chain([-D / 2, D / 2 - TF, D / 2], BF / 2, BF / 2 + 40 * f,
                   ext_from=BF / 2)
        db.v_total(-D / 2, D / 2, BF / 2, BF / 2 + 75 * f, ext_from=BF / 2)

    else:  # Caja HSS
        t = TW
        d.ents.append(ir.rect(-BF / 2, -D / 2, BF / 2, D / 2))
        d.ents.append(ir.rect(-BF / 2 + t, -D / 2 + t, BF / 2 - t, D / 2 - t))
        A = BF * D - (BF - 2 * t) * (D - 2 * t)
        db.h_chain([-BF / 2, -BF / 2 + t, BF / 2 - t, BF / 2], -D / 2,
                   -D / 2 - 40 * f, ext_from=-D / 2)
        db.h_total(-BF / 2, BF / 2, -D / 2, -D / 2 - 75 * f, ext_from=-D / 2)
        db.v_chain([-D / 2, -D / 2 + t, D / 2 - t, D / 2], BF / 2,
                   BF / 2 + 40 * f, ext_from=BF / 2)
        db.v_total(-D / 2, D / 2, BF / 2, BF / 2 + 75 * f, ext_from=BF / 2)

    # ejes
    d.ents.append(line_y(0, -BF / 2 - 40 * f, BF / 2 + 40 * f))
    d.ents.append(line_x(0, -D / 2 - 40 * f, D / 2 + 40 * f))
    d.ents.append(Text((0, D / 2 + 90 * f), "SECCIÓN",
                       3.5 * f, layer=ir.L_TXT, ha="c", va="m"))

    # propiedades
    peso = A * 7850e-9 * 1000          # kg/m (A en mm²)
    props = [f"A = {A / 100.0:.1f} cm²    PESO = {peso:.1f} kg/m",
             "PROPIEDADES APROXIMADAS, SIN RADIOS DE UNIÓN"]
    y0 = -D / 2 - 115 * f
    for i, s in enumerate(props):
        d.ents.append(Text((-BF / 2 - 40 * f, y0 - i * 8 * f), s,
                           2.5 * f, 0, ir.L_TXT, "l", "m"))
    d.ents.append(Text((0, y0 - len(props) * 8 * f - 14 * f),
                       f"{tipo.upper()} {p['serie'] if p['serie'] != '—' else ''}"
                       f"  -  ESC {p['escala']}", 4.5 * f, 0, ir.L_TXT,
                       "c", "m"))
    return d
