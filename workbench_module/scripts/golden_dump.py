"""Volcado etiquetado de la IR a JSON puro (para golden y comparaciones).

Se usa tanto contra el repo ORIGINAL (escritorio) como contra el motor
copiado: ambos deben producir exactamente el mismo resultado.
"""
import dataclasses


def dump(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out = {"_t": type(obj).__name__}
        for f in dataclasses.fields(obj):
            out[f.name] = dump(getattr(obj, f.name))
        return out
    if isinstance(obj, dict):
        if any(isinstance(k, tuple) for k in obj):
            return {"_t": "pairs",
                    "items": [[list(k) if isinstance(k, tuple) else k, dump(v)]
                              for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))]}
        return {str(k): dump(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [dump(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 9)
    return obj
