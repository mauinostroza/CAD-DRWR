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
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout,
                               QLabel, QListWidget, QMainWindow, QMessageBox,
                               QProgressDialog, QPushButton, QSplitter,
                               QStackedWidget, QStatusBar, QVBoxLayout,
                               QWidget)
from PySide6.QtWidgets import QInputDialog

from core import ir
from core.sheet import compose_sheet
from core.layout_review import annotation_overlaps
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
        self.sheet_metadata = {}
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
        self.a_sheet = QAction("Lámina con cajetín", self)
        self.a_sheet.setCheckable(True)
        self.a_sheet.triggered.connect(self.refresh)
        tb.addAction(self.a_sheet)
        a_meta = QAction("Datos del plano…", self)
        a_meta.triggered.connect(self.edit_sheet_metadata)
        tb.addAction(a_meta)
        a_review = QAction("Revisar anotaciones", self)
        a_review.triggered.connect(self.review_annotations)
        tb.addAction(a_review)
        tb.addSeparator()
        # --- conexión COM en vivo (AutoCAD / ZWCAD / BricsCAD abiertos) ---
        a_send = QAction("Enviar a CAD (COM)", self)
        a_send.setShortcut(QKeySequence("Ctrl+G"))
        a_send.setToolTip("Dibuja el detalle directamente en la sesión CAD "
                          "abierta (AutoCAD/ZWCAD) vía COM")
        a_send.triggered.connect(self.send_com)
        tb.addAction(a_send)
        self.a_pick = QAction("Ubicar con clic", self)
        self.a_pick.setCheckable(True)
        self.a_pick.setChecked(True)
        self.a_pick.setToolTip("Antes de enviar, pide un clic en pantalla "
                               "dentro del CAD para ubicar el dibujo ahí")
        tb.addAction(self.a_pick)
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
        self.preview.fit()

    def _schedule_refresh(self):
        self._timer.start()

    def current(self):
        row = self.list.currentRow()
        return MODULES[row], self.panels[row]

    def build_current(self, module, panel):
        params = panel.params()
        drawing = module.builder(params)
        if self.a_sheet.isChecked():
            scale = float(str(params.get("escala", "1:25")).split(":")[-1])
            drawing = compose_sheet(drawing, scale=scale, title=module.nombre,
                                    project=self.sheet_metadata.get("proyecto", ""),
                                    number=self.sheet_metadata.get("numero_plano", ""),
                                    revision=self.sheet_metadata.get("revision", ""))
        return drawing

    def edit_sheet_metadata(self):
        values = dict(self.sheet_metadata)
        for key, label in (("proyecto", "Proyecto"), ("numero_plano", "Número de plano"),
                           ("revision", "Revisión")):
            value, accepted = QInputDialog.getText(self, "Datos del plano", label,
                                                   text=values.get(key, ""))
            if not accepted:
                return
            values[key] = value
        self.sheet_metadata = values
        self.refresh()

    def review_annotations(self):
        collisions = annotation_overlaps(self.preview.dwg)
        message = (f"{len(collisions)} posibles solapes de texto. Estimación geométrica; "
                   "confirme las fuentes y el ploteo en CAD.\n\n" +
                   "\n".join(f"{a} ↔ {b}" for a,b in collisions[:15]))
        QMessageBox.information(self, "Revisión de anotaciones", message)

    def refresh(self):
        m, panel = self.current()
        try:
            dwg = self.build_current(m, panel)
        except Exception as exc:  # parámetros inválidos, etc.
            self.preview.set_drawing(ir.Drawing())
            self.statusBar().showMessage(f"Error en {m.nombre}: {exc}")
            return
        self.preview.set_drawing(dwg)
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
            write_dxf(self.build_current(m, panel), path)
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
                write_dxf(self.build_current(m, panel),
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

    def _pedir_punto_con_reintento(self, app, doc):
        """Pide el punto de inserción; si falla por RPC_E_SERVERFAULT
        (el CAD no aceptó el foco forzado automáticamente — puede pasar
        en algunos entornos/versiones de Windows pese a AttachThreadInput),
        ofrece un último recurso: que el usuario cambie manualmente a la
        ventana del CAD (Alt+Tab) y confirme, momento en el que el CAD sí
        es el foco real (acción directa del usuario, que Windows siempre
        permite). Devuelve el punto, o None si el usuario cancela."""
        try:
            return com_live.pedir_punto(app=app, doc=doc)
        except RuntimeError as exc:
            if "RPC_E_SERVERFAULT" not in str(exc) and \
                    "-2147417851" not in str(exc):
                raise
        # Reintento manual: el usuario cambia de ventana él mismo.
        self.showNormal()
        resp = QMessageBox.question(
            self, "Enviar a CAD (COM)",
            "El CAD no aceptó el punto de forma automática.\n\n"
            "Cambie manualmente a la ventana de ZWCAD/AutoCAD (Alt+Tab) "
            "y presione Reintentar para hacer clic ahí.",
            QMessageBox.Retry | QMessageBox.Cancel, QMessageBox.Retry)
        if resp != QMessageBox.Retry:
            return None
        self.showMinimized()
        return com_live.pedir_punto(app=app, doc=doc)

    def send_com(self):
        """Dibuja el detalle actual directamente en el CAD abierto (COM)."""
        m, panel = self.current()
        try:
            dwg = self.build_current(m, panel)
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Parámetros inválidos:\n{exc}")
            return

        self.statusBar().showMessage("Conectando con el CAD…")
        QApplication.processEvents()
        try:
            app, pid = com_live.detectar()
        except RuntimeError as exc:
            self.statusBar().showMessage(str(exc))
            QMessageBox.warning(self, "Enviar a CAD (COM)", str(exc))
            return
        except Exception as exc:
            self.statusBar().showMessage("Error al conectar con el CAD.")
            QMessageBox.critical(self, "Enviar a CAD (COM)",
                                 f"No se pudo conectar:\n{exc}")
            return
        try:
            doc = com_live.documento_activo(app)
        except Exception as exc:
            self.statusBar().showMessage("Error al conectar con el CAD.")
            QMessageBox.critical(self, "Enviar a CAD (COM)",
                                 f"No se pudo obtener el documento activo:\n{exc}")
            return

        origen = None
        if self.a_pick.isChecked():
            # Forzar el foco del CAD ANTES de minimizar la ventana propia:
            # una vez minimizada, Windows puede denegar en silencio que
            # nuestro proceso (ya en segundo plano) le robe el foco a otra
            # ventana — hacerlo mientras todavía somos la ventana activa
            # es lo que realmente evita el RPC_E_SERVERFAULT de GetPoint.
            com_live.traer_al_frente(app)
            self.statusBar().showMessage(
                "Haga clic en la ventana de ZWCAD/AutoCAD para ubicar el "
                "dibujo (Esc para cancelar)…")
            QApplication.processEvents()
            self.showMinimized()
            try:
                origen = self._pedir_punto_con_reintento(app, doc)
            except RuntimeError as exc:
                self.showNormal()
                self.statusBar().showMessage(str(exc))
                return
            except Exception as exc:
                self.showNormal()
                QMessageBox.critical(self, "Enviar a CAD (COM)",
                                     f"No se pudo pedir el punto:\n{exc}")
                return
            self.showNormal()
            if origen is None:
                self.statusBar().showMessage("Envío cancelado.")
                return

        progreso = QProgressDialog("Enviando dibujo a CAD…", None, 0, 100, self)
        progreso.setWindowTitle("Enviar a CAD (COM)")
        progreso.setMinimumDuration(0)
        progreso.setCancelButton(None)
        progreso.setValue(0)
        progreso.show()
        QApplication.processEvents()

        def _progreso(hechas, total):
            progreso.setValue(int(100 * hechas / total) if total else 100)
            QApplication.processEvents()

        try:
            info = com_live.enviar_dibujo(dwg, origen=origen, app=app,
                                          doc=doc, pid=pid,
                                          progress_cb=_progreso)
        except RuntimeError as exc:
            progreso.close()
            QMessageBox.warning(self, "Enviar a CAD (COM)", str(exc))
            return
        except Exception as exc:
            progreso.close()
            QMessageBox.critical(self, "Enviar a CAD (COM)",
                                 f"Fallo el envío en vivo:\n{exc}")
            return
        progreso.close()
        self.statusBar().showMessage(f"Enviado en vivo -> {info}")
        QMessageBox.information(self, "Enviar a CAD (COM)",
                                f"Dibujo enviado en vivo:\n{info}")

    def open_in_cad(self):
        """Exporta un DXF temporal y lo abre en el CAD activo."""
        m, panel = self.current()
        try:
            dwg = self.build_current(m, panel)
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
            json.dump({**panel.params(), "_sheet_metadata": self.sheet_metadata,
                       "_sheet_enabled": self.a_sheet.isChecked()}, fh,
                      indent=2, ensure_ascii=False)
        self.statusBar().showMessage(f"Plantilla guardada: {path}")

    def load_template(self):
        m, panel = self.current()
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar plantilla", "", "Plantilla JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                values = json.load(fh)
                self.sheet_metadata = values.pop("_sheet_metadata", {})
                self.a_sheet.setChecked(bool(values.pop("_sheet_enabled", False)))
                panel.set_params(values)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Plantilla inválida:\n{exc}")
            return
        self.refresh()
