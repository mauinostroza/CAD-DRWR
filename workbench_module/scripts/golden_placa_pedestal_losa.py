# -*- coding: utf-8 -*-
"""Genera los golden de placa base, pedestal y losa desde el ORIGINAL (escritorio).

Uso (desde la raíz del repo):
    QT_QPA_PLATFORM=offscreen python workbench_module/scripts/golden_placa_pedestal_losa.py

Escribe en backend/motor_calculo/cad_drwr/golden/:
    placa_base.json, pedestal.json, losa.json  -> casos {nombre, params, drawing}
    placa_base_autofill.json                    -> casos {antes, campo, valor, despues}
"""
import json
import pathlib
import sys

from PySide6.QtWidgets import QCheckBox, QComboBox, QApplication

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GOLDEN = ROOT / "workbench_module/backend/motor_calculo/cad_drwr/golden"

sys.path.insert(0, str(ROOT))   # paquete ORIGINAL `generators`
sys.path.insert(0, str(HERE))   # golden_dump

from generators import MODULES  # noqa: E402
from golden_dump import dump    # noqa: E402


def modulo(prefix):
    return next(m for m in MODULES if m.prefix == prefix)


def caso(m, nombre, cambios=None):
    panel = m.panel()
    if cambios:
        panel.set_params(cambios)
    params = panel.params()
    return {"nombre": nombre, "params": params,
            "drawing": dump(m.builder(params))}


def casos_placa_base():
    return [
        caso(modulo("placa_base"), "ui_defaults"),
        caso(modulo("placa_base"), "n_pernos_6", {"n_pernos": "6"}),
        caso(modulo("placa_base"), "n_pernos_8_d22",
             {"n_pernos": "8", "d_perno": 22}),
        caso(modulo("placa_base"), "sin_cartelas_w310",
             {"perfil": "W310X39", "cartelas": False}),
        caso(modulo("placa_base"), "perfil_manual",
             {"perfil": "Manual", "d": 300, "bf": 200, "tw": 8, "tf": 12,
              "B": 500, "N": 520, "w_conc": 700}),
        caso(modulo("placa_base"), "escala_1_100_grout",
             {"escala": "1:100", "grout_mpa": 25, "material_placa": "A36",
              "material_perno": "F1554 Gr.36", "norma_soldadura": "AWS D1.1"}),
    ]


def casos_pedestal():
    return [
        caso(modulo("pedestal"), "ui_defaults"),
        caso(modulo("pedestal"), "n_barras_12", {"n_barras": "12"}),
        caso(modulo("pedestal"), "elevacion_off", {"elevacion": False}),
        caso(modulo("pedestal"), "H_600", {"H": 600}),
        caso(modulo("pedestal"), "d_barra_25_e12",
             {"d_barra": 25, "d_estribo": 10, "e_estribo": 12}),
        caso(modulo("pedestal"), "referencia_20", {"preset": "Referencia 20"}),
    ]


def casos_losa():
    return [
        caso(modulo("losa"), "ui_defaults"),
        caso(modulo("losa"), "sup_off", {"sup": False}),
        caso(modulo("losa"), "L_600", {"L": 600}),
        caso(modulo("losa"), "t_18_escala_1_25", {"t": 18, "escala": "1:25"}),
        caso(modulo("losa"), "d1_16_s1_15", {"d1": 16, "s1": 15}),
        caso(modulo("losa"), "escala_1_20_a200_L500",
             {"escala": "1:20", "L": 500, "a": 200}),
    ]


def caso_autofill(m, base, campo, valor):
    panel = m.panel()
    if base:
        panel.set_params(base)
    antes = panel.params()
    w = panel.w[campo]
    if isinstance(w, QComboBox):
        w.setCurrentText(str(valor))
    elif isinstance(w, QCheckBox):
        w.setChecked(bool(valor))
    else:
        w.setValue(valor)
    return {"antes": antes, "campo": campo, "valor": valor,
            "despues": panel.params()}


def casos_autofill_placa_base():
    m = modulo("placa_base")
    return [
        caso_autofill(m, None, "perfil", "W310X39"),
        caso_autofill(m, None, "perfil", "W150X24"),
        caso_autofill(m, None, "perfil", "Manual"),
        caso_autofill(m, None, "d", 300),
        caso_autofill(m, {"perfil": "W360X45"}, "perfil", "W200X22"),
        caso_autofill(m, None, "n_pernos", "8"),
        caso_autofill(m, None, "cartelas", False),
        caso_autofill(m, None, "d_perno", 22),
        caso_autofill(m, None, "escala", "1:100"),
    ]


def escribir(nombre, datos):
    GOLDEN.mkdir(parents=True, exist_ok=True)
    ruta = GOLDEN / nombre
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    print(f"escrito {ruta.relative_to(ROOT)} ({len(datos)} casos)")


def main():
    app = QApplication.instance() or QApplication([])  # noqa: F841 (mantener vivo)
    escribir("placa_base.json", casos_placa_base())
    escribir("pedestal.json", casos_pedestal())
    escribir("losa.json", casos_losa())
    escribir("placa_base_autofill.json", casos_autofill_placa_base())


if __name__ == "__main__":
    main()
