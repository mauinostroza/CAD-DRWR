# -*- coding: utf-8 -*-
"""generators.data — Bases de datos de perfiles y series normalizadas."""

# Perfiles W (dimensiones nominales en mm) — AISC/CISC métrico
W_DB = {
    "W150X24":  dict(d=162, bf=154, tw=6.6, tf=9.1),
    "W200X22":  dict(d=203, bf=102, tw=6.2, tf=8.4),
    "W250X25":  dict(d=257, bf=101, tw=5.8, tf=8.4),
    "W310X39":  dict(d=310, bf=165, tw=5.8, tf=10.2),
    "W360X45":  dict(d=356, bf=127, tw=7.5, tf=11.9),
    "W410X46":  dict(d=404, bf=140, tw=6.4, tf=11.6),
    "W530X66":  dict(d=533, bf=165, tw=7.5, tf=13.5),
}

# Perfiles H (HEA aproximado)
HE_DB = {
    "HE200A": dict(d=190, bf=200, tw=6.5, tf=10.0),
    "HE240A": dict(d=230, bf=240, tw=7.5, tf=12.0),
    "HE300A": dict(d=270, bf=300, tw=8.5, tf=14.0),
}

# Diámetros de pernos comunes (mm)
DIAM_PERNOS = [16, 19, 22, 25, 29, 32]

# Diámetros de barra corrugada (mm)
DIAM_BARRAS = [8, 10, 12, 16, 18, 22, 25, 28, 32]

ESCALAS = ["1:10", "1:20", "1:25", "1:50", "1:75", "1:100"]


def factor_escala(esc: str) -> float:
    """1:50 -> 5.0  (multiplicador de alturas de texto/acotado)."""
    try:
        n = float(esc.split(":")[1])
        return n / 10.0
    except Exception:
        return 5.0
