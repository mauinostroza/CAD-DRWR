# -*- coding: utf-8 -*-
"""Genera el golden de reglas de interfaz desde el ORIGINAL (escritorio).

Uso (desde la raíz del repo):
    QT_QPA_PLATFORM=offscreen python workbench_module/scripts/golden_reglas_ui.py

Cada escenario crea un Panel real, aplica un prefijo de cambios reales sobre
los widgets (sin bloquear señales) y después un cambio real campo=valor.
Registra:
    params_antes   panel.params() antes del cambio
    campo, valor   el cambio aplicado
    params_despues panel.params() después del cambio
    habilitados    {clave: widget.isEnabled()} de todos los widgets

Escribe backend/motor_calculo/cad_drwr/golden/reglas_ui.json.
No escribe nada dentro del ORIGINAL (no genera __pycache__ allí).
"""
import json
import pathlib
import sys

sys.dont_write_bytecode = True  # el ORIGINAL permanece intacto

from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox,  # noqa: E402
                               QDoubleSpinBox, QSpinBox)

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GOLDEN = (ROOT / "workbench_module/backend/motor_calculo/cad_drwr/golden"
          / "reglas_ui.json")

sys.path.insert(0, str(ROOT))  # paquete ORIGINAL `generators`

from generators import MODULES  # noqa: E402

REF20 = "Referencia 20"

# (nombre, prefijo [(campo, valor)...], campo, valor)
ESCENARIOS = {
    "placa_base": [
        ("perfil_w310", [], "perfil", "W310X39"),
        ("perfil_w150", [], "perfil", "W150X24"),
        ("perfil_manual", [], "perfil", "Manual"),
        ("perfil_w200_desde_w360", [("perfil", "W360X45")], "perfil", "W200X22"),
        ("perfil_w530", [], "perfil", "W530X66"),
        ("d_manual_no_autollena", [], "d", 300),
        ("perfil_manual_conserva_valores", [("perfil", "W310X39")], "perfil", "Manual"),
        ("bf_manual_conserva_w150", [("perfil", "W150X24")], "bf", 120),
        ("n_pernos_8", [], "n_pernos", "8"),
        ("cartelas_off", [], "cartelas", False),
        ("d_perno_22", [], "d_perno", 22),
        ("escala_1_100", [], "escala", "1:100"),
    ],
    "pedestal": [
        ("entra_referencia_desde_total", [], "preset", REF20),
        ("entra_referencia_desde_por_caras", [("preset", "Por caras"), ("n_sup", 5)],
         "preset", REF20),
        ("sale_referencia_a_por_caras", [("preset", REF20)], "preset", "Por caras"),
        ("sale_referencia_a_total", [("preset", REF20)], "preset", "Total anterior"),
        ("por_caras_desde_total", [], "preset", "Por caras"),
        ("n_barras_12_total", [], "n_barras", "12"),
        ("b_60_dentro_de_referencia", [("preset", REF20)], "b", 60),
        ("entra_referencia_pisa_d_barra", [("d_barra", "25"), ("elevacion", True)],
         "preset", REF20),
        ("modo_b1_manual", [], "modo_b1", "Manual (esquemático)"),
        ("modo_b1_vuelve_segun_elevacion", [("modo_b1", "Manual (esquemático)")],
         "modo_b1", "Según elevación"),
        ("lazos_interiores_on", [], "lazos_interiores", True),
        ("lazos_interiores_off_conserva_vertical", [("lazos_interiores", True),
                                                   ("lazo_vertical", False)],
         "lazos_interiores", False),
    ],
    "losa": [
        ("sup_off", [], "sup", False),
        ("L_600", [], "L", 600),
        ("t_18_escala", [], "t", 18),
        ("d1_16", [], "d1", "16"),
        ("s1_15", [], "s1", 15),
        ("escala_1_20", [], "escala", "1:20"),
        ("d3_12_sup_on", [], "d3", "12"),
    ],
    "perno_anclaje": [
        ("tipo_L", [], "tipo", "L (codo 90°)"),
        ("d_nominal_mm", [], "d_nominal", "mm"),
        ("d_nominal_1in_fuerza_25_4", [("d_nominal", "mm"), ("d_perno", "19")],
         "d_nominal", "1 in"),
        ("tipo_PG_desde_J", [("tipo", "J (gancho 135°)")], "tipo",
         "PG (recto con golilla)"),
        ("tipo_recto_con_placa", [], "tipo", "Recto con placa"),
        ("d_perno_16_con_mm", [("d_nominal", "mm")], "d_perno", "16"),
        ("n_60", [], "n", 60),
        ("acabado_galvanizado", [], "acabado", "Galvanizado en caliente"),
        ("permitir_h1_pg", [], "permitir_h1_bajo_tc", True),
        ("tipo_L_desde_PG_mm", [("d_nominal", "mm")], "tipo", "L (codo 90°)"),
    ],
    "perfil": [
        ("serie_w310", [], "serie", "W310X39"),
        ("serie_he240", [], "serie", "HE240A"),
        ("serie_guion", [], "serie", "—"),
        ("d_300_con_serie_bloqueada", [], "d", 300),
        ("d_300_sin_serie", [("serie", "—")], "d", 300),
        ("tw_9_con_serie_w150", [("serie", "W150X24")], "tw", 9),
        ("serie_he300_desde_caja", [("tipo", "Caja HSS")], "serie", "HE300A"),
        ("tipo_canal", [], "tipo", "Canal C"),
        ("escala_1_50", [], "escala", "1:50"),
        ("bf_180_con_he200", [("serie", "HE200A")], "bf", 180),
    ],
    "forma_barra": [
        ("forma_gancho", [], "forma", "Gancho 90° (L)"),
        ("forma_estribo", [], "forma", "Estribo 135°"),
        ("forma_z", [], "forma", "Z"),
        ("d_barra_16", [], "d_barra", "16"),
        ("qty_5", [], "qty", 5),
        ("marca_b2", [], "marca", "B2"),
        ("k_3_5", [], "k", 3.5),
        ("a_800", [], "a", 800),
    ],
}


