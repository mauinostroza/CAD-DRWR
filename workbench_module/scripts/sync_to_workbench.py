#!/usr/bin/env python3
"""Copia el módulo CAD-DRWR a un CLON LOCAL del workbench y aplica las ediciones
aditivas en los archivos compartidos. NUNCA toca el remoto: solo escribe en TARGET.

Uso:
    python workbench_module/scripts/sync_to_workbench.py TARGET [--commit SHA]

Es idempotente: cada edición comprueba si ya está aplicada y falla en voz alta si
el ancla esperada no existe (el workbench cambió y hay que revisar el script).
"""

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

ORIGEN = pathlib.Path(__file__).resolve().parents[1]
REPO = ORIGEN.parent

COPIAS_DIR = [
    "backend/motor_calculo/cad_drwr",
    "web/src/cad_drwr",
]
COPIAS_ARCHIVO = [
    "backend/routers/cad_drwr.py",
    "bridge/cad_drwr.py",
    "bridge/cad_drwr_sap.py",
    "bridge/cad_com_live.py",
    "bridge/cad_sap_link.py",
]
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "*.tsbuildinfo")


class AnclaFaltante(RuntimeError):
    pass


def reemplazar_una_vez(texto, ancla, nuevo, marca, archivo):
    """Inserta `nuevo` justo DESPUÉS de `ancla` si `marca` aún no está en el texto."""
    if marca in texto:
        return texto, False
    if texto.count(ancla) != 1:
        raise AnclaFaltante(f"{archivo}: el ancla aparece {texto.count(ancla)} veces: {ancla[:70]!r}")
    return texto.replace(ancla, ancla + nuevo, 1), True


def escribir(path, texto, cambiado, log, nombre):
    if cambiado:
        path.write_text(texto, encoding="utf-8")
        log.append(f"editado   {nombre}")
    else:
        log.append(f"sin cambio {nombre} (ya aplicado)")


def copiar(target, log):
    for rel in COPIAS_DIR:
        dst = target / rel
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ORIGEN / rel, dst, ignore=IGNORAR)
        log.append(f"copiado   {rel}/")
    for rel in COPIAS_ARCHIVO:
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ORIGEN / rel, target / rel)
        log.append(f"copiado   {rel}")
    for t in sorted((ORIGEN / "tests").glob("test_*.py")):
        nombre = "test_cad_drwr_" + t.name[len("test_"):]
        nombre = nombre.replace("cad_drwr_bridge_cad_drwr", "cad_drwr_bridge").replace(
            "cad_drwr_router_cad_drwr", "cad_drwr_router")
        shutil.copy2(t, target / "tests" / nombre)
        log.append(f"copiado   tests/{nombre}")


def parchear_integrados(target, log):
    """Añade la entrada AL FINAL de MODULOS (el orden lo fija tests/test_integrados.py)."""
    p = target / "backend/integrados.py"
    t = p.read_text(encoding="utf-8")
    if "app_id='cad_drwr'" in t:
        log.append("sin cambio backend/integrados.py (ya aplicado)")
        return
    ancla = "\n)\n\n_ERRORES"
    if t.count(ancla) != 1:
        raise AnclaFaltante("backend/integrados.py: no se encontró el cierre de MODULOS")
    nuevo = (
        "    ModuloIntegrado(\n"
        "        app_id='cad_drwr',\n"
        "        nombre='CAD-DRWR',\n"
        "        descripcion='Detalles estructurales 2D (placa base, pedestal, losa, perno, perfil, barra, "
        "fundaciones SAP2000) con exportación DXF y envío a ZWCAD/AutoCAD.',\n"
        "        router='backend.routers.cad_drwr:router',\n"
        "        requiere=(),\n"
        "    ),"
    )
    t = t.replace(ancla, "\n" + nuevo + ancla, 1)
    p.write_text(t, encoding="utf-8")
    log.append("editado   backend/integrados.py")

