# -*- coding: utf-8 -*-
"""Pruebas sin CAD real para el puente de selección de punto por comando."""

import unittest
from unittest.mock import patch

from cad import com_live


class _PythonCom:
    def PumpWaitingMessages(self):
        pass


class _Documento:
    def __init__(self, resultado):
        self.vars = {"USERR1": 11.0, "USERR2": 22.0, "USERR3": 33.0}
        self.resultado = resultado
        self.comando = ""

    def GetVariable(self, nombre):
        return self.vars[nombre]

    def SetVariable(self, nombre, valor):
        self.vars[nombre] = value = float(valor)

    def SendCommand(self, comando):
        self.comando = comando
        if self.resultado == "ok":
            self.vars.update({"USERR1": 125.5, "USERR2": -42.25,
                              "USERR3": -123456.0})
        elif self.resultado == "cancel":
            self.vars["USERR3"] = 0.0


class CommandPointTests(unittest.TestCase):
    @patch("cad.com_live.random.randint", return_value=123456)
    @patch("cad.com_live.time.sleep")
    def test_reads_point_and_restores_user_variables(self, _sleep, _random):
        doc = _Documento("ok")
        punto = com_live._pedir_punto_por_comando(doc, "Indique punto", _PythonCom())
        self.assertEqual(punto, (125.5, -42.25))
        self.assertIn("getpoint", doc.comando)
        self.assertIn("USERR3", doc.comando)
        self.assertEqual(doc.vars, {"USERR1": 11.0, "USERR2": 22.0,
                                    "USERR3": 33.0})

    @patch("cad.com_live.random.randint", return_value=123456)
    @patch("cad.com_live.time.sleep")
    def test_cancel_is_reported_and_restores_user_variables(self, _sleep, _random):
        doc = _Documento("cancel")
        with self.assertRaisesRegex(RuntimeError, "cancelada"):
            com_live._pedir_punto_por_comando(doc, "Indique punto", _PythonCom())
        self.assertEqual(doc.vars, {"USERR1": 11.0, "USERR2": 22.0,
                                    "USERR3": 33.0})
