# -*- coding: utf-8 -*-
"""
generators.foundation_sap — Fundación leída desde un modelo SAP2000.

Se conecta a una instancia de SAP2000 abierta, permite elegir una
fundación (un grupo de SAP2000 con nodos y shells asignados) y dibuja:
planta con el contorno real de cada shell (acotada), considerando el
espesor de la propiedad de área asignada, y una elevación individual como
corte real de la geometría según el eje (X o Y) y posición elegidos.

A diferencia de los demás módulos, el panel no es un formulario estático
(SpecPanel): el flujo es interactivo (conectar -> elegir grupo -> ajustar
corte), así que implementa a mano el mismo contrato mínimo que usa
MainWindow: params(), set_params() y la señal params_changed.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from cad import sap2000_link as sap
from .data import ESCALAS, factor_escala
from core import ir
from core.ir import Circle, Poly, Text
from core.geom import corte_poligono, level_symbol
from core.dims import DimBuilder


# ----------------------------------------------------------------- panel --
class FoundationSapPanel(QWidget):
    params_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._link = sap.SapLink()
        self._cache = {}          # {nombre_grupo: FundacionGeom}
        self._grupos_shell = []   # grupos con al menos un shell

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        self.btn_conectar = QPushButton("Conectar a SAP2000")
        self.btn_conectar.clicked.connect(self._conectar)
        lay.addWidget(self.btn_conectar)

        self.lbl_estado = QLabel("Sin conexión.")
        self.lbl_estado.setWordWrap(True)
        self.lbl_estado.setStyleSheet("color:#666; font-size:11px;")
        lay.addWidget(self.lbl_estado)

        form = QFormLayout()
        form.setSpacing(6)

        self.cb_fundacion = QComboBox()
        self.cb_fundacion.currentTextChanged.connect(self._fundacion_changed)
        form.addRow("Fundación (grupo SAP2000)", self.cb_fundacion)

        self.cb_eje = QComboBox()
        self.cb_eje.addItems(["X", "Y"])
        self.cb_eje.currentTextChanged.connect(self._changed)
        form.addRow("Corte perpendicular a", self.cb_eje)

        self.sp_pos = QDoubleSpinBox()
        self.sp_pos.setRange(-1e7, 1e7)
        self.sp_pos.setDecimals(0)
        self.sp_pos.setSuffix(" mm")
        self.sp_pos.valueChanged.connect(self._changed)
        form.addRow("Posición del corte", self.sp_pos)

        pos_btns = QHBoxLayout()
        self.btn_centrar = QPushButton("Centrar")
        self.btn_centrar.clicked.connect(self._centrar_corte)
        self.btn_columna = QPushButton("En columna")
        self.btn_columna.clicked.connect(self._corte_en_columna)
        pos_btns.addWidget(self.btn_centrar)
        pos_btns.addWidget(self.btn_columna)
        form.addRow("", pos_btns)

        self.sp_espesor = QDoubleSpinBox()
        self.sp_espesor.setRange(0, 5000)
        self.sp_espesor.setDecimals(0)
        self.sp_espesor.setSuffix(" mm")
        self.sp_espesor.valueChanged.connect(self._changed)
        form.addRow("Espesor por defecto", self.sp_espesor)

        self.cb_escala = QComboBox()
        self.cb_escala.addItems(ESCALAS)
        self.cb_escala.setCurrentText("1:50")
        self.cb_escala.currentTextChanged.connect(self._changed)
        form.addRow("Escala de acotado", self.cb_escala)

        lay.addLayout(form)
        lay.addStretch(1)
        self._set_controles_habilitados(False)

    # ------------------------------------------------------------ acciones --
    def _set_controles_habilitados(self, on: bool):
        for w in (self.cb_fundacion, self.cb_eje, self.sp_pos,
                  self.btn_centrar, self.btn_columna, self.sp_espesor):
            w.setEnabled(on)

    def _conectar(self):
        try:
            info = self._link.connect()
            grupos = sap.listar_grupos(self._link)
            self._grupos_shell = []
            for g in grupos:
                try:
                    miembros = sap.miembros_de_grupo(self._link, g)
                except RuntimeError:
                    continue
                if miembros["shells"]:
                    self._grupos_shell.append(g)
        except RuntimeError as exc:
            self.lbl_estado.setText(str(exc))
            QMessageBox.warning(self, "Conectar a SAP2000", str(exc))
            return
        except Exception as exc:
            msg = f"No se pudo conectar:\n{exc}"
            self.lbl_estado.setText(msg)
            QMessageBox.critical(self, "Conectar a SAP2000", msg)
            return

        self._cache.clear()
        self.cb_fundacion.blockSignals(True)
        self.cb_fundacion.clear()
        self.cb_fundacion.addItems(self._grupos_shell)
        self.cb_fundacion.blockSignals(False)

        if not self._grupos_shell:
            self.lbl_estado.setText(
                f"{info}\nNo hay grupos con shells asignados. Cree un "
                "grupo en SAP2000 con los nodos y shells de la fundación.")
            self._set_controles_habilitados(False)
            return

        self.lbl_estado.setText(info)
        self._set_controles_habilitados(True)
        self._fundacion_changed(self.cb_fundacion.currentText())

    def _geom_actual(self):
        nombre = self.cb_fundacion.currentText()
        return self._cache.get(nombre)

    def _fundacion_changed(self, nombre: str):
        if not nombre:
            return
        if nombre not in self._cache:
            try:
                self._cache[nombre] = sap.leer_fundacion(self._link, nombre)
            except RuntimeError as exc:
                self.lbl_estado.setText(str(exc))
                QMessageBox.warning(self, "Leer fundación", str(exc))
                return
            except Exception as exc:
                msg = f"No se pudo leer la fundación:\n{exc}"
                self.lbl_estado.setText(msg)
                QMessageBox.critical(self, "Leer fundación", msg)
                return
        geom = self._cache[nombre]
        espesores = [a.espesor for a in geom.areas if a.espesor]
        self.sp_espesor.blockSignals(True)
        self.sp_espesor.setValue(espesores[0] if espesores else 0)
        self.sp_espesor.blockSignals(False)
        self._centrar_corte()
        self._changed()

    def _bbox(self, geom):
        xs = [p[0] for a in geom.areas for p in a.pts]
        ys = [p[1] for a in geom.areas for p in a.pts]
        return min(xs), max(xs), min(ys), max(ys)

    def _centrar_corte(self):
        geom = self._geom_actual()
        if geom is None:
            return
        x0, x1, y0, y1 = self._bbox(geom)
        valor = (x0 + x1) / 2.0 if self.cb_eje.currentText() == "X" \
            else (y0 + y1) / 2.0
        self.sp_pos.blockSignals(True)
        self.sp_pos.setValue(valor)
        self.sp_pos.blockSignals(False)
        self._changed()

    def _corte_en_columna(self):
        geom = self._geom_actual()
        if geom is None or not geom.nodos_libres:
            return
        eje_i = 0 if self.cb_eje.currentText() == "X" else 1
        vals = [c[eje_i] for _, c in geom.nodos_libres]
        self.sp_pos.blockSignals(True)
        self.sp_pos.setValue(sum(vals) / len(vals))
        self.sp_pos.blockSignals(False)
        self._changed()

    def _changed(self, *_):
        self.params_changed.emit()

    # ------------------------------------------------------------- API --
    def params(self) -> dict:
        geom = self._geom_actual()
        return {
            "_escala": factor_escala(self.cb_escala.currentText()),
            "escala": self.cb_escala.currentText(),
            "fundacion": self.cb_fundacion.currentText(),
            "eje_corte": self.cb_eje.currentText(),
            "pos_corte": self.sp_pos.value(),
            "espesor_default": self.sp_espesor.value(),
            "_geom": geom.to_dict() if geom is not None else None,
        }

    def set_params(self, p: dict):
        geom_d = p.get("_geom")
        if geom_d:
            geom = sap.FundacionGeom.from_dict(geom_d)
            self._cache[geom.nombre] = geom
            self.cb_fundacion.blockSignals(True)
            if self.cb_fundacion.findText(geom.nombre) < 0:
                self.cb_fundacion.addItem(geom.nombre)
            self.cb_fundacion.setCurrentText(geom.nombre)
            self.cb_fundacion.blockSignals(False)
            self._set_controles_habilitados(True)
        if "eje_corte" in p:
            self.cb_eje.setCurrentText(str(p["eje_corte"]))
        if "escala" in p:
            self.cb_escala.setCurrentText(str(p["escala"]))
        if "pos_corte" in p:
            self.sp_pos.setValue(float(p["pos_corte"]))
        if "espesor_default" in p:
            self.sp_espesor.setValue(float(p["espesor_default"]))


# -------------------------------------------------------------- generador --
def build_foundation(p: dict) -> ir.Drawing:
    geom_d = p.get("_geom")
    if not geom_d or not geom_d.get("areas"):
        raise ValueError("Conecte a SAP2000 y elija una fundación con "
                         "shells asignados.")

    f = p.get("_escala", 5.0)
    th = 3.0 * f
    d = ir.Drawing()
    db = DimBuilder(d.ents, th)

    areas = geom_d["areas"]
    nodos_libres = geom_d.get("nodos_libres", [])
    espesor_default = p.get("espesor_default", 0.0)

    xs = [pt[0] for a in areas for pt in a["pts"]]
    ys = [pt[1] for a in areas for pt in a["pts"]]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0

    def loc(pt):
        return (pt[0] - cx, pt[1] - cy)

    # ============================ PLANTA ============================
    for a in areas:
        pts_xy = [loc(pt) for pt in a["pts"]]
        d.ents.append(Poly(pts_xy, closed=True, layer=ir.L_CONC))
        for px, py in pts_xy:
            d.ents.append(Circle((px, py), 1.2 * f, ir.L_EJE))
    for nombre, coord in nodos_libres:
        px, py = loc(coord)
        d.ents.append(Circle((px, py), 1.6 * f, ir.L_EJE))
        d.ents.append(Text((px + 3 * f, py + 3 * f), nombre, 2.0 * f,
                           0, ir.L_TXT, "l", "b"))

    xs_l = sorted(set(round(x - cx, 1) for x in xs))
    ys_l = sorted(set(round(y - cy, 1) for y in ys))
    x0, x1 = xs_l[0], xs_l[-1]
    y0, y1 = ys_l[0], ys_l[-1]

    y_dim1 = y0 - 30 * f
    if len(xs_l) > 2:
        db.h_chain(xs_l, y0, y_dim1, ext_from=y0)
        y_dim1 -= 30 * f
    db.h_total(x0, x1, y0, y_dim1, ext_from=y0)
    x_dim1 = x1 + 30 * f
    if len(ys_l) > 2:
        db.v_chain(ys_l, x1, x_dim1, ext_from=x1)
        x_dim1 += 30 * f
    db.v_total(y0, y1, x1, x_dim1, ext_from=x1)

    # ========================== ELEVACIÓN ===========================
    eje = "x" if p.get("eje_corte", "X") == "X" else "y"
    centro_eje = cx if eje == "x" else cy
    pos = p.get("pos_corte", centro_eje) - centro_eje

    espesores = [a.get("espesor") or espesor_default for a in areas]
    esp_max = max(espesores) if espesores else espesor_default
    ex = x1 + 200 * f                # centro horizontal de la elevación

    tramos = []   # (a, b, espesor)
    for a, esp in zip(areas, espesores):
        pts_xy = [loc(pt) for pt in a["pts"]]
        for t0, t1 in corte_poligono(pts_xy, eje, pos):
            tramos.append((t0, t1, esp if esp else espesor_default))

    if not tramos:
        d.ents.append(Text((ex, 0), "EL CORTE NO ATRAVIESA NINGÚN SHELL",
                           3.0 * f, 0, ir.L_TXT, "c", "m"))
    else:
        centro_tramos = (min(t[0] for t in tramos) +
                         max(t[1] for t in tramos)) / 2.0
        for t0, t1, esp in tramos:
            xa = ex + (t0 - centro_tramos)
            xb = ex + (t1 - centro_tramos)
            d.ents.append(ir.rect(xa, -esp, xb, 0, ir.L_CONC))
        d.ents.extend(level_symbol(
            (ex - (max(t[1] for t in tramos) -
                  min(t[0] for t in tramos)) / 2.0 - 25 * f, 0),
            th, "N.P. ±0.00"))

        t_min = min(t[0] for t in tramos) - centro_tramos
        t_max = max(t[1] for t in tramos) - centro_tramos
        y_dim2 = -esp_max - 30 * f
        db.h_total(ex + t_min, ex + t_max, -esp_max, y_dim2, ext_from=-esp_max)
        db.v_total(-esp_max, 0, ex + t_max, ex + t_max + 30 * f,
                  ext_from=ex + t_max)

    nombres_sec = ", ".join(sorted({a["seccion"] for a in areas if a["seccion"]}))
    d.ents.append(Text(
        (ex, -esp_max - 60 * f),
        f"FUNDACIÓN {geom_d['nombre']}" +
        (f"  -  SEC. {nombres_sec}" if nombres_sec else "") +
        f"  -  ESC {p.get('escala', '1:50')}",
        4.0 * f, 0, ir.L_TXT, "c", "m"))
    return d