def parchear_actions(target, log):
    p = target / "bridge/actions.py"
    t = p.read_text(encoding="utf-8")
    ancla = "    install_equilibrio_routes(app, call)\n"
    nuevo = (
        "\n    from bridge.cad_drwr import install_routes as install_cad_drwr_routes\n\n"
        "    install_cad_drwr_routes(app, call)\n"
    )
    t, c = reemplazar_una_vez(t, ancla, nuevo, "install_cad_drwr_routes", "bridge/actions.py")
    escribir(p, t, c, log, "bridge/actions.py")


def parchear_contratos(target, log):
    p = target / "web/src/bridge_contracts.json"
    t = p.read_text(encoding="utf-8")
    nuevos = json.loads((ORIGEN / "web/src/cad_drwr/bridge_contracts.cad_drwr.json").read_text("utf-8"))["routes"]
    existentes = json.loads(t)["routes"]
    faltan = {k: v for k, v in nuevos.items() if k not in existentes}
    if not faltan:
        log.append("sin cambio web/src/bridge_contracts.json (ya aplicado)")
        return
    lineas = "".join(
        f"    {json.dumps(k, ensure_ascii=False)}: {json.dumps({kk: vv for kk, vv in v.items() if kk != 'opcionales'}, ensure_ascii=False)},\n"
        for k, v in faltan.items()
    )
    # Antes de las rutas de emparejamiento: test_previous_contract_keys_are_intact fija el orden
    # del resto y solo tolera que las dos últimas (pairing) se desplacen.
    ancla = '    "POST /v1/sap/pairing/request"'
    if t.count(ancla) != 1:
        raise AnclaFaltante("web/src/bridge_contracts.json: no se encontró la ruta de emparejamiento")
    p.write_text(t.replace(ancla, lineas + ancla, 1), encoding="utf-8")
    log.append(f"editado   web/src/bridge_contracts.json (+{len(faltan)} rutas)")


ICONO = '''
export function CadDrwrIcon({ size = 24, stroke = '#1C1C1F', className }: IconProps) {
  return (
    <svg {...base(size)} viewBox="0 0 24 24" className={className} xmlns="http://www.w3.org/2000/svg">
      <rect x="4" y="14" width="16" height="6" stroke={stroke} strokeWidth={1.4} />
      <rect x="9" y="4" width="6" height="10" stroke={stroke} strokeWidth={1.4} />
      <path d="M2 22h20M12 2v2" stroke={stroke} strokeWidth={1} strokeLinecap="round" />
    </svg>
  )
}
'''


def parchear_iconos(target, log):
    p = target / "web/src/icons.tsx"
    t = p.read_text(encoding="utf-8")
    if "export function CadDrwrIcon" in t:
        log.append("sin cambio web/src/icons.tsx (ya aplicado)")
        return
    p.write_text(t.rstrip("\n") + "\n" + ICONO, encoding="utf-8")
    log.append("editado   web/src/icons.tsx (+CadDrwrIcon)")


def siguiente_short(texto):
    cifras = [int(n) for n in re.findall(r"short: '(\d+)'", texto)]
    return f"{max(cifras) + 1:02d}"


