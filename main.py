# -*- coding: utf-8 -*-
"""
StructGen CAD — Generador automático de dibujos estructurales en DXF
compatible con AutoCAD y ZWCAD.

Uso:  python main.py
"""

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication
    from app.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("StructGen CAD")
    app.setOrganizationName("StructGen")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
