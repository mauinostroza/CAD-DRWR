# -*- coding: utf-8 -*-
"""Genera el golden de fundaciones con el ORIGINAL de escritorio.

Ejecutar desde la raíz del repo:
    QT_QPA_PLATFORM=offscreen python workbench_module/scripts/golden_fundacion.py

Escribe backend/motor_calculo/cad_drwr/golden/fundacion_sap.json: una lista de
{"nombre", "params", "drawing"} por caso, o {"nombre", "params", "error"} cuando
build_foundation lanza ValueError.
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "workbench_module", "scripts"))

from generators.foundation_sap import build_foundation  # ORIGINAL
from cad.sap2000_link import FundacionGeom, Zapata, AreaGeom, Pedestal  # ORIGINAL
from golden_dump import dump

OUT = os.path.join(ROOT, "workbench_module", "backend", "motor_calculo",
                   "cad_drwr", "golden", "fundacion_sap.json")


def _params(geom):
    return {
        "_escala": 5.0,
        "escala": "1:50",
        "fundacion": "G1",
        "espesor_default": 400.0,
        "_geom": geom.to_dict() if geom is not None else None,
    }


def _ejecutar(nombre, params):
    try:
        drawing = build_foundation(params)
    except ValueError as exc:
        return {"nombre": nombre, "params": params, "error": str(exc)}
    return {"nombre": nombre, "params": params, "drawing": dump(drawing)}


def _casos():
    casos = []

    # (a) zapata rectangular 3000 x 3500 con 1 pedestal 400 x 400 en el centro
    z_a = Zapata(
        nombre="Z1",
        areas=[AreaGeom(nombre="A1", seccion="E400", espesor=400.0,
                        pts_nombres=["J1", "J2", "J3", "J4"],
                        pts=[(0.0, 0.0, 0.0), (3000.0, 0.0, 0.0),
                             (3000.0, 3500.0, 0.0), (0.0, 3500.0, 0.0)])],
        contorno=[(0.0, 0.0), (3000.0, 0.0), (3000.0, 3500.0), (0.0, 3500.0)],
        pedestales=[Pedestal(frame="C1", largo=400.0, ancho=400.0,
                             largo_en_x=True, centro=(1500.0, 1750.0),
                             punto_pie="N10")],
    )
    casos.append(("a_rectangular_1_pedestal",
                  _params(FundacionGeom(nombre="G1", zapatas=[z_a]))))

    # (b) dos zapatas separadas: una con pedestal (largo_en_x False), otra sin pedestal
    z_b1 = Zapata(
        nombre="Z1",
        areas=[AreaGeom(nombre="A1", seccion="E400", espesor=400.0,
                        pts_nombres=["J1", "J2", "J3", "J4"],
                        pts=[(0.0, 0.0, -200.0), (2000.0, 0.0, -200.0),
                             (2000.0, 2000.0, -200.0), (0.0, 2000.0, -200.0)])],
        contorno=[(0.0, 0.0), (2000.0, 0.0), (2000.0, 2000.0), (0.0, 2000.0)],
        pedestales=[Pedestal(frame="C2", largo=300.0, ancho=500.0,
                             largo_en_x=False, centro=(1000.0, 1000.0),
                             punto_pie="N20")],
    )
    z_b2 = Zapata(
        nombre="Z2",
        areas=[AreaGeom(nombre="A2", seccion="E350", espesor=350.0,
                        pts_nombres=["J5", "J6", "J7", "J8"],
                        pts=[(4000.0, 0.0, -200.0), (6500.0, 0.0, -200.0),
                             (6500.0, 2500.0, -200.0), (4000.0, 2500.0, -200.0)])],
        contorno=[(4000.0, 0.0), (6500.0, 0.0), (6500.0, 2500.0), (4000.0, 2500.0)],
        pedestales=[],
    )
    casos.append(("b_dos_zapatas_separadas",
                  _params(FundacionGeom(nombre="G1", zapatas=[z_b1, z_b2]))))

    # (c) zapata en L con 2 áreas de espesores distintos (400 y 500) y 2 pedestales,
    #     uno aproximado con motivo_aviso
    z_c = Zapata(
        nombre="Z1",
        areas=[
            AreaGeom(nombre="A1", seccion="E400", espesor=400.0,
                     pts_nombres=["J1", "J2", "J3", "J4"],
                     pts=[(0.0, 0.0, 0.0), (3000.0, 0.0, 0.0),
                          (3000.0, 1500.0, 0.0), (0.0, 1500.0, 0.0)]),
            AreaGeom(nombre="A2", seccion="E500", espesor=500.0,
                     pts_nombres=["J4", "J3", "J5", "J6"],
                     pts=[(0.0, 1500.0, 0.0), (1500.0, 1500.0, 0.0),
                          (1500.0, 3500.0, 0.0), (0.0, 3500.0, 0.0)]),
        ],
        contorno=[(0.0, 0.0), (3000.0, 0.0), (3000.0, 1500.0),
                  (1500.0, 1500.0), (1500.0, 3500.0), (0.0, 3500.0)],
        pedestales=[
            Pedestal(frame="C3", largo=400.0, ancho=400.0, largo_en_x=True,
                     centro=(2500.0, 750.0), punto_pie="N30"),
            Pedestal(frame="C4", largo=600.0, ancho=600.0, largo_en_x=True,
                     centro=(750.0, 2500.0), punto_pie="N40",
                     aproximado=True,
                     motivo_aviso="Sección circular, aproximada como cuadrado"),
        ],
    )
    casos.append(("c_zapata_L_dos_espesores",
                  _params(FundacionGeom(nombre="G1", zapatas=[z_c]))))

    # (d) zapata con espesor None: se usa espesor_default (400)
    z_d = Zapata(
        nombre="Z1",
        areas=[AreaGeom(nombre="A1", seccion="SIN_ESP", espesor=None,
                        pts_nombres=["J1", "J2", "J3", "J4"],
                        pts=[(0.0, 0.0, 0.0), (1800.0, 0.0, 0.0),
                             (1800.0, 1200.0, 0.0), (0.0, 1200.0, 0.0)])],
        contorno=[(0.0, 0.0), (1800.0, 0.0), (1800.0, 1200.0), (0.0, 1200.0)],
        pedestales=[],
    )
    casos.append(("d_espesor_none_usa_default",
                  _params(FundacionGeom(nombre="G1", zapatas=[z_d]))))

    # error: sin geometría
    casos.append(("e_sin_geometria", _params(None)))
    return casos


def main():
    salida = [_ejecutar(nombre, params) for nombre, params in _casos()]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(salida, fh, indent=1)
    for caso in salida:
        estado = ("ERROR: " + caso["error"]) if "error" in caso else "ok"
        print(f"{caso['nombre']}: {estado}")
    print("escrito:", OUT)


if __name__ == "__main__":
    main()