def parchear_shell(target, log):
    """Registra la ruta con anclas relativas al FINAL de cada bloque (el workbench sigue creciendo)."""
    p = target / "web/src/Shell.tsx"
    t = p.read_text(encoding="utf-8")
    if "id: 'cad_drwr'" in t:
        log.append("sin cambio web/src/Shell.tsx (ya aplicado)")
        return
    # 1) icono en el import
    ancla = "import {\n  ArrowIcon,\n"
    if t.count(ancla) != 1:
        raise AnclaFaltante("web/src/Shell.tsx: no se encontró el import de iconos")
    t = t.replace(ancla, ancla + "  CadDrwrIcon,\n", 1)
    # 2) tipo Route (se añade al final de la línea)
    m = re.search(r"^type Route = .*$", t, flags=re.M)
    if not m:
        raise AnclaFaltante("web/src/Shell.tsx: no se encontró `type Route`")
    t = t[: m.end()] + " | 'cad_drwr'" + t[m.end():]
    # 3) cargador perezoso tras el último `const cargarX`
    cargas = list(re.finditer(r"^const cargar\w+ = \(\) => import\([^)]*\)\n", t, flags=re.M))
    if not cargas:
        raise AnclaFaltante("web/src/Shell.tsx: no se encontraron cargadores perezosos")
    t = t[: cargas[-1].end()] + "const cargarCadDrwr = () => import('./cad_drwr/CadDrwrPage')\n" + t[cargas[-1].end():]
    # 4) entrada de `routes` justo antes de la ruta `sap`
    short = siguiente_short(t)
    ancla = "  {\n    id: 'sap',\n"
    if t.count(ancla) != 1:
        raise AnclaFaltante("web/src/Shell.tsx: no se encontró la entrada `sap` de routes")
    entrada = (
        "  {\n    id: 'cad_drwr',\n    label: 'CAD-DRWR',\n"
        f"    short: '{short}',\n"
        "    description: 'Detalles estructurales 2D con exportación DXF y envío a ZWCAD/AutoCAD.',\n"
        "    icon: CadDrwrIcon,\n  },\n"
    )
    t = t.replace(ancla, entrada + ancla, 1)
    # 5) caso de la página justo antes de `case 'sap':`
    ancla = "      case 'sap':\n"
    if t.count(ancla) != 1:
        raise AnclaFaltante("web/src/Shell.tsx: no se encontró `case 'sap':`")
    caso = (
        "      case 'cad_drwr':\n        return (\n          <ModuloDiferido\n            cargar={cargarCadDrwr}\n"
        "            nombre=\"CAD-DRWR\"\n            state={props.state}\n            onState={props.onState}\n"
        "            onReport={props.onReport}\n            onReportBundle={props.onReportBundle}\n          />\n        )\n"
    )
    t = t.replace(ancla, caso + ancla, 1)
    p.write_text(t, encoding="utf-8")
    log.append(f"editado   web/src/Shell.tsx (short '{short}')")

def parchear_test_integrados(target, log):
    p = target / "tests/test_integrados.py"
    t = p.read_text(encoding="utf-8")
    if "'cad_drwr'" in t:
        log.append("sin cambio tests/test_integrados.py (ya aplicado)")
        return
    m = re.search(r"(        '[a-z_]+',\n)(    \]\n    assert all\(a\['status'\] == 'available' for a in body\[)", t)
    if not m:
        raise AnclaFaltante("tests/test_integrados.py: no se encontró la lista de módulos integrados")
    t = t[: m.end(1)] + "        'cad_drwr',\n" + t[m.end(1):]
    p.write_text(t, encoding="utf-8")
    log.append("editado   tests/test_integrados.py")

def contar_herramientas(target):
    """Módulos de la métrica «N módulos» del Resumen: rutas salvo `overview` y `sap`."""
    t = (target / "web/src/Shell.tsx").read_text(encoding="utf-8")
    bloque = t[t.index("const routes:"): t.index("]\n", t.index("const routes:"))]
    ids = re.findall(r"id: '(\w+)'", bloque)
    return len([i for i in ids if i not in ("overview", "sap")])


def parchear_shell_test(target, log, autorizado):
    """`Shell.test.tsx` fija «N módulos»: al sumar CAD-DRWR cambia. Es un test existente (check_protected
    prohíbe borrar sus líneas), así que SOLO se edita con autorización explícita del usuario.
    Idempotente y robusto: fija el número en el conteo REAL de rutas del Shell ya parcheado."""
    p = target / "web/src/Shell.test.tsx"
    t = p.read_text(encoding="utf-8")
    n = contar_herramientas(target)
    pat_a = re.compile(r"con (\d+) módulos', async")
    pat_b = re.compile(r"getByText\('(\d+) módulos'\)")
    ma, mb = pat_a.search(t), pat_b.search(t)
    if not ma or not mb:
        raise AnclaFaltante("web/src/Shell.test.tsx: no se encontró la métrica de módulos")
    if int(ma.group(1)) == n and int(mb.group(1)) == n:
        log.append(f"sin cambio web/src/Shell.test.tsx (ya dice {n} módulos)")
        return
    if not autorizado:
        log.append(f"PENDIENTE web/src/Shell.test.tsx: requiere autorización (cambia «{ma.group(1)} módulos» por "
                   f"«{n} módulos»; usa --autorizar-shell-test)")
        return
    t = pat_a.sub(f"con {n} módulos', async", t, count=1)
    t = pat_b.sub(f"getByText('{n} módulos')", t, count=1)
    p.write_text(t, encoding="utf-8")
    log.append(f"editado   web/src/Shell.test.tsx (AUTORIZADO: {ma.group(1)} -> {n} módulos)")


