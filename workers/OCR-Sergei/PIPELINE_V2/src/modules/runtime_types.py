from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class PageWorkItem:
    page_id: str
    page_no: int
    source_bgr: np.ndarray
    clean_bgr: np.ndarray
    no_lines_bgr: np.ndarray
    mask: np.ndarray
    mask_json_path: Path
    raw_ocr_json_path: Path
    header_ocr_json_path: Path | None = None
    roi_coords_path: Path | None = None
    roi_text_path: Path | None = None
    full_text: str = ""
    ocr_items: list[dict[str, Any]] | None = None
    signals: dict[str, Any] | None = None
    segment_id: str | None = None
    segment_doc_type: str | None = None
    page_role: str | None = None
