"""Revisión conservadora de solapes de texto; no sustituye el ploteo CAD."""

from . import ir
from .annotations import expand_annotations
from .bounds import entity_bounds
from .dims import dim_parts


def annotation_overlaps(drawing):
    texts = []
    for entity in expand_annotations(drawing.ents):
        parts = dim_parts(entity, entity.text_height or 3) if isinstance(entity, ir.Dim) else [entity]
        texts.extend(part for part in parts if isinstance(part, ir.Text) and part.s)
    boxes = [entity_bounds(text) for text in texts]
    result = []
    for i, a in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            b = boxes[j]
            if min(a[2], b[2]) - max(a[0], b[0]) > 0.1 and min(a[3], b[3]) - max(a[1], b[1]) > 0.1:
                result.append((texts[i].s, texts[j].s))
    return result