def parchear_browser_check(target, log):
    """Escenario de navegador de CAD-DRWR en scripts/browser_check_modulos.cjs (herramienta de verificación)."""
    p = target / "scripts/browser_check_modulos.cjs"
    t = p.read_text(encoding="utf-8")
    if "escenarioCadDrwr" in t:
        log.append("sin cambio scripts/browser_check_modulos.cjs (ya aplicado)")
        return
    n = contar_herramientas(target)
    # etiqueta (último elemento de ETIQUETAS)
    m = re.search(r"(const ETIQUETAS = \{\n(?:  \w+: '[^']*',\n)+)", t)
    if not m:
        raise AnclaFaltante("scripts/browser_check_modulos.cjs: no se encontró ETIQUETAS")
    t = t[: m.end(1)] + "  cad_drwr: 'CAD-DRWR',\n" + t[m.end(1):]
    # escenario antes de `const escenarios = {`
    ancla = "const escenarios = {\n"
    if t.count(ancla) != 1:
        raise AnclaFaltante("scripts/browser_check_modulos.cjs: no se encontró `const escenarios`")
    escenario = (ORIGEN / "scripts/escenario_cad_drwr.cjs.txt").read_text(encoding="utf-8")
    t = t.replace(ancla, escenario + ancla, 1)
    # entrada al final del objeto escenarios
    m = re.search(r"(const escenarios = \{\n(?:  \w+: \w+,\n)+)", t)
    t = t[: m.end(1)] + "  cad_drwr: escenarioCadDrwr,\n" + t[m.end(1):]
    # métrica esperada por defecto
    t, k = re.subn(r"(const EXPECTED_MODULES = process\.env\.EXPECTED_MODULES \|\| ')\d+(')", rf"\g<1>{n}\g<2>", t)
    p.write_text(t, encoding="utf-8")
    log.append(f"editado   scripts/browser_check_modulos.cjs (+escenario, EXPECTED_MODULES={n})")

def anexar_doc(target, rel, fuente, commit, log):
    p = target / rel
    t = p.read_text(encoding="utf-8")
    contenido = (ORIGEN / "docs" / fuente).read_text(encoding="utf-8").replace("{COMMIT}", commit)
    titulo = contenido.strip().splitlines()[0]
    if titulo in t:
        log.append(f"sin cambio {rel} (ya aplicado)")
        return
    p.write_text(t.rstrip("\n") + "\n" + contenido, encoding="utf-8")
    log.append(f"editado   {rel} (+{len(contenido.splitlines())} líneas)")


def parchear_ruff(target, log):
    p = target / "pyproject.toml"
    t = p.read_text(encoding="utf-8")
    if '"backend/motor_calculo/cad_drwr/**"' in t:
        log.append("sin cambio pyproject.toml (ya aplicado)")
        return
    ancla = "\n[tool.ruff.format]"
    if t.count(ancla) != 1:
        raise AnclaFaltante("pyproject.toml: no se encontró [tool.ruff.format]")
    comunes = ('"UP006", "UP007", "UP009", "UP015", "UP031", "UP032", "UP035", "UP037", "UP045", '
               '"F401", "F841", "I001", "E401", "E701", "E702", "E731", "B006", "B007", "B904", "E501"')
    reglas = (
        f'"backend/motor_calculo/cad_drwr/**" = [{comunes}]'
        "  # copia literal del motor del escritorio: se conserva el estilo original\n"
        f'"bridge/cad_com_live.py" = [{comunes}]  # copia casi literal de cad/com_live.py\n'
        f'"bridge/cad_sap_link.py" = [{comunes}]  # copia casi literal de cad/sap2000_link.py\n'
    )
    t = t.replace(ancla, reglas + ancla, 1)
    p.write_text(t, encoding="utf-8")
    log.append("editado   pyproject.toml (+ignores de copia literal)")

