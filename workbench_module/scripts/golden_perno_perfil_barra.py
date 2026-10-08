"""Genera los golden de perno_anclaje, perfil y forma_barra desde el ORIGINAL
de escritorio (generators/ en la raíz del repo, solo lectura).

Uso (desde la raíz del repo):
    QT_QPA_PLATFORM=offscreen python workbench_module/scripts/golden_perno_perfil_barra.py

Salida en backend/motor_calculo/cad_drwr/golden/:
    perno_anclaje.json, perfil.json, forma_barra.json, perfil_autofill.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
GOLDEN = os.path.join(ROOT, "workbench_module", "backend",
                      "motor_calculo", "cad_drwr", "golden")

sys.path.insert(0, HERE)   # golden_dump.py
sys.path.insert(0, ROOT)   # paquetes ORIGINALES: generators/, core/

from PySide6.QtWidgets import QApplication  # noqa: E402

from generators import MODULES  # noqa: E402  (original)
from golden_dump import dump  # noqa: E402

PREFIXES = ("perno_anclaje", "perfil", "forma_barra")

# Variantes por módulo: (nombre, {campo: valor}); se aplican con set_params.
CASOS = {
    "perno_anclaje": [
        ("L_d16_tabla_on", {
            "tipo": "L (codo 90°)", "d_nominal": "mm", "d_perno": 16,
            "Le": 850, "P": 400, "lg": 150, "n": 48, "tabla": True}),
        ("J_d22_A325_sin_tabla", {
            "tipo": "J (gancho 135°)", "d_nominal": "mm", "d_perno": 22,
            "material": "A325", "lg": 200, "tabla": False}),
        ("recto_placa_d19_F1554", {
            "tipo": "Recto con placa", "d_nominal": "mm", "d_perno": 19,
            "material": "F1554 Gr.55", "Le": 600, "P": 250, "n": 24}),
        ("PG_1in_galvanizado_UNC", {
            "tipo": "PG (recto con golilla)", "d_nominal": "1 in",
            "acabado": "Galvanizado en caliente", "tipo_hilo": "UNC",
            "Le": 850, "P": 400, "h1": 150, "h2": 75, "W": 75,
            "t_golilla": 20, "b_golilla": 50, "escala": "1:20"}),
        ("PG_mm_d25_4_A36", {
            "tipo": "PG (recto con golilla)", "d_nominal": "mm",
            "d_perno": 25.4, "material": "A36", "Le": 900, "P": 450,
            "h1": 150, "h2": 100, "W": 100, "t_golilla": 25,
            "b_golilla": 60, "tabla": True}),
        ("PG_mm_d32_h1_bajo_tc_sin_tabla", {
            "tipo": "PG (recto con golilla)", "d_nominal": "mm",
            "d_perno": 32, "material": "A307", "Le": 1000, "P": 300,
            "h1": 200, "h2": 100, "W": 120,
            "permitir_h1_bajo_tc": True, "tabla": False}),
    ],
    "perfil": [
        ("I_W_serie_W310X39", {
            "tipo": "Perfil I / W", "serie": "W310X39"}),
        ("H_HEA_serie_HE240A", {
            "tipo": "Perfil H (HEA)", "serie": "HE240A"}),
        ("canal_C_manual", {
            "serie": "—", "tipo": "Canal C", "d": 200, "bf": 75,
            "tw": 6, "tf": 9, "escala": "1:10"}),
        ("angulo_L_manual", {
            "serie": "—", "tipo": "Ángulo L", "d": 100, "bf": 75,
            "tw": 8, "tf": 8}),
        ("T_manual", {
            "serie": "—", "tipo": "T", "d": 300, "bf": 200,
            "tw": 10, "tf": 12}),
        ("caja_HSS_manual", {
            "serie": "—", "tipo": "Caja HSS", "d": 200, "bf": 150,
            "tw": 8, "tf": 8, "escala": "1:25"}),
    ],
    "forma_barra": [
        ("U_d25_k6", {
            "forma": "U", "a": 800, "b": 350, "d_barra": 25, "k": 6,
            "qty": 12, "marca": "B2"}),
        ("recta_d16", {
            "forma": "Recta", "a": 1200, "d_barra": 16, "qty": 5,
            "marca": "B3"}),
        ("gancho_90_d12", {
            "forma": "Gancho 90° (L)", "a": 800, "b": 150, "d_barra": 12,
            "qty": 20, "marca": "B4"}),
        ("estribo_135_d10_k2", {
            "forma": "Estribo 135°", "a": 300, "b": 200, "d_barra": 10,
            "k": 2, "qty": 40, "marca": "B5", "escala": "1:20"}),
        ("Z_d22_k3", {
            "forma": "Z", "a": 500, "b": 400, "c": 150, "d_barra": 22,
            "k": 3, "qty": 8, "marca": "B6"}),
    ],
}

# Casos de autollenado de perfil: (antes_set_params, campo, valor)
AUTOFILL_PERFIL = [
    ({}, "serie", "W310X39"),
    ({}, "serie", "HE240A"),
    ({}, "serie", "—"),
    ({}, "tipo", "Canal C"),
    ({"serie": "—", "d": 300, "bf": 200}, "serie", "W530X66"),
    ({}, "d", 300),
]


def _modulo(prefix):
    return next(m for m in MODULES if m.prefix == prefix)


def _panel_con(mod, cambios):
    panel = mod.panel()
    if cambios:
        panel.set_params(cambios)
    return panel


def _escribir(nombre, datos):
    with open(os.path.join(GOLDEN, nombre), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
        f.write("\n")


def _generar_modulo(prefix, errores):
    mod = _modulo(prefix)
    casos = [("ui_defaults", {})] + CASOS[prefix]
    salida = []
    for nombre, cambios in casos:
        panel = _panel_con(mod, cambios)
        params = panel.params()
        try:
            drawing = dump(mod.builder(params))
        except Exception as exc:  # el original falla: se anota y se quita
            errores.append(f"{prefix}:{nombre}: {type(exc).__name__}: {exc}")
            continue
        salida.append({"nombre": nombre, "params": params, "drawing": drawing})
    _escribir(prefix + ".json", salida)
    print(f"{prefix}.json: {len(salida)} casos")


def _generar_autofill(errores):
    mod = _modulo("perfil")
    salida = []
    for cambios, campo, valor in AUTOFILL_PERFIL:
        panel = _panel_con(mod, cambios)
        antes = panel.params()
        widget = panel.w[campo]
        if hasattr(widget, "setCurrentText"):
            widget.setCurrentText(str(valor))
        else:
            widget.setValue(valor)
        despues = panel.params()
        salida.append({"antes": antes, "campo": campo, "valor": valor,
                       "despues": despues})
    _escribir("perfil_autofill.json", salida)
    print(f"perfil_autofill.json: {len(salida)} casos")


def main():
    app = QApplication.instance() or QApplication([])  # noqa: F841
    os.makedirs(GOLDEN, exist_ok=True)
    errores = []
    for prefix in PREFIXES:
        _generar_modulo(prefix, errores)
    _generar_autofill(errores)
    for e in errores:
        print("ERROR ORIGINAL (variante descartada):", e)


if __name__ == "__main__":
    main()
