from __future__ import annotations

from pathlib import Path

import numpy as np

from src.modules.runtime_io import copy_file, save_png


def save_standard_cleaner_output(clean_bgr: np.ndarray, cleaner_dir: Path, source_stem: str, page_no: int) -> Path:
    return save_png(cleaner_dir / f"{source_stem}_p{page_no:02d}_clean.png", clean_bgr)


def copy_standard_stage1_outputs(page_id: str, debug_page_dir: Path, stage1_doc_dir: Path) -> None:
    copy_file(debug_page_dir / "10_mask.png", stage1_doc_dir / f"{page_id}__mask.png")
    copy_file(debug_page_dir / "10_ov1.png", stage1_doc_dir / f"{page_id}__overlay.png")