def _modulo(prefix):
    return next(m for m in MODULES if m.prefix == prefix)


def _asignar(panel, campo, valor):
    """Cambio como lo haría el usuario: sin bloquear señales.

    Devuelve el valor convertido al tipo del widget (str, bool, int o float),
    que es el que el test debe usar como ``valor``.
    """
    w = panel.w[campo]
    if isinstance(w, QComboBox):
        w.setCurrentText(str(valor))
        return str(valor)
    if isinstance(w, QCheckBox):
        w.setChecked(bool(valor))
        return bool(valor)
    if isinstance(w, QSpinBox):
        w.setValue(int(valor))
        return int(valor)
    if isinstance(w, QDoubleSpinBox):
        w.setValue(float(valor))
        return float(valor)
    raise TypeError(f"tipo de widget no soportado para {campo!r}")


def _habilitados(panel):
    return {k: w.isEnabled() for k, w in panel.w.items()}


def _escenario(prefix, nombre, prefijo, campo, valor):
    panel = _modulo(prefix).panel()
    for c, v in prefijo:
        _asignar(panel, c, v)
    antes = panel.params()
    valor_real = _asignar(panel, campo, valor)
    despues = panel.params()
    return {
        "modulo": prefix,
        "nombre": nombre,
        "params_antes": antes,
        "campo": campo,
        "valor": valor_real,
        "params_despues": despues,
        "habilitados": _habilitados(panel),
    }


def casos():
    out = []
    for prefix, lista in ESCENARIOS.items():
        for nombre, prefijo, campo, valor in lista:
            out.append(_escenario(prefix, nombre, prefijo, campo, valor))
    return out


def _resumen(caso):
    cambios = {k: (caso["params_antes"].get(k), v)
               for k, v in caso["params_despues"].items()
               if caso["params_antes"].get(k) != v}
    deshab = sorted(k for k, on in caso["habilitados"].items() if not on)
    print(f"[{caso['modulo']}] {caso['nombre']}: {caso['campo']}={caso['valor']!r}")
    print(f"    cambios: {cambios}")
    print(f"    deshabilitados: {deshab}")


def main():
    app = QApplication.instance() or QApplication([])  # noqa: F841
    datos = casos()
    for c in datos:
        _resumen(c)
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    print(f"escrito {GOLDEN.relative_to(ROOT)} ({len(datos)} escenarios)")


if __name__ == "__main__":
    main()
