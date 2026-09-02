# -*- coding: utf-8 -*-
"""
generators.panels — Widgets de parámetros declarativos para PySide6.

Cada módulo declara su SPEC; `SpecPanel` construye el formulario y expone
params() / set_params(). Las señales notifican cambios para actualizar la
vista previa en vivo.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QLabel, QSpinBox,
                               QWidget)

from .data import factor_escala


def _spin(minv, maxv, val, step=1, suffix="", dec=0):
    if dec:
        w = QDoubleSpinBox()
        w.setDecimals(dec)
        w.setSingleStep(step)
    else:
        w = QSpinBox()
        w.setSingleStep(step)
    w.setRange(minv, maxv)
    w.setValue(val)
    if suffix:
        w.setSuffix(suffix)
    return w


class SpecPanel(QWidget):
    """Formulario generado a partir de SPEC.
    Tipos:  ("combo", opciones, por defecto)
            ("int", min, max, valor, paso, sufijo)
            ("float", min, max, valor, decimales, paso, sufijo)
            ("chk", valor_inicial)"""
    params_changed = Signal()

    SPEC = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self.w = {}
        form = QFormLayout(self)
        form.setContentsMargins(6, 6, 6, 6)
        form.setSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for row in self.SPEC:
            key, label, kind = row[0], row[1], row[2]
            if kind == "combo":
                opts = row[3]
                w = QComboBox()
                w.addItems([str(o) for o in opts])
                if len(row) > 4 and row[4] in opts:
                    w.setCurrentText(str(row[4]))
                w.currentTextChanged.connect(self._changed)
            elif kind == "int":
                w = _spin(row[3], row[4], row[5], row[6] if len(row) > 6 else 1,
                          row[7] if len(row) > 7 else "")
                w.valueChanged.connect(self._changed)
            elif kind == "float":
                w = _spin(row[3], row[4], row[5], row[7] if len(row) > 7 else 1.0,
                          row[8] if len(row) > 8 else "", dec=row[6])
                w.valueChanged.connect(self._changed)
            elif kind == "chk":
                w = QCheckBox()
                w.setChecked(bool(row[3]))
                w.toggled.connect(self._changed)
            else:
                continue
            self.w[key] = w
            form.addRow(label, w)
        self.after_spec()

    # ganchos para comportamiento extra (p. ej. autollenado de perfiles)
    def after_spec(self):
        # sincroniza los valores dependientes la primera vez
        self.on_change()

    def _changed(self, *_):
        self.on_change()
        self.params_changed.emit()

    def on_change(self):
        pass

    # ------------------------------------------------------------- API --
    def params(self) -> dict:
        p = {}
        for key, w in self.w.items():
            if isinstance(w, QComboBox):
                p[key] = w.currentText()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                p[key] = w.value()
            elif isinstance(w, QCheckBox):
                p[key] = w.isChecked()
        p["_escala"] = factor_escala(p.get("escala", "1:50"))
        return p

    def set_params(self, p: dict):
        for key, val in p.items():
            w = self.w.get(key)
            if w is None:
                continue
            try:
                if isinstance(w, QComboBox):
                    idx = w.findText(str(val))
                    if idx >= 0:
                        w.setCurrentIndex(idx)
                elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                    w.setValue(float(val))
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(val))
            except (TypeError, ValueError):
                pass

    # ------------------------------------------------------------ extras --
    def set_many(self, values: dict):
        """Asigna varios valores sin disparar múltiples eventos."""
        for k, v in values.items():
            w = self.w.get(k)
            if w is None:
                continue
            try:
                if isinstance(w, QComboBox):
                    idx = w.findText(str(v))
                    if idx >= 0:
                        w.setCurrentIndex(idx)
                elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                    w.setValue(float(v))
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(v))
            except (TypeError, ValueError):
                pass

    def note(self, text: str) -> None:
        lay = self.layout()
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setStyleSheet("color:#666; font-size:11px;")
        lay.addRow(lab)
