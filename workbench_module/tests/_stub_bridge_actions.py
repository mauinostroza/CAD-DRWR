"""Sustituto de `bridge.actions` para el arnés (fuera del workbench).

`split_return` es copia literal de `bridge/actions.py` del workbench; en el workbench real se usa
el módulo verdadero (este archivo NO se copia al workbench).
"""

from typing import Any


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def split_return(raw: Any, ret_first: bool | None = None) -> tuple[int, list[Any]]:
    """Separate a COM call result into ``(return_code, outputs)``.

    SAP2000's OAPI puts the return code last with comtypes/typed wrappers
    (``(out1, ..., ret)``) and first with pywin32 late binding (``(ret, out1, ...)``).
    The side is inferred from the types: the code is the only ``int`` at an end when
    the other end is not an ``int``. When both ends are ints (e.g. ``GetTypeOAPI``)
    the end holding ``0`` wins, ret-last by default; callers that already know the
    side from an unambiguous call in the same session pass ``ret_first``.
    """
    if not isinstance(raw, (tuple, list)):
        try:
            return int(raw), []
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Unexpected SAP2000 response (no return code)") from exc
    items = list(raw)
    if not items:
        raise RuntimeError("Unexpected SAP2000 response (empty)")
    if ret_first is None:
        first, last = _is_int(items[0]), _is_int(items[-1])
        if first and not last:
            ret_first = True
        elif last and not first:
            ret_first = False
        elif first and last:
            ret_first = items[0] == 0 and items[-1] != 0
        else:
            raise RuntimeError("Unexpected SAP2000 response (no return code)")
    if ret_first:
        return int(items[0]), items[1:]
    return int(items[-1]), items[:-1]
