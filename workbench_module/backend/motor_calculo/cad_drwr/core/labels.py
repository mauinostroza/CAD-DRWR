# -*- coding: utf-8 -*-
"""Formateo único de rótulos técnicos."""

from . import ir


def rebar_spacing(diameter_mm: float, spacing_mm: float, position: str) -> str:
    """Rótulo de armadura con espaciamiento expresado en centímetros."""
    return (f"Ø{diameter_mm:g} c/{ir.fmt_cm(spacing_mm)} cm "
            f"({position.upper()})")
