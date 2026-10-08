# -*- coding: utf-8 -*-
"""Reglas de interfaz de los Panel del escritorio, sin Qt.

Porta a funciones puras la lógica que el ORIGINAL ejecuta en ``on_change`` de
cada Panel: qué widgets quedan habilitados y qué valores cambia el autollenado
cuando el usuario modifica un campo. El golden que manda es
``golden/reglas_ui.json``, generado desde el ORIGINAL por
``scripts/golden_reglas_ui.py``.

Convenciones del estado ``p`` (equivalente a ``panel.params()``):
    * combos: ``str`` (p. ej. "16", nunca 16);
    * spin de precisión 0 (QSpinBox): ``int``;
    * spin con decimales (QDoubleSpinBox): ``float`` (p. ej. 55.0, no 55);
    * casillas: ``bool``.

Lo que NO está aquí, documentado del ORIGINAL:

``set_params`` (SpecPanel) asigna cada clave con setValue/setCurrentText, que
dispara ``on_change``. Por eso el resultado puede depender del orden del
diccionario recibido. Comprobado con el ORIGINAL:
    * placa_base: el autollenado corre solo si el emisor es ``perfil``. Con
      ``{"d": 300, "perfil": "W310X39"}`` queda d=310 (el autollenado pisa d);
      con ``{"perfil": "W310X39", "d": 300}`` queda d=300.
    * perfil: con serie conocida, d/bf/tw/tf se fuerzan al catálogo en
      cualquier orden (la serie bloquea las dimensiones).
    * pedestal: ``PedestalPanel.set_params`` aplica ``preset`` siempre primero
      (lo extrae del diccionario), así que el orden de b/h/etc. no influye.
      Si falta ``modo_b1`` usa "Manual (esquemático)" (el widget arranca en
      "Según elevación"). ``preset == "Legacy"`` se trata como "Total anterior".
    * perno_anclaje: ``set_params`` usa "mm" para ``d_nominal`` si falta. Con
      PG y "1 in" cualquier señal fuerza ``d_perno`` a "25.4".

Fuera de alcance: no se replican ``set_params`` ni la construcción de widgets.
"""

from . import anchor_bolt, base_plate, bar_shape, pedestal, profile, slab

# Módulos con reglas de interfaz (fundacion_sap es interactivo y no aplica).
_MODULOS = {
    "placa_base": base_plate,
    "pedestal": pedestal,
    "losa": slab,
    "perno_anclaje": anchor_bolt,
    "perfil": profile,
    "forma_barra": bar_shape,
}

_PRESET_DEFAULT = "Total anterior"
_PRESET_REF20 = "Referencia 20"
_PRESET_LEGADO = {"Legacy": "Total anterior"}

# Valores que el bloque "Referencia 20" del Panel fija al ENTRAR a ese modo.
# Tipos alineados con los widgets: b/h/r/e_estribo son float (decimales > 0),
# d_barra/d_estribo son combos (str).
_REF20_VALORES = {
    "b": 55.0,
    "h": 40.0,
    "r": 5.0,
    "d_barra": "16",
    "d_estribo": "10",
    "e_estribo": 15.0,
    "lazos_interiores": True,
    "lazo_vertical": True,
    "lazo_horizontal": True,
    "elevacion": False,
    "cuadro": False,
}


def _modulo(modulo_id):
    try:
        return _MODULOS[modulo_id]
    except KeyError:
        raise ValueError(f"módulo sin reglas de interfaz: {modulo_id!r}") from None


def _spec(modulo_id):
    return _modulo(modulo_id).SPEC


def _defaults(spec):
    """Valor inicial de cada clave del SPEC, igual que SpecPanel.__init__."""
    out = {}
    for row in spec:
        key, kind = row[0], row[2]
        if kind == "combo":
            opts = [str(o) for o in row[3]]
            out[key] = str(row[4]) if len(row) > 4 and str(row[4]) in opts else opts[0]
        elif kind in ("int", "float"):
            out[key] = row[5]
        elif kind == "chk":
            out[key] = bool(row[3])
    return out


def _estado(modulo_id, p):
    """Defaults del SPEC superpuestos con ``p`` (claves ausentes se completan)."""
    return {**_defaults(_spec(modulo_id)), **(p or {})}


def _preset(valor):
    return _PRESET_LEGADO.get(valor, valor)


def _igual(a, b):
    """Igualdad de valores de widget: numérica con tolerancia, resto exacta."""
    if isinstance(a, (bool, str)) or isinstance(b, (bool, str)):
        return a == b
    try:
        return abs(float(a) - float(b)) <= 1e-9
    except (TypeError, ValueError):
        return a == b


# --------------------------------------------------------- habilitados --
def _hab_pedestal(v):
    preset = _preset(v["preset"])
    por_caras = preset == "Por caras"
    lazos = bool(v["lazos_interiores"])
    out = {
        "largo_barra": v["modo_b1"] != "Según elevación",
        "n_barras": preset == "Total anterior",
        "lazo_vertical": lazos,
        "lazo_horizontal": lazos,
    }
    for clave in ("n_sup", "n_inf", "n_izq", "n_der"):
        out[clave] = por_caras
    return out


def _hab_perno(v):
    pg = str(v["tipo"]).startswith("PG")
    inch = pg and v["d_nominal"] == "1 in"
    out = {"d_perno": not inch, "lg": not pg}
    for clave in ("d_nominal", "h1", "h2", "W", "t_golilla", "b_golilla",
                  "permitir_h1_bajo_tc"):
        out[clave] = pg
    return out


_HABILITADOS = {
    "pedestal": _hab_pedestal,
    "perno_anclaje": _hab_perno,
}


def habilitados(modulo_id: str, p: dict) -> dict:
    """Para cada clave del SPEC, si el widget del Panel original queda habilitado.

    ``p`` es el estado tras el cambio (``panel.params()``). Las claves que el
    Panel no toca quedan habilitadas.
    """
    spec = _spec(modulo_id)
    out = {row[0]: True for row in spec}
    regla = _HABILITADOS.get(modulo_id)
    if regla is not None:
        out.update(regla(_estado(modulo_id, p)))
    return out


# ---------------------------------------------------------- autollenado --
def _pedestal_referencia(p, campo, previo):
    """Bloque "Referencia 20" de PedestalPanel.on_change.

    El original lo ejecuta solo en la TRANSICIÓN a ese modo
    (``_previous_mode != mode``), no en cada cambio mientras se está en él.
    Por eso exige ``campo == "preset"``, el nuevo preset y ``previo`` con otro.
    Devuelve solo las claves que difieren de ``p``.
    """
    if campo != "preset" or previo is None:
        return {}
    if _preset(p.get("preset")) != _PRESET_REF20:
        return {}
    if _preset(previo.get("preset", _PRESET_DEFAULT)) == _PRESET_REF20:
        return {}
    return {k: v for k, v in _REF20_VALORES.items() if not _igual(p.get(k), v)}


def autollenar_ui(modulo_id: str, p: dict, campo: str, previo: dict | None = None) -> dict:
    """Claves que el Panel original cambia cuando el usuario modifica ``campo``.

    ``p`` ya contiene el nuevo valor de ``campo``; ``previo`` es el estado
    anterior al cambio (necesario solo para la transición a "Referencia 20").
    Compone la ``autollenar`` del módulo (si existe) con la lógica de pedestal.
    """
    mod = _modulo(modulo_id)
    out = {}
    fn = getattr(mod, "autollenar", None)
    if fn is not None:
        out.update(fn(p, campo))
    if modulo_id == "pedestal":
        out.update(_pedestal_referencia(p, campo, previo))
    return out
