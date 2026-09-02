# -*- coding: utf-8 -*-
"""
app.main_window — Ventana principal: módulos + parámetros + vista previa.

Funciones: cambio de módulo, actualización en vivo (debounce), exportación
DXF individual o por lote, guardado/carga de plantillas JSON.
"""

import json
import os

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QListWidget,
                               QMainWindow, QMessageBox, QPushButton,
                               QSplitter, QStackedWidget, QStatusBar,
                               QVBoxLayout, QWidget)

from core import ir
from cad.dxf_out import write_dxf
from cad import com_live
from .preview import PreviewWidget
from generators import MODULES


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StructGen CAD — Generador de detalles "
                            "estructurales (AutoCAD / ZWCAD)")
        self.resize(1360, 860)

        self.panels = []
        self.stack = QStackedWidget()
        for m in MODULES:
            panel = m.panel()
            panel.params_changed.connect(self._schedule_refresh)
            self.panels.append(panel)
            self.stack.addWidget(panel)

        self.list = QListWidget()
        for m in MODULES:
            self.list.addItem(m.nombre)
        self.list.setFixedWidth(170)
        self.list.currentRowChanged.connect(self._module_changed)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(6, 6, 2, 6)
        lv.addWidget(QLabel("<b>Módulos</b>"))
        lv.addWidget(self.list)
        lv.addWidget(self.stack, 1)

        self.preview = PreviewWidget()

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.preview)
        split.setStretchFactor(1, 1)
        split.setSizes([360, 1000])
        self.setCentralWidget(split)

        # barra de herramientas
        tb = self.addToolBar("main")
        tb.setMovable(False)
        a_fit = QAction("Ajustar vista", self)
        a_fit.triggered.connect(self.preview.fit)
        tb.addAction(a_fit)
        a_dxf = QAction("Exportar DXF…", self)
        a_dxf.setShortcut(QKeySequence("Ctrl+E"))
        a_dxf.triggered.connect(self.export_dxf)
        tb.addAction(a_dxf)
        a_all = QAction("Exportar todo (DXF)…", self)
        a_all.triggered.connect(self.export_all)
        tb.addAction(a_all)
        tb.addSeparator()
        # --- conexión COM en vivo (AutoCAD / ZWCAD / BricsCAD abiertos) ---
        a_send = QAction("Enviar a CAD (COM)", self)
        a_send.setShortcut(QKeySequence("Ctrl+G"))
        a_send.setToolTip("Dibuja el detalle directamente en la sesión CAD "
                          "abierta (AutoCAD/ZWCAD) vía COM")
        a_send.triggered.connect(self.send_com)
        tb.addAction(a_send)
        a_open = QAction("Abrir DXF en CAD", self)
        a_open.setToolTip("Exporta un DXF temporal y lo abre en el CAD activo")
        a_open.triggered.connect(self.open_in_cad)
        tb.addAction(a_open)
        a_det = QAction("Detectar CAD", self)
        a_det.setToolTip("Prueba la conexión COM con el CAD abierto")
        a_det.triggered.connect(self.detect_cad)
        tb.addAction(a_det)
        tb.addSeparator()
        a_save = QAction("Guardar plantilla…", self)
        a_save.triggered.connect(self.save_template)
        tb.addAction(a_save)
        a_load = QAction("Cargar plantilla…", self)
        a_load.triggered.connect(self.load_template)
        tb.addAction(a_load)

        st = QStatusBar()
        self.setStatusBar(st)
        st.showMessage("Listo. Rueda: zoom  |  Arrastrar: paneo  |  "
                       "Doble clic: ajustar")

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self.refresh)

        self.list.setCurrentRow(0)
        self.refresh()

    # ------------------------------------------------------------- acciones --
    def _module_changed(self, row):
        self.stack.setCurrentIndex(row)
        self.refresh()

    def _schedule_refresh(self):
        self._timer.start()

    def current(self):
        row = self.list.currentRow()
        return MODULES[row], self.panels[row]

    def refresh(self):
        m, panel = self.current()
        try:
            dwg = m.builder(panel.params())
        except Exception as exc:  # parámetros inválidos, etc.
            self.statusBar().showMessage(f"Error en {m.nombre}: {exc}")
            return
        self.preview.set_drawing(dwg)
        self.preview.fit()
        self.statusBar().showMessage(
            f"{m.nombre}: {len(dwg.ents)} entidades  |  "
            "Rueda: zoom  |  Arrastrar: paneo  |  Doble clic: ajustar")

    def export_dxf(self):
        m, panel = self.current()
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar DXF", f"{m.prefix}.dxf",
            "Dibujo DXF (*.dxf)")
        if not path:
            return
        try:
            write_dxf(m.builder(panel.params()), path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{exc}")
            return
        self.statusBar().showMessage(f"DXF exportado: {path}")

    def export_all(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Carpeta para exportar todos los módulos")
        if not folder:
            return
        ok, errs = [], []
        for m, panel in zip(MODULES, self.panels):
            try:
                write_dxf(m.builder(panel.params()),
                          os.path.join(folder, f"{m.prefix}.dxf"))
                ok.append(m.prefix)
            except Exception as exc:
                errs.append(f"{m.nombre}: {exc}")
        msg = f"Exportados {len(ok)} DXF en:\n{folder}"
        if errs:
            msg += "\n\nErrores:\n" + "\n".join(errs)
        QMessageBox.information(self, "Exportación por lote", msg)

    # ---------------------------------------------------- conexión COM en vivo --
    def detect_cad(self):
        try:
            info = com_live.estado()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Conexión COM", str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, "Conexión COM",
                                f"No se pudo conectar:\n{exc}")
            return
        self.statusBar().showMessage(f"CAD conectado: {info}")
        QMessageBox.information(self, "Conexión COM",
                                f"CAD detectado correctamente:\n{info}")

    def send_com(self):
        """Dibuja el detalle actual directamente en el CAD abierto (COM)."""
        m, panel = self.current()
        try:
            dwg = m.builder(panel.params())
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Parámetros inválidos:\n{exc}")
            return
        try:
            info = com_live.enviar_dibujo(dwg)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Enviar a CAD (COM)", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Enviar a CAD (COM)",
                                 f"Fallo el envío en vivo:\n{exc}")
            return
        self.statusBar().showMessage(f"Enviado en vivo -> {info}")
        QMessageBox.information(self, "Enviar a CAD (COM)",
                                f"Dibujo enviado en vivo:\n{info}")

    def open_in_cad(self):
        """Exporta un DXF temporal y lo abre en el CAD activo."""
        m, panel = self.current()
        try:
            dwg = m.builder(panel.params())
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Parámetros inválidos:\n{exc}")
            return
        import tempfile
        path = os.path.join(tempfile.gettempdir(),
                            f"structgen_{m.prefix}.dxf")
        try:
            write_dxf(dwg, path)
            info = com_live.abrir_dxf_en_cad(path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Abrir DXF en CAD", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Abrir DXF en CAD",
                                 f"No se pudo abrir en el CAD:\n{exc}")
            return
        self.statusBar().showMessage(f"DXF abierto en {info}")

    def save_template(self):
        m, panel = self.current()
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar plantilla", f"{m.prefix}.json",
            "Plantilla JSON (*.json)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(panel.params(), fh, indent=2, ensure_ascii=False)
        self.statusBar().showMessage(f"Plantilla guardada: {path}")

    def load_template(self):
        m, panel = self.current()
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar plantilla", "", "Plantilla JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                panel.set_params(json.load(fh))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Plantilla inválida:\n{exc}")
            return
        self.refresh()
