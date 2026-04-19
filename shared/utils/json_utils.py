"""Fast JSON helpers with an orjson-first strategy."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import orjson
except ImportError:  # pragma: no cover
    orjson = None


def _default(value: Any) -> Any:
    if isinstance(value, (datetime, Path)):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def json_dumps(value: Any, *, indent: int | None = None) -> str:
    if orjson is not None:
        option = 0
        if indent:
            option |= orjson.OPT_INDENT_2
        return orjson.dumps(value, default=_default, option=option).decode("utf-8")
    return json.dumps(value, ensure_ascii=False, default=_default, indent=indent)


def json_dumpb(value: Any, *, indent: int | None = None) -> bytes:
    if orjson is not None:
        option = 0
        if indent:
            option |= orjson.OPT_INDENT_2
        return orjson.dumps(value, default=_default, option=option)
    return json_dumps(value, indent=indent).encode("utf-8")


def json_loads(value: str | bytes | bytearray) -> Any:
    if isinstance(value, str):
        if orjson is not None:
            return orjson.loads(value)
        return json.loads(value)
    payload = bytes(value)
    if orjson is not None:
        return orjson.loads(payload)
    return json.loads(payload.decode("utf-8"))
