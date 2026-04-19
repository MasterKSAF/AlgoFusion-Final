from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from shared.utils.json_utils import json_dumpb, json_loads


def mkdir_clean(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_png(path: Path, image: np.ndarray) -> Path:
    ensure_dir(path.parent)
    cv2.imwrite(str(path), image)
    return path


def read_json(path: Path) -> Any:
    return json_loads(path.read_bytes())


def write_json(path: Path, payload: Any) -> Path:
    ensure_dir(path.parent)
    path.write_bytes(json_dumpb(payload, indent=2))
    return path


def write_text(path: Path, text: str) -> Path:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")
    return path


def copy_file(src: Path, dst: Path) -> Path:
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)
    return dst
