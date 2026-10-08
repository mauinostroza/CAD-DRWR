"""Compara por AST la lógica de los archivos copiados contra el escritorio.

Uso: python workbench_module/scripts/check_engine_parity.py
Normaliza imports (absolutos -> relativos) y descarta docstrings; el resto del
AST debe coincidir. Sale con código 1 si hay diferencias.
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEST = ROOT / "workbench_module/backend/motor_calculo/cad_drwr"
PAIRS = [(p, DEST / "core" / p.name) for p in sorted((ROOT / "core").glob("*.py"))
         if p.name != "__init__.py"]
PAIRS.append((ROOT / "cad/dxf_out.py", DEST / "dxf_out.py"))
PAIRS.append((ROOT / "generators/data.py", DEST / "generators/data.py"))


class Norm(ast.NodeTransformer):
    """Todo import interno (absoluto 'core.x' o relativo '.core.x'/'.x') se
    reduce a 'from .x import ...'; los externos se dejan intactos."""

    def visit_ImportFrom(self, node):
        mod = node.module or ""
        if node.level == 0 and mod.split(".")[0] != "core":
            return node
        if mod == "core" or mod.startswith("core."):
            mod = mod[len("core"):].lstrip(".")
        return ast.ImportFrom(module=mod or None, names=node.names, level=1)


def strip_doc(tree):
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            b = n.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) \
                    and isinstance(b[0].value.value, str):
                n.body = b[1:] or [ast.Pass()]
    return tree


def dump(path):
    tree = strip_doc(ast.parse(path.read_text(encoding="utf-8")))
    return ast.dump(Norm().visit(tree), include_attributes=False)


bad = 0
for src, dst in PAIRS:
    if not dst.exists():
        print(f"FALTA   {dst.relative_to(ROOT)}")
        bad += 1
    elif dump(src) != dump(dst):
        print(f"DIFIERE {dst.relative_to(ROOT)}")
        bad += 1
    else:
        print(f"OK      {dst.relative_to(ROOT)}")
sys.exit(1 if bad else 0)