NUEVOS_RUFF = [
    "bridge/cad_drwr.py",
    "bridge/cad_drwr_sap.py",
    "backend/routers/cad_drwr.py",
    "backend/motor_calculo/cad_drwr/serializar.py",
    "backend/motor_calculo/cad_drwr/servicio.py",
    "backend/motor_calculo/cad_drwr/volcado.py",
    "backend/motor_calculo/cad_drwr/generators/__init__.py",
    "backend/motor_calculo/cad_drwr/generators/reglas_ui.py",
]


def formatear_json(target, log):
    """Prettier del workbench: deja bridge_contracts.json con su formato (si hay node_modules)."""
    web = target / "web"
    if not (web / "node_modules").exists():
        log.append("AVISO     sin web/node_modules: ejecuta «npx prettier --write src/bridge_contracts.json»")
        return
    r = subprocess.run(["npx", "prettier", "--write", "src/bridge_contracts.json", "src/cad_drwr"],
                       cwd=web, capture_output=True, text=True)
    log.append("formateado web/src/bridge_contracts.json y web/src/cad_drwr (prettier)"
               if r.returncode == 0 else f"AVISO prettier: {r.stderr.strip()[:200]}")


def ordenar_imports(target, log):
    """El orden de imports depende de qué paquetes son «propios» en cada raíz:
    se normaliza con la configuración del workbench (solo código nuevo, no las copias literales)."""
    archivos = NUEVOS_RUFF + sorted(f"tests/{t.name}" for t in (target / "tests").glob("test_cad_drwr_*.py"))
    for cmd in (["check", "--fix", "--select", "I", "--quiet"], ["format", "--quiet"]):
        r = subprocess.run(["ruff", *cmd, *archivos], cwd=target, capture_output=True, text=True)
        if r.returncode not in (0, 1):
            log.append(f"AVISO ruff {cmd[0]}: {r.stderr.strip()[:200]}")
    log.append("ordenado  imports/formato del código nuevo (ruff)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--commit", default=None)
    ap.add_argument("--autorizar-shell-test", action="store_true",
                    help="aplica el cambio de «10 módulos» a «11 módulos» en Shell.test.tsx (requiere OK del usuario)")
    a = ap.parse_args()
    target = pathlib.Path(a.target).resolve()
    if not (target / "backend/integrados.py").exists():
        sys.exit(f"{target} no parece un clon del workbench")
    commit = a.commit or subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                                        capture_output=True, text=True).stdout.strip() or "desconocido"
    log = []
    copiar(target, log)
    parchear_integrados(target, log)
    parchear_actions(target, log)
    parchear_contratos(target, log)
    parchear_iconos(target, log)
    parchear_shell(target, log)
    parchear_ruff(target, log)
    parchear_test_integrados(target, log)
    parchear_shell_test(target, log, a.autorizar_shell_test)
    parchear_browser_check(target, log)
    ordenar_imports(target, log)
    formatear_json(target, log)
    anexar_doc(target, "docs/MODULES_SOURCE.md", "MODULES_SOURCE_cad_drwr.md", commit, log)
    anexar_doc(target, "docs/SAP_ACTIONS.md", "SAP_ACTIONS_cad_drwr.md", commit, log)
    anexar_doc(target, "docs/SAP2000_ACCEPTANCE.md", "ACCEPTANCE_cad_drwr.md", commit, log)
    print("\n".join(log))


if __name__ == "__main__":
    main()
