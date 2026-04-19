from __future__ import annotations

import numpy as np

from src.modules.runtime_cleaner_unp_image import _detect_unp_cells_from_clean_image
from src.modules.runtime_cleaner_unp_mask import _detect_unp_cells_from_mask
from src.modules.runtime_cleaner_unp_segments import _cm_to_px


def detect_unp_cells(
    mask: np.ndarray,
    table_top_y: int,
    dpi: int = 200,
    clean_bgr: np.ndarray | None = None,
):
    result = _detect_unp_cells_from_mask(mask, table_top_y, dpi=dpi)
    if result:
        return result
    return _detect_unp_cells_from_clean_image(clean_bgr, table_top_y, dpi=dpi)

__all__ = [
    "_cm_to_px",
    "detect_unp_cells",
]
