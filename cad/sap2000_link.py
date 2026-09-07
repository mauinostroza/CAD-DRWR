# -*- coding: utf-8 -*-
"""
cad.sap2000_link — Conexión de solo lectura con SAP2000 (COM/OAPI).

Lee la geometría de fundaciones ya modeladas en SAP2000 (nodos y shells de
área agrupados en un grupo de SAP2000) para dibujarlas en StructGenCAD.

Un grupo de SAP2000 puede contener más de una fundación física (varios
shells sin relación entre sí): se detectan las componentes conexas por
adyacencia de arista (`core.geom.agrupar_por_adyacencia`) y cada una se
resuelve a una `Zapata` con su contorno exterior único (esquinas reales,
`core.geom.contorno_exterior` + `simplificar_colineales`), su espesor por
shell y los pedestales (columnas) que nacen sobre ella — detección
portada de la app de referencia "Foundations SAP2000"
(`app/sap2000/pedestales_automaticos.py`): frames verticales cuyo pie
coincide con un joint de la malla de un shell, con su dimensión real leída
de `PropFrame.GetRectangle`/`GetCircle`.

Estrategia de conexión y criterio de tolerancia a firmas COM adaptados de
esa misma app de referencia (win32com late-binding, sin `gencache`, para
no invocar DISPID de otra versión de SAP2000 instalada y cerrarla a mitad
de la conexión). Requiere Windows + pywin32 (ya listado en
requirements.txt) y SAP2000 abierto con el modelo cargado.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.geom import agrupar_por_adyacencia, contorno_exterior, \
    simplificar_colineales

PROG_IDS = [
    "CSI.SAP2000.API.SapObject",
    "CSI.SAP2000.API.SapObject.1",
    "Sap2000.SapObject",
]

HELPER_PROG_IDS = [
    "CSI.SAP2000.API.Helper",
    "CSI.SAP2000.Helper",
    "SAP2000v1.Helper",
    "SAP2000.Helper",
]

UNIDADES_N_MM_C = 9  # eUnits de SAP2000: N, mm, °C

# Tolerancia (mm) para considerar un frame "vertical": variación máxima
# admitida en X/Y entre sus dos extremos. Unidades ya fijadas a mm
# (`set_units_mm`), a diferencia de la app de referencia (metros).
_EPS_VERTICAL_MM = 1.0

# Dimensión de relleno (mm) cuando no se pudo leer ni rectángulo ni
# círculo de la sección del pedestal — deliberadamente chica para que
# salte a la vista en la vista previa como un valor a revisar.
_DIMENSION_PLACEHOLDER_MM = 300.0


def _win32():
    """Importa win32com (solo Windows). Lanza RuntimeError con mensaje claro."""
    import os
    if os.name != "nt":
        raise RuntimeError(
            "La conexión con SAP2000 solo está disponible en Windows.")
    try:
        import win32com.client
        import win32com.client.dynamic
        return win32com.client
    except ImportError:
        raise RuntimeError(
            "pywin32 no está instalado. Ejecute:\n"
            "    pip install pywin32\n"
            "y vuelva a intentar la conexión.")


def _dispatch_tardio(win32com_client, prog_id: str):
    """Activa un objeto COM SIEMPRE con late binding (dynamic.Dispatch).

    `Dispatch`/`gencache` usan el caché makepy, generado contra la type
    library de la versión de SAP2000 registrada en ese momento; con varias
    versiones instaladas eso invoca los DISPID de una versión distinta de
    la que está corriendo y puede cerrarla a mitad de la conexión.
    `dynamic.Dispatch` resuelve cada método por nombre contra el objeto
    real, sin ese riesgo."""
    return win32com_client.dynamic.Dispatch(prog_id)


def _clean_com_error(e: Exception) -> str:
    msg = str(e)
    if hasattr(e, "args") and e.args:
        args = e.args[0]
        if isinstance(args, tuple) and len(args) >= 3:
            return f"{args[1]} (hresult={args[0]})"
        if isinstance(args, str):
            return args
    return msg


class SapLink:
    """Conexión de solo lectura con una instancia de SAP2000 abierta."""

    def __init__(self):
        self._sap_object = None
        self._sap_model = None

    @property
    def is_connected(self) -> bool:
        return self._sap_model is not None

    def get_sap_model(self):
        if not self.is_connected:
            raise RuntimeError("No hay conexión activa con SAP2000.")
        return self._sap_model

    def connect(self) -> str:
        """Se adjunta a una instancia de SAP2000 ya abierta (no abre una
        nueva: no tiene sentido leer geometría de un SAP2000 vacío).
        Devuelve un texto de estado o lanza RuntimeError."""
        win32com_client = _win32()
        errores: List[str] = []

        # Intento 1: Helper.GetObject (forma documentada por CSI para
        # adjuntarse a una instancia ya corriendo).
        for helper_id in HELPER_PROG_IDS:
            try:
                helper = _dispatch_tardio(win32com_client, helper_id)
            except Exception as e:
                errores.append(f"Dispatch(Helper {helper_id}): "
                               f"{_clean_com_error(e)}")
                continue
            for sap_obj_id in PROG_IDS:
                try:
                    sap_object = helper.GetObject(sap_obj_id)
                except Exception as e:
                    errores.append(f"Helper({helper_id}).GetObject"
                                   f"({sap_obj_id}): {_clean_com_error(e)}")
                    continue
                model = getattr(sap_object, "SapModel", None)
                if model is None:
                    errores.append(f"{sap_obj_id}: objeto sin SapModel")
                    continue
                self._sap_object = sap_object
                self._sap_model = model
                return self._info_modelo()

        # Intento 2: GetActiveObject (Running Object Table).
        for prog_id in PROG_IDS:
            try:
                sap_object = win32com_client.GetActiveObject(
                    prog_id, dynamic=True)
            except Exception as e:
                errores.append(f"GetActiveObject({prog_id}): "
                               f"{_clean_com_error(e)}")
                continue
            model = getattr(sap_object, "SapModel", None)
            if model is None:
                errores.append(f"GetActiveObject({prog_id}): "
                               "objeto sin SapModel")
                continue
            self._sap_object = sap_object
            self._sap_model = model
            return self._info_modelo()

        self._sap_object = None
        self._sap_model = None
        raise RuntimeError(
            "No se pudo conectar con SAP2000.\n"
            "Verifique que SAP2000 esté abierto con el modelo cargado y "
            "que 'Allow API Application Access' esté activo "
            "(File > Preferences > API).\n\n"
            "Detalle de los intentos:\n  - " + "\n  - ".join(errores))

    def _info_modelo(self) -> str:
        nombre = "Modelo sin guardar"
        try:
            ruta = self._sap_model.GetModelFilename()
            if isinstance(ruta, (list, tuple)):
                ruta = ruta[0] if ruta else ""
            if ruta:
                import os
                nombre = os.path.basename(str(ruta))
        except Exception:
            pass
        return f"SAP2000 conectado — modelo: {nombre}"

    def set_units_mm(self) -> int:
        """Fija unidades N-mm-°C y devuelve las unidades originales."""
        model = self.get_sap_model()
        original = None
        try:
            original = model.GetPresentUnits()
        except Exception:
            pass
        try:
            model.SetPresentUnits(UNIDADES_N_MM_C)
        except Exception as e:
            raise RuntimeError(f"No se pudo fijar unidades mm en SAP2000: "
                               f"{_clean_com_error(e)}")
        return original if isinstance(original, int) else 0

    def restore_units(self, original: int) -> None:
        if not original or not self.is_connected:
            return
        try:
            self._sap_model.SetPresentUnits(original)
        except Exception:
            pass


# ---------------------------------------------------- parseo tolerante --

def _parse_name_list(ret) -> List[str]:
    """Normaliza GetNameList/variantes COM a lista de strings, tolerando
    firmas (ret, count, names) / (count, names) / lista de strings."""
    if isinstance(ret, (list, tuple)) and ret and all(
            isinstance(x, str) for x in ret):
        return [str(x) for x in ret]
    if not isinstance(ret, (list, tuple)):
        return []
    for i in range(len(ret) - 1):
        names = ret[i + 1]
        if isinstance(names, (list, tuple)):
            try:
                count = int(ret[i])
                return [str(n) for n in names[:count]]
            except Exception:
                if all(isinstance(n, str) for n in names):
                    return [str(n) for n in names]
    return []


def _arrays_de_respuesta(raw) -> List[list]:
    """Filtra los elementos list/tuple de una respuesta COM, en orden —
    descarta el código de retorno y contadores escalares sin asumir una
    posición fija (las firmas ByRef varían según la versión de SAP2000)."""
    if not isinstance(raw, (list, tuple)):
        return []
    return [list(x) for x in raw if isinstance(x, (list, tuple))]


def listar_grupos(link: SapLink) -> List[str]:
    model = link.get_sap_model()
    try:
        ret = model.GroupDef.GetNameList()
    except Exception as e:
        raise RuntimeError(f"No se pudo listar los grupos de SAP2000: "
                           f"{_clean_com_error(e)}")
    return _parse_name_list(ret)


def _llamar_get_assignments(model, nombre_grupo: str):
    try:
        return model.GroupDef.GetAssignments(nombre_grupo, 0, [], [])
    except Exception:
        return model.GroupDef.GetAssignments(nombre_grupo)


def _parsear_get_assignments(ret) -> Tuple[list, list]:
    if not isinstance(ret, (list, tuple)):
        return [], []
    for i in range(len(ret) - 1):
        tipos, nombres = ret[i], ret[i + 1]
        if (isinstance(tipos, (list, tuple))
                and isinstance(nombres, (list, tuple))
                and len(tipos) == len(nombres) and len(tipos) > 0):
            try:
                return [int(t) for t in tipos], [str(n) for n in nombres]
            except Exception:
                continue
    return [], []


def miembros_de_grupo(link: SapLink, grupo: str) -> Dict[str, List[str]]:
    """Nodos (tipo 1) y shells (tipo 5) asignados a un grupo de SAP2000."""
    model = link.get_sap_model()
    try:
        ret = _llamar_get_assignments(model, grupo)
    except Exception as e:
        raise RuntimeError(f"No se pudieron leer los miembros del grupo "
                           f"'{grupo}': {_clean_com_error(e)}")
    tipos, nombres = _parsear_get_assignments(ret)
    return {
        "nodos": [nombres[i] for i in range(len(nombres)) if tipos[i] == 1],
        "shells": [nombres[i] for i in range(len(nombres)) if tipos[i] == 5],
    }


def coordenada(link: SapLink, nodo: str) -> Tuple[float, float, float]:
    """Coordenada cartesiana de un nodo (Point object), en las unidades
    activas del modelo (mm si se llamó `set_units_mm` antes)."""
    model = link.get_sap_model()
    try:
        ret = model.PointObj.GetCoordCartesian(str(nodo))
        if isinstance(ret, (list, tuple)) and len(ret) >= 4:
            if int(ret[0]) == 0:
                return (float(ret[1]), float(ret[2]), float(ret[3]))
    except Exception:
        pass
    try:
        import pythoncom
        import win32com.client
        x = win32com.client.VARIANT(pythoncom.VT_R8, 0.0)
        y = win32com.client.VARIANT(pythoncom.VT_R8, 0.0)
        z = win32com.client.VARIANT(pythoncom.VT_R8, 0.0)
        ret_code = model.PointObj.GetCoordCartesian(str(nodo), x, y, z)
        if ret_code == 0 or ret_code == (0,):
            return (float(x.value), float(y.value), float(z.value))
    except Exception:
        pass
    try:
        ret = model.PointObj.GetCoordCartesian(str(nodo))
        if isinstance(ret, (list, tuple)) and len(ret) >= 3:
            return (float(ret[0]), float(ret[1]), float(ret[2]))
    except Exception:
        pass
    raise RuntimeError(f"No se pudo leer la coordenada del nodo '{nodo}'.")


def puntos_de_area(link: SapLink, area: str) -> List[str]:
    """Nombres de los joints que forman el objeto de área tal como fue
    dibujado en SAP2000 (contorno del objeto, no de su malla de análisis)."""
    model = link.get_sap_model()
    try:
        raw = model.AreaObj.GetPoints(area)
    except Exception as e:
        raise RuntimeError(f"No se pudieron leer los puntos del área "
                           f"'{area}': {_clean_com_error(e)}")
    arrays = _arrays_de_respuesta(raw)
    for arr in arrays:
        if arr and all(isinstance(x, str) for x in arr):
            return [str(x) for x in arr]
    if isinstance(raw, (list, tuple)):
        nombres = [str(x) for x in raw if isinstance(x, str)]
        if nombres:
            return nombres
    raise RuntimeError(f"No se pudo interpretar AreaObj.GetPoints({area!r}).")


def seccion_de_area(link: SapLink, area: str) -> str:
    """Nombre de la propiedad de área (sección shell) asignada al objeto."""
    model = link.get_sap_model()
    try:
        ret = model.AreaObj.GetProperty(area)
    except Exception as e:
        raise RuntimeError(f"No se pudo leer la sección del área "
                           f"'{area}': {_clean_com_error(e)}")
    if isinstance(ret, (list, tuple)):
        nombres = [x for x in ret if isinstance(x, str) and x]
        if nombres:
            return nombres[0]
    if isinstance(ret, str) and ret:
        return ret
    raise RuntimeError(f"No se pudo interpretar AreaObj.GetProperty"
                       f"({area!r}).")


def elementos_de_area(link: SapLink, area: str) -> List[str]:
    """Nombres de los elementos de la malla de análisis (AreaElm) en que se
    subdivide un objeto de área — puede ser uno solo si no se subdividió."""
    model = link.get_sap_model()
    try:
        raw = model.AreaObj.GetElm(area)
    except Exception:
        return []
    arrays = _arrays_de_respuesta(raw)
    for arr in arrays:
        if arr and all(isinstance(x, str) for x in arr):
            return [str(x) for x in arr]
    if isinstance(raw, (list, tuple)):
        nombres = [str(x) for x in raw if isinstance(x, str)]
        if nombres:
            return nombres
    return []


def puntos_de_elemento(link: SapLink, elm: str) -> List[str]:
    """Nombres de los joints de un elemento de la malla de análisis
    (AreaElm) — incluye nodos intermedios que la malla automática agrega
    y que no son esquina del objeto de área (p. ej. el punto donde se
    apoya una columna al centro de una zapata de un solo shell)."""
    model = link.get_sap_model()
    try:
        raw = model.AreaElm.GetPoints(elm)
    except Exception:
        return []
    arrays = _arrays_de_respuesta(raw)
    for arr in arrays:
        if arr and all(isinstance(x, str) for x in arr):
            return [str(x) for x in arr]
    if isinstance(raw, (list, tuple)):
        nombres = [str(x) for x in raw if isinstance(x, str)]
        if nombres:
            return nombres
    return []


def joints_malla_de_area(link: SapLink, area: str) -> List[str]:
    """Todos los joints de la malla de análisis de un objeto de área
    (unión de los joints de cada uno de sus elementos), usada para detectar
    pedestales que se apoyan en un nodo interior generado por el mallado
    automático — mismo criterio que `diagramas_shell.py` en la app de
    referencia (`AreaObj.GetElm` + `AreaElm.GetPoints`)."""
    vistos = []
    for elm in elementos_de_area(link, area):
        for nombre in puntos_de_elemento(link, elm):
            if nombre not in vistos:
                vistos.append(nombre)
    return vistos


def espesor_de_seccion(link: SapLink, nombre_seccion: str) -> Optional[float]:
    """Espesor (mm, con unidades ya fijadas a N-mm-°C) de una propiedad de
    área tipo shell. La firma exacta de PropArea.GetShell no está
    verificada contra todas las versiones de SAP2000 (mismo problema ya
    documentado para otras llamadas OAPI de área): se buscan los valores
    float del resultado y se toma el más grande y razonable como espesor.
    Devuelve None si no se puede determinar — la UI lo deja editable."""
    model = link.get_sap_model()
    candidatos = []
    for metodo in ("GetShell", "GetShell_1"):
        try:
            fn = getattr(model.PropArea, metodo)
            ret = fn(nombre_seccion)
        except Exception:
            continue
        if not isinstance(ret, (list, tuple)):
            continue
        for v in ret:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if 0.5 <= fv <= 5000.0:      # rango plausible de espesor en mm
                candidatos.append(fv)
        if candidatos:
            break
    if not candidatos:
        return None
    return max(candidatos)


# --------------------------------------------------------- pedestales --
# Puerto de app/sap2000/pedestales_automaticos.py (Foundations SAP2000):
# frames verticales cuyo pie coincide con un joint que es esquina de algún
# shell del grupo, con su dimensión real leída de PropFrame.

def nombres_de_frames(link: SapLink) -> List[str]:
    model = link.get_sap_model()
    try:
        return _parse_name_list(model.FrameObj.GetNameList())
    except Exception:
        return []


def puntos_de_frame(link: SapLink, frame: str) -> Tuple[str, str]:
    model = link.get_sap_model()
    raw = model.FrameObj.GetPoints(frame)
    arrays = _arrays_de_respuesta(raw)
    if arrays:
        punto_i = str(arrays[0][0]) if arrays[0] else None
        punto_j = str(arrays[1][0]) if len(arrays) > 1 and arrays[1] else None
        if punto_i and punto_j:
            return punto_i, punto_j
    if isinstance(raw, (list, tuple)):
        candidatos = [str(x) for x in raw if isinstance(x, str)]
        if len(candidatos) >= 2:
            return candidatos[0], candidatos[1]
    raise RuntimeError(f"No se pudo interpretar FrameObj.GetPoints({frame!r}).")


def seccion_de_frame(link: SapLink, frame: str) -> str:
    model = link.get_sap_model()
    ret = model.FrameObj.GetSection(frame)
    if isinstance(ret, (list, tuple)):
        nombres = [x for x in ret if isinstance(x, str)]
        if nombres:
            return nombres[0]
    raise RuntimeError(f"No se pudo interpretar FrameObj.GetSection({frame!r}).")


def dimensiones_rectangulo_frame(link: SapLink,
                                 seccion: str) -> Tuple[float, float]:
    model = link.get_sap_model()
    ret = model.PropFrame.GetRectangle(seccion)
    # T3/T2 llegan como `float`; el código de retorno y `Color` son `int`
    # — filtrar por float aísla las dimensiones reales.
    dims = [v for v in ret if isinstance(v, float)] if isinstance(
        ret, (list, tuple)) else []
    if len(dims) >= 2 and dims[0] > 0 and dims[1] > 0:
        return float(dims[0]), float(dims[1])
    raise RuntimeError(f"PropFrame.GetRectangle({seccion!r}) no devolvió "
                       "dimensiones válidas.")


def dimensiones_circulo_frame(link: SapLink, seccion: str) -> Tuple[float, float]:
    model = link.get_sap_model()
    ret = model.PropFrame.GetCircle(seccion)
    dims = [v for v in ret if isinstance(v, float)] if isinstance(
        ret, (list, tuple)) else []
    if dims and dims[0] > 0:
        return float(dims[0]), float(dims[0])
    raise RuntimeError(f"PropFrame.GetCircle({seccion!r}) no devolvió un "
                       "diámetro válido.")


def orientacion_frame(link: SapLink, frame: str) -> bool:
    """`largo_en_x`: True si el lado "largo" de la sección queda sobre el
    eje X global. Sin lectura confiable de los ejes locales, se asume
    True por defecto (el usuario puede corregirlo en la vista previa)."""
    try:
        model = link.get_sap_model()
        ret = model.FrameObj.GetLocalAxes(frame)
        angulos = [v for v in ret if isinstance(v, (int, float))
                  and not isinstance(v, bool)] if isinstance(
            ret, (list, tuple)) else []
        if angulos:
            angulo = float(angulos[-1]) % 180.0
            return angulo < 45.0 or angulo >= 135.0
    except Exception:
        pass
    return True


@dataclass
class Pedestal:
    frame: str
    largo: float
    ancho: float
    largo_en_x: bool
    centro: Tuple[float, float]
    punto_pie: str
    aproximado: bool = False
    motivo_aviso: str = ""


def detectar_pedestales(link: SapLink,
                        coords: Dict[str, Tuple[float, float, float]]
                        ) -> List[Pedestal]:
    """Recorre todos los frames del modelo y devuelve los candidatos a
    pedestal: frames verticales cuyo extremo inferior coincide con un
    joint de `coords` (típicamente las esquinas de los shells de un
    grupo/fundación)."""
    candidatos: List[Pedestal] = []
    for frame in nombres_de_frames(link):
        try:
            punto_i, punto_j = puntos_de_frame(link, frame)
            xi, yi, zi = coordenada(link, punto_i)
            xj, yj, zj = coordenada(link, punto_j)
        except Exception:
            continue

        vertical = (abs(xi - xj) < _EPS_VERTICAL_MM
                   and abs(yi - yj) < _EPS_VERTICAL_MM
                   and abs(zi - zj) > _EPS_VERTICAL_MM)
        if not vertical:
            continue

        if zi <= zj:
            punto_pie, (x_pie, y_pie) = punto_i, (xi, yi)
        else:
            punto_pie, (x_pie, y_pie) = punto_j, (xj, yj)

        if punto_pie not in coords:
            continue

        try:
            seccion = seccion_de_frame(link, frame)
        except Exception:
            continue

        aproximado = False
        motivo_aviso = ""
        try:
            largo, ancho = dimensiones_rectangulo_frame(link, seccion)
        except Exception:
            try:
                largo, ancho = dimensiones_circulo_frame(link, seccion)
                aproximado = True
                motivo_aviso = "Sección circular, aproximada como cuadrado"
            except Exception:
                largo = ancho = _DIMENSION_PLACEHOLDER_MM
                aproximado = True
                motivo_aviso = ("Sección no reconocida, dimensión de "
                                "relleno — revisar manualmente")

        largo_en_x = orientacion_frame(link, frame)
        candidatos.append(Pedestal(
            frame=frame, largo=largo, ancho=ancho, largo_en_x=largo_en_x,
            centro=(x_pie, y_pie), punto_pie=punto_pie,
            aproximado=aproximado, motivo_aviso=motivo_aviso))
    return candidatos


# ------------------------------------------------------- modelo de datos --

@dataclass
class AreaGeom:
    nombre: str
    seccion: str
    espesor: Optional[float]
    pts_nombres: List[str]
    pts: List[Tuple[float, float, float]]
    pts_malla: List[str] = field(default_factory=list)


@dataclass
class Zapata:
    """Una fundación física (componente conexa de shells) dentro de un
    grupo de SAP2000."""
    nombre: str
    areas: List[AreaGeom] = field(default_factory=list)
    contorno: List[Tuple[float, float]] = field(default_factory=list)
    pedestales: List[Pedestal] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "areas": [
                {"nombre": a.nombre, "seccion": a.seccion,
                 "espesor": a.espesor, "pts_nombres": list(a.pts_nombres),
                 "pts": [list(p) for p in a.pts],
                 "pts_malla": list(a.pts_malla)}
                for a in self.areas
            ],
            "contorno": [list(p) for p in self.contorno],
            "pedestales": [
                {"frame": pd.frame, "largo": pd.largo, "ancho": pd.ancho,
                 "largo_en_x": pd.largo_en_x, "centro": list(pd.centro),
                 "punto_pie": pd.punto_pie, "aproximado": pd.aproximado,
                 "motivo_aviso": pd.motivo_aviso}
                for pd in self.pedestales
            ],
        }

    @staticmethod
    def from_dict(d: dict) -> "Zapata":
        return Zapata(
            nombre=d.get("nombre", ""),
            areas=[
                AreaGeom(a["nombre"], a["seccion"], a.get("espesor"),
                        list(a.get("pts_nombres", [])),
                        [tuple(p) for p in a["pts"]],
                        list(a.get("pts_malla", [])))
                for a in d.get("areas", [])
            ],
            contorno=[tuple(p) for p in d.get("contorno", [])],
            pedestales=[
                Pedestal(pd["frame"], pd["largo"], pd["ancho"],
                        pd["largo_en_x"], tuple(pd["centro"]),
                        pd.get("punto_pie", ""), pd.get("aproximado", False),
                        pd.get("motivo_aviso", ""))
                for pd in d.get("pedestales", [])
            ],
        )


@dataclass
class FundacionGeom:
    nombre: str
    zapatas: List[Zapata] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"nombre": self.nombre,
                "zapatas": [z.to_dict() for z in self.zapatas]}

    @staticmethod
    def from_dict(d: dict) -> "FundacionGeom":
        return FundacionGeom(
            nombre=d.get("nombre", ""),
            zapatas=[Zapata.from_dict(z) for z in d.get("zapatas", [])])


def leer_fundacion(link: SapLink, grupo: str) -> FundacionGeom:
    """Lee de SAP2000 toda la geometría de un grupo: separa sus shells en
    fundaciones físicas independientes (componentes conexas por arista
    compartida), calcula el contorno exterior único de cada una (esquinas
    reales, sin vértices colineales) y detecta los pedestales que nacen
    sobre cada una."""
    miembros = miembros_de_grupo(link, grupo)
    nombres_shells = miembros["shells"]

    original_units = link.set_units_mm()
    try:
        areas: List[AreaGeom] = []
        coords: Dict[str, Tuple[float, float, float]] = {}
        # Joints de la malla de análisis (superconjunto de las esquinas del
        # objeto): necesarios para detectar pedestales apoyados en un nodo
        # interior de una zapata de un solo shell (el caso más común), no
        # solo en sus 4 esquinas — mismo criterio que `diagramas_shell.py`
        # en la app de referencia.
        coords_malla: Dict[str, Tuple[float, float, float]] = {}
        for area in nombres_shells:
            nombres_pts = puntos_de_area(link, area)
            pts = [coordenada(link, p) for p in nombres_pts]
            for nombre_pt, xyz in zip(nombres_pts, pts):
                coords[nombre_pt] = xyz
                coords_malla[nombre_pt] = xyz
            try:
                seccion = seccion_de_area(link, area)
            except RuntimeError:
                seccion = ""
            espesor = espesor_de_seccion(link, seccion) if seccion else None

            pts_malla = joints_malla_de_area(link, area)
            for nombre_pt in pts_malla:
                if nombre_pt not in coords_malla:
                    try:
                        coords_malla[nombre_pt] = coordenada(link, nombre_pt)
                    except RuntimeError:
                        continue
            if not pts_malla:
                pts_malla = list(nombres_pts)

            areas.append(AreaGeom(area, seccion, espesor, nombres_pts, pts,
                                  pts_malla))

        if not areas:
            raise RuntimeError(f"El grupo '{grupo}' no tiene shells asignados.")

        pedestales = detectar_pedestales(link, coords_malla)

        componentes = agrupar_por_adyacencia([a.pts_nombres for a in areas])
        zapatas: List[Zapata] = []
        for k, idxs in enumerate(componentes):
            areas_comp = [areas[i] for i in idxs]
            nombres_contorno = contorno_exterior(
                [a.pts_nombres for a in areas_comp])
            contorno_xy = [coords[n][:2] for n in nombres_contorno]
            contorno_xy = simplificar_colineales(contorno_xy)

            joints_malla_comp = {n for a in areas_comp for n in a.pts_malla}
            pedestales_comp = [p for p in pedestales
                               if p.punto_pie in joints_malla_comp]

            nombre_zapata = (pedestales_comp[0].frame
                            if len(pedestales_comp) == 1 else f"F{k + 1}")
            zapatas.append(Zapata(nombre=nombre_zapata, areas=areas_comp,
                                  contorno=contorno_xy,
                                  pedestales=pedestales_comp))
    finally:
        link.restore_units(original_units)

    return FundacionGeom(nombre=grupo, zapatas=zapatas)
