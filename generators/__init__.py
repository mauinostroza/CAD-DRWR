# -*- coding: utf-8 -*-
"""generators — Registro central de módulos de la aplicación."""

from collections import namedtuple

from .base_plate import BasePlatePanel, build_base_plate
from .pedestal import PedestalPanel, build_pedestal
from .slab import SlabPanel, build_slab
from .anchor_bolt import AnchorBoltPanel, build_anchor_bolt
from .profile import ProfilePanel, build_profile
from .bar_shape import BarShapePanel, build_bar_shape

Module = namedtuple("Module", "nombre prefix panel builder")

MODULES = [
    Module("Placa Base", "placa_base", BasePlatePanel, build_base_plate),
    Module("Pedestal", "pedestal", PedestalPanel, build_pedestal),
    Module("Losa", "losa", SlabPanel, build_slab),
    Module("Perno de Anclaje", "perno_anclaje", AnchorBoltPanel,
           build_anchor_bolt),
    Module("Perfil Estructural", "perfil", ProfilePanel, build_profile),
    Module("Forma de Barra", "forma_barra", BarShapePanel, build_bar_shape),
]
