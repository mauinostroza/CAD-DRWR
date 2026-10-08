# -*- coding: utf-8 -*-
"""
sap_geom — Modelo de datos puro de la geometría de fundaciones (sin COM).

Copia literal de los dataclasses de `cad/sap2000_link.py` del escritorio:
Pedestal, AreaGeom, Zapata y FundacionGeom, con su serialización a dict.
La lectura desde SAP2000 (COM) no se porta.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Pedestal:
    frame: str
    largo: float
    ancho: float
    largo_en_x: bool
    centro: Tuple[float, float]
    punto_pie: str
    aproximado: bool = False
    motivo_aviso: str = ""


# ------------------------------------------------------- modelo de datos --

@dataclass
class AreaGeom:
    nombre: str
    seccion: str
    espesor: Optional[float]
    pts_nombres: List[str]
    pts: List[Tuple[float, float, float]]
    pts_malla: List[str] = field(default_factory=list)


@dataclass
class Zapata:
    """Una fundación física (componente conexa de shells) dentro de un
    grupo de SAP2000."""
    nombre: str
    areas: List[AreaGeom] = field(default_factory=list)
    contorno: List[Tuple[float, float]] = field(default_factory=list)
    pedestales: List[Pedestal] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "areas": [
                {"nombre": a.nombre, "seccion": a.seccion,
                 "espesor": a.espesor, "pts_nombres": list(a.pts_nombres),
                 "pts": [list(p) for p in a.pts],
                 "pts_malla": list(a.pts_malla)}
                for a in self.areas
            ],
            "contorno": [list(p) for p in self.contorno],
            "pedestales": [
                {"frame": pd.frame, "largo": pd.largo, "ancho": pd.ancho,
                 "largo_en_x": pd.largo_en_x, "centro": list(pd.centro),
                 "punto_pie": pd.punto_pie, "aproximado": pd.aproximado,
                 "motivo_aviso": pd.motivo_aviso}
                for pd in self.pedestales
            ],
        }

    @staticmethod
    def from_dict(d: dict) -> "Zapata":
        return Zapata(
            nombre=d.get("nombre", ""),
            areas=[
                AreaGeom(a["nombre"], a["seccion"], a.get("espesor"),
                        list(a.get("pts_nombres", [])),
                        [tuple(p) for p in a["pts"]],
                        list(a.get("pts_malla", [])))
                for a in d.get("areas", [])
            ],
            contorno=[tuple(p) for p in d.get("contorno", [])],
            pedestales=[
                Pedestal(pd["frame"], pd["largo"], pd["ancho"],
                        pd["largo_en_x"], tuple(pd["centro"]),
                        pd.get("punto_pie", ""), pd.get("aproximado", False),
                        pd.get("motivo_aviso", ""))
                for pd in d.get("pedestales", [])
            ],
        )


@dataclass
class FundacionGeom:
    nombre: str
    zapatas: List[Zapata] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"nombre": self.nombre,
                "zapatas": [z.to_dict() for z in self.zapatas]}

    @staticmethod
    def from_dict(d: dict) -> "FundacionGeom":
        return FundacionGeom(
            nombre=d.get("nombre", ""),
            zapatas=[Zapata.from_dict(z) for z in d.get("zapatas", [])])
