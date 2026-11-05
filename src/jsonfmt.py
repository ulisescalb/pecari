"""Escritura de JSON legible: listas de escalares en una linea, dicts indentados."""
import json


def _leaf(v):
    return isinstance(v, (int, float, str, bool)) or v is None


def dumps(o, ind=0, step=2):
    sp = " " * ind
    if isinstance(o, dict):
        if not o:
            return "{}"
        items = []
        for k, v in o.items():
            items.append(" " * (ind + step) + json.dumps(k, ensure_ascii=False) + ": " + dumps(v, ind + step, step))
        return "{\n" + ",\n".join(items) + "\n" + sp + "}"
    if isinstance(o, list):
        if all(_leaf(v) for v in o):
            return "[" + ", ".join(_num(v) for v in o) + "]"
        if all(isinstance(v, list) and all(_leaf(x) for x in v) for v in o):
            return "[\n" + ",\n".join(" " * (ind + step) + dumps(v) for v in o) + "\n" + sp + "]"
        return "[\n" + ",\n".join(" " * (ind + step) + dumps(v, ind + step, step) for v in o) + "\n" + sp + "]"
    return _num(o)


def _num(v):
    if isinstance(v, float):
        r = round(v, 5)
        return json.dumps(r)
    return json.dumps(v, ensure_ascii=False)


def dump(o, path):
    with open(path, "w") as fh:
        fh.write(dumps(o) + "\n")
