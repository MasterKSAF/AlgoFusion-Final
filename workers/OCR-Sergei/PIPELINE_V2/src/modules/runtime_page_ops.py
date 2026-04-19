from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.modules.runtime_io import save_png, write_json, write_text
from src.modules.runtime_render import bgr_from_pil, pil_from_bgr, thin_lines_safe
from src.modules.runtime_services import CleanerLayoutService, RawOcrService


def run_cleaner_debug(cleaner: CleanerLayoutService, src_bgr: np.ndarray, input_dpi: int, page_dir: Path) -> dict[str, Any]:
    save_png(page_dir / "01_src.png", src_bgr)

    img = pil_from_bgr(src_bgr)
    img_norm = cleaner.normalize_to_working_dpi(img, input_dpi=input_dpi)
    save_png(page_dir / "02_norm.png", bgr_from_pil(img_norm))

    img_s41 = cleaner.preprocess_stage_4_1(img_norm)
    save_png(page_dir / "03_s41.png", bgr_from_pil(img_s41))

    img_s42 = cleaner.preprocess_stage_4_2(img_s41)
    save_png(page_dir / "04_s42.png", bgr_from_pil(img_s42))

    img_s43 = cleaner.preprocess_stage_4_3(img_s42)
    save_png(page_dir / "05_s43.png", bgr_from_pil(img_s43))

    img_bg = cleaner.build_background(img_s43.convert("L"))
    save_png(page_dir / "06_bg.png", bgr_from_pil(img_bg.convert("RGB")))

    img_bin = cleaner.build_binary(img_bg)
    bin_bgr = bgr_from_pil(img_bin.convert("RGB"))
    save_png(page_dir / "07_bin.png", bin_bgr)

    angle, found = cleaner.detect_rotation_angle(bin_bgr)
    if found and cleaner.rotate_min_abs_angle <= abs(angle) <= cleaner.rotate_max_abs_angle:
        rot_bgr = cleaner.rotate_image_by_angle(bin_bgr, angle)
    else:
        rot_bgr = bin_bgr
        angle = 0.0
    save_png(page_dir / "08_rot.png", rot_bgr)

    img_a4 = pil_from_bgr(rot_bgr)
    if cleaner.a4_canvas_enabled:
        img_a4 = cleaner.fit_to_a4_canvas(img_a4)
    clean_bgr = bgr_from_pil(img_a4)
    save_png(page_dir / "09_a4.png", clean_bgr)

    return {
        "clean_bgr": clean_bgr,
        "rotation_angle": angle,
        "rotation_found": found,
    }


def build_stage1_artifacts(
    cleaner: CleanerLayoutService,
    page_id: str,
    clean_bgr: np.ndarray,
    source_meta: dict[str, Any],
    page_dir: Path,
    stage1_dir: Path,
) -> tuple[np.ndarray, Path]:
    line_mask = cleaner.detect_table_lines_mask(clean_bgr)
    line_mask = thin_lines_safe(cleaner.thin_lines_ximgproc, line_mask)
    save_png(page_dir / "10_mask.png", line_mask)
    cleaner.draw_overlay_stage1(clean_bgr, line_mask, page_dir / "10_ov1.png")

    mask_json_path = stage1_dir / f"{page_id}__mask.json"
    cleaner.save_mask_json(line_mask, mask_json_path, page_id, source=source_meta)
    return line_mask, mask_json_path.with_suffix(".json.gz")


def run_raw_ocr_page(raw_ocr: RawOcrService, page_id: str, no_lines_bgr: np.ndarray, page_dir: Path) -> tuple[dict[str, Any], Path]:
    image = pil_from_bgr(no_lines_bgr)
    ocr_items = raw_ocr.run_image(image)
    full_text = "\n".join(item.get("text", "").strip() for item in ocr_items if item.get("text")).strip()
    payload = {
        "page_id": page_id,
        "text": full_text,
        "ocr_items": ocr_items,
    }
    raw_json = write_json(page_dir / f"{page_id}__ocr_raw.json", payload)
    write_text(page_dir / "12_raw.txt", full_text)
    return payload, raw_json
