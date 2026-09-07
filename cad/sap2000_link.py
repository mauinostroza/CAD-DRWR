# -*- coding: utf-8 -*-
"""
cad.sap2000_link — Conexión de solo lectura con SAP2000 (COM/OAPI).

Lee la geometría de fundaciones ya modeladas en SAP2000 (nodos y shells de
área agrupados en un grupo de SAP2000) para dibujarlas en StructGenCAD:
planta con el contorno real de cada shell y espesor de su propiedad de
área asignada.

Estrategia de conexión y criterio de tolerancia a firmas COM adaptados de
la app de referencia "Foundations SAP2000" (win32com late-binding, sin
`gencache`, para no invocar DISPID de otra versión de SAP2000 instalada y
cerrarla a mitad de la conexión). Requiere Windows + pywin32 (ya listado
en requirements.txt) y SAP2000 abierto con el modelo cargado.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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


@dataclass
class AreaGeom:
    nombre: str
    seccion: str
    espesor: Optional[float]
    pts: List[Tuple[float, float, float]]


@dataclass
class FundacionGeom:
    nombre: str
    areas: List[AreaGeom] = field(default_factory=list)
    nodos_libres: List[Tuple[str, Tuple[float, float, float]]] = field(
        default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "areas": [
                {"nombre": a.nombre, "seccion": a.seccion,
                 "espesor": a.espesor, "pts": [list(p) for p in a.pts]}
                for a in self.areas
            ],
            "nodos_libres": [[n, list(c)] for n, c in self.nodos_libres],
        }

    @staticmethod
    def from_dict(d: dict) -> "FundacionGeom":
        return FundacionGeom(
            nombre=d.get("nombre", ""),
            areas=[
                AreaGeom(a["nombre"], a["seccion"], a.get("espesor"),
                        [tuple(p) for p in a["pts"]])
                for a in d.get("areas", [])
            ],
            nodos_libres=[(n, tuple(c)) for n, c in d.get("nodos_libres", [])],
        )


def leer_fundacion(link: SapLink, grupo: str) -> FundacionGeom:
    """Lee de SAP2000 toda la geometría de una fundación (grupo): contorno
    y espesor de cada shell, y los nodos del grupo que no pertenecen a
    ningún shell (típicamente columnas/pedestales)."""
    miembros = miembros_de_grupo(link, grupo)
    nombres_shells = miembros["shells"]
    nombres_nodos = set(miembros["nodos"])

    original_units = link.set_units_mm()
    try:
        areas = []
        nodos_usados = set()
        for area in nombres_shells:
            nombres_pts = puntos_de_area(link, area)
            pts = [coordenada(link, p) for p in nombres_pts]
            nodos_usados.update(nombres_pts)
            try:
                seccion = seccion_de_area(link, area)
            except RuntimeError:
                seccion = ""
            espesor = espesor_de_seccion(link, seccion) if seccion else None
            areas.append(AreaGeom(area, seccion, espesor, pts))

        nodos_libres = []
        for nodo in nombres_nodos - nodos_usados:
            nodos_libres.append((nodo, coordenada(link, nodo)))
    finally:
        link.restore_units(original_units)

    if not areas:
        raise RuntimeError(f"El grupo '{grupo}' no tiene shells asignados.")
    return FundacionGeom(nombre=grupo, areas=areas, nodos_libres=nodos_libres)
