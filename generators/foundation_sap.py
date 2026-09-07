# -*- coding: utf-8 -*-
"""
generators.foundation_sap — Fundaciones leídas desde un modelo SAP2000.

Se conecta a una instancia de SAP2000 abierta y permite elegir un grupo de
SAP2000 con nodos y shells asignados. Un grupo puede contener más de una
fundación física (shells sin relación entre sí): cada una se resuelve por
separado (`cad.sap2000_link.leer_fundacion`) a una "zapata" con su
contorno exterior único (solo esquinas reales), el espesor de cada shell
y los pedestales (columnas) detectados sobre ella.

Cada zapata se dibuja en planta en su posición real dentro del modelo
(sin recolocarla), y con dos elevaciones (corte real, no bounding-box) —
una perpendicular a X y otra a Y, "sus dos lados" — dispuestas en una
fila aparte, lejos de las plantas y sin traslape entre ellas.

A diferencia de los demás módulos, el panel no es un formulario estático
(SpecPanel): el flujo es interactivo (conectar -> elegir grupo), así que
implementa a mano el mismo contrato mínimo que usa MainWindow: params(),
set_params() y la señal params_changed.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout,
                               QLabel, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from cad import sap2000_link as sap
from .data import ESCALAS, factor_escala
from core import ir
from core.ir import Poly, Text
from core.geom import corte_poligono, level_symbol
from core.dims import DimBuilder

GAP_ELEV = 200.0       # mm entre las 2 elevaciones (ejeX/ejeY) de una zapata
GAP_FILA_ZAPATA = 300.0    # mm entre el par de elevaciones de zapatas vecinas
GAP_FILA = 400.0       # mm entre la fila de plantas y la fila de elevaciones
ALTO_ARRANQUE_COL = 300.0   # mm, tramo de columna dibujado sobre la zapata


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
        form.addRow("Grupo SAP2000", self.cb_fundacion)

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
        for w in (self.cb_fundacion, self.sp_espesor):
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
        espesores = [a.espesor for z in geom.zapatas for a in z.areas
                    if a.espesor]
        self.sp_espesor.blockSignals(True)
        self.sp_espesor.setValue(espesores[0] if espesores else 0)
        self.sp_espesor.blockSignals(False)
        self.lbl_estado.setText(
            f"Grupo '{nombre}': {len(geom.zapatas)} fundación(es) "
            f"detectada(s).")
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
        if "escala" in p:
            self.cb_escala.setCurrentText(str(p["escala"]))
        if "espesor_default" in p:
            self.sp_espesor.setValue(float(p["espesor_default"]))


# ------------------------------------------------------------ geometría --

def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def _dibujar_pedestal(d, pos, pedestal, f, layer=ir.L_ACERO):
    cx, cy = pos
    largo, ancho = pedestal["largo"], pedestal["ancho"]
    hx, hy = (largo / 2.0, ancho / 2.0) if pedestal["largo_en_x"] \
        else (ancho / 2.0, largo / 2.0)
    d.ents.append(ir.rect(cx - hx, cy - hy, cx + hx, cy + hy, layer))
    etiqueta = pedestal["frame"]
    if pedestal["aproximado"]:
        etiqueta += " (aprox.)"
    d.ents.append(Text((cx, cy), etiqueta, 2.0 * f, 0, ir.L_TXT, "c", "m"))


def _dibujar_zapata_planta(d, db, zapata, f, th):
    """Dibuja la zapata en su posición real (coordenadas globales del
    modelo, sin recentrar ni trasladar). Devuelve el y mínimo alcanzado
    por su dibujo (contorno + acotado + rótulo), para saber dónde
    empieza, lejos de todas las plantas, la fila de elevaciones."""
    contorno = [(p[0], p[1]) for p in zapata["contorno"]]
    d.ents.append(Poly(contorno, closed=True, layer=ir.L_CONC))

    for pedestal in zapata["pedestales"]:
        _dibujar_pedestal(d, pedestal["centro"], pedestal, f)

    xs_l = sorted(set(round(p[0], 1) for p in contorno))
    ys_l = sorted(set(round(p[1], 1) for p in contorno))
    lx0, lx1 = xs_l[0], xs_l[-1]
    ly0, ly1 = ys_l[0], ys_l[-1]
    cx = (lx0 + lx1) / 2.0

    y_dim1 = ly0 - 30 * f
    if len(xs_l) > 2:
        db.h_chain(xs_l, ly0, y_dim1, ext_from=ly0)
        y_dim1 -= 30 * f
    db.h_total(lx0, lx1, ly0, y_dim1, ext_from=ly0)
    x_dim1 = lx1 + 30 * f
    if len(ys_l) > 2:
        db.v_chain(ys_l, lx1, x_dim1, ext_from=lx1)
        x_dim1 += 30 * f
    db.v_total(ly0, ly1, lx1, x_dim1, ext_from=lx1)

    y_label = y_dim1 - 60 * f
    d.ents.append(Text((cx, y_label), zapata["nombre"], 3.5 * f,
                       0, ir.L_TXT, "c", "m"))
    return y_label - 15 * f


def _dibujar_zapata_elevacion(d, db, zapata, eje, offset_x, y0_off, f, th,
                              espesor_default):
    """Dibuja UNA elevación (corte real perpendicular a `eje`) de la
    zapata, aislada de todo lo demás (solo usa los shells propios de esa
    zapata). Devuelve (x_min_usado, x_max_usado, esp_max): el rango real
    de X ocupado por TODO lo dibujado (cortes, arranques de columna,
    cota y rótulo), para que el llamador pueda ubicar la siguiente
    elevación sin traslape."""
    x0, x1, y0, y1 = _bbox(zapata["contorno"])
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    titulo = f"{zapata['nombre']} — CORTE EJE {'X' if eje == 'x' else 'Y'}"

    if zapata["pedestales"]:
        px = sum(p["centro"][0] for p in zapata["pedestales"]) / \
            len(zapata["pedestales"])
        py = sum(p["centro"][1] for p in zapata["pedestales"]) / \
            len(zapata["pedestales"])
    else:
        px, py = cx, cy
    pos_corte = px if eje == "x" else py

    tramos = []   # (a, b, espesor)
    for a in zapata["areas"]:
        pts_xy = [(p[0], p[1]) for p in a["pts"]]
        esp = a.get("espesor") or espesor_default
        for t0, t1 in corte_poligono(pts_xy, eje, pos_corte):
            tramos.append((t0, t1, esp if esp else espesor_default))

    centro_transv = cy if eje == "x" else cx

    def loc_t(t):
        return offset_x + (t - centro_transv)

    if not tramos:
        d.ents.append(Text((offset_x, y0_off),
                           f"{titulo}: EL CORTE AUTOMÁTICO NO ATRAVIESA "
                           "NINGÚN SHELL", 2.5 * f, 0, ir.L_TXT, "c", "m"))
        ancho_txt = 0.6 * 2.5 * f * len(titulo) / 2.0
        return offset_x - ancho_txt, offset_x + ancho_txt, 0.0

    esp_max = max(t[2] for t in tramos)
    for t0, t1, esp in tramos:
        d.ents.append(ir.rect(loc_t(t0), y0_off - esp, loc_t(t1), y0_off,
                              ir.L_CONC))

    t_min = min(t[0] for t in tramos)
    t_max = max(t[1] for t in tramos)
    x_min_usado = loc_t(t_min) - 25 * f    # símbolo de nivel a la izquierda
    x_max_usado = loc_t(t_max)

    d.ents.extend(level_symbol((loc_t(t_min) - 25 * f, y0_off), th,
                               "N.P. ±0.00"))

    alto_col = ALTO_ARRANQUE_COL * f / 5.0
    for pedestal in zapata["pedestales"]:
        centro_ped = pedestal["centro"][1] if eje == "x" else \
            pedestal["centro"][0]
        ancho_ped = pedestal["ancho"] if (
            (eje == "x") == pedestal["largo_en_x"]) else pedestal["largo"]
        xa = loc_t(centro_ped) - ancho_ped / 2.0
        xb = loc_t(centro_ped) + ancho_ped / 2.0
        d.ents.append(ir.rect(xa, y0_off, xb, y0_off + alto_col,
                              ir.L_ACERO))
        x_min_usado = min(x_min_usado, xa)
        x_max_usado = max(x_max_usado, xb)

    y_dim2 = y0_off - esp_max - 30 * f
    db.h_total(loc_t(t_min), loc_t(t_max), y0_off - esp_max, y_dim2,
              ext_from=y0_off - esp_max)
    x_cota_v = loc_t(t_max) + 30 * f
    db.v_total(y0_off - esp_max, y0_off, loc_t(t_max), x_cota_v,
              ext_from=loc_t(t_max))
    x_max_usado = max(x_max_usado, x_cota_v + 15 * f)

    nombres_sec = ", ".join(sorted({a["seccion"] for a in zapata["areas"]
                                    if a["seccion"]}))
    rotulo = titulo + (f"  -  SEC. {nombres_sec}" if nombres_sec else "")
    d.ents.append(Text(
        (offset_x, y0_off - esp_max - 60 * f), rotulo, 2.5 * f,
        0, ir.L_TXT, "c", "m"))
    ancho_rotulo = 0.6 * 2.5 * f * len(rotulo) / 2.0
    x_min_usado = min(x_min_usado, offset_x - ancho_rotulo)
    x_max_usado = max(x_max_usado, offset_x + ancho_rotulo)

    return x_min_usado, x_max_usado, esp_max


# -------------------------------------------------------------- generador --
def build_foundation(p: dict) -> ir.Drawing:
    geom_d = p.get("_geom")
    zapatas = geom_d.get("zapatas") if geom_d else None
    if not zapatas:
        raise ValueError("Conecte a SAP2000 y elija un grupo con shells "
                         "asignados.")

    f = p.get("_escala", 5.0)
    th = 3.0 * f
    d = ir.Drawing()
    db = DimBuilder(d.ents, th)
    espesor_default = p.get("espesor_default", 0.0)

    # ===================== PLANTAS (posición real) =====================
    # Cada zapata se dibuja en sus coordenadas reales del modelo, sin
    # recolocarla: conservan su posición relativa unas con otras.
    y_min_plantas = 0.0
    for zapata in zapatas:
        y_bottom = _dibujar_zapata_planta(d, db, zapata, f, th)
        y_min_plantas = min(y_min_plantas, y_bottom)

    # ========================== ELEVACIONES ===========================
    # Fila aparte, lejos de todas las plantas. Dos elevaciones por zapata
    # (corte eje X y corte eje Y, "sus dos lados"), cada una aislada del
    # resto y sin traslape entre bloques (el ancho de avance del cursor
    # es el rango real de X que ocupó cada elevación, no una estimación).
    y_fila_elev = y_min_plantas - GAP_FILA * f
    cursor_x = 0.0
    for zapata in zapatas:
        for eje in ("x", "y"):
            inicio = len(d.ents)
            x_min, x_max, esp = _dibujar_zapata_elevacion(
                d, db, zapata, eje, cursor_x, y_fila_elev, f, th,
                espesor_default)
            # El dibujo queda centrado en cursor_x (no alineado a su
            # borde izquierdo) — se traslada lo recién agregado para que
            # su borde izquierdo real (x_min) coincida con cursor_x,
            # garantizando que no invada el bloque anterior.
            shift = cursor_x - x_min
            if abs(shift) > 1e-6:
                bloque = ir.translate(ir.Drawing(ents=d.ents[inicio:]),
                                      shift, 0.0)
                d.ents[inicio:] = bloque.ents
                x_max += shift
            cursor_x = x_max + GAP_ELEV * f
        cursor_x += GAP_FILA_ZAPATA * f

    return d
