# -*- coding: utf-8 -*-
"""轻量 JSON Schema 校验器（只实现抽取值需要的那部分关键字）。

不依赖 jsonschema 库，保证在只有标准库的环境里也能跑。
支持：type / required / properties / additionalProperties / enum /
      items / minLength / minimum / maximum
"""
from __future__ import annotations

import json
from pathlib import Path

TYPES = {
    "object": dict, "array": list, "string": str, "number": (int, float),
    "integer": int, "boolean": bool, "null": type(None),
}


def _type_ok(value, t) -> bool:
    if isinstance(t, list):
        return any(_type_ok(value, x) for x in t)
    py = TYPES.get(t)
    if py is None:
        return True
    if t in ("number", "integer") and isinstance(value, bool):
        return False
    return isinstance(value, py)


def validate(value, schema, path="$") -> list[str]:
    errors = []
    if not isinstance(schema, dict):
        return errors

    if "type" in schema and not _type_ok(value, schema["type"]):
        errors.append(f"{path}: expected {schema['type']}, got {type(value).__name__}")
        return errors

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum")

    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        errors.append(f"{path}: shorter than minLength {schema['minLength']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required '{key}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}: unexpected key '{key}'")
        for key, sub in props.items():
            if key in value:
                errors.extend(validate(value[key], sub, f"{path}.{key}"))

    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errors.extend(validate(item, schema["items"], f"{path}[{i}]"))

    return errors


def load_schema(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    import sys
    schema = load_schema(sys.argv[1] if len(sys.argv) > 1 else "schemas/extraction.schema.json")
    sample = {"accident": {"type": "collision"},
              "entities": [{"id": "e1", "type": "Ship", "text": "M/V X"}],
              "relations": []}
    print("errors:", validate(sample, schema) or "none")
