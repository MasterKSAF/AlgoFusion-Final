from __future__ import annotations

import gzip
import json
from pathlib import Path

import cv2
import fitz
import numpy as np

def prepare_binary_mask(mask: np.ndarray) -> np.ndarray:
    """
    Приводит маску к бинарному виду и закрывает мелкие разрывы.
    """
    bin_img = (mask > 0).astype(np.uint8) * 255
    bin_img = cv2.morphologyEx(
        bin_img,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
    )
    return bin_img


def save_mask_json(line_mask: np.ndarray, out_json: Path, page_id: str, source: dict | None = None) -> None:
    """
    Сохраняет маску линий в json.gz
    """
    mask01 = (line_mask > 0).astype(np.uint8)

    data = {
        "page_id": page_id,
        "image_size_hw": [int(mask01.shape[0]), int(mask01.shape[1])],
        "mask": mask01.tolist(),
    }

    if source is not None:
        data["source"] = source

    out_json = out_json.with_suffix(".json.gz")

    with gzip.open(out_json, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def load_mask_from_json(mask_json_path: Path) -> np.ndarray | None:
    try:
        if str(mask_json_path).endswith(".gz"):
            with gzip.open(mask_json_path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(mask_json_path.read_text(encoding="utf-8"))
    except Exception as e:
        print("skip: bad json:", mask_json_path, e)
        return None

    if "mask" not in data:
        print("skip: key 'mask' not found:", mask_json_path)
        return None

    mask = np.array(data["mask"], dtype=np.uint8)

    if mask.ndim != 2:
        print("skip: mask is not 2D:", mask_json_path)
        return None

    if mask.max() <= 1:
        mask = mask * 255
    else:
        mask = (mask > 0).astype(np.uint8) * 255

    return mask

# =========================================================
# ЭТАП 1 — ПОИСК ЛИНИЙ
# =========================================================

def thin_lines_ximgproc(lines: np.ndarray) -> np.ndarray:
    """
    Утончение линий + утолщение обратно примерно до 2 px.
    """
    if lines.dtype != np.uint8:
        lines = lines.astype(np.uint8)

    lines_bin = (lines > 0).astype(np.uint8) * 255

    thin = cv2.ximgproc.thinning(
        lines_bin,
        thinningType=cv2.ximgproc.THINNING_ZHANGSUEN,
    )

    thin = cv2.dilate(
        thin,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
        1,
    )

    return thin


def render_pdf_to_images(pdf_path: Path, dpi: int = 200) -> list[tuple[int, np.ndarray]]:
    doc = fitz.open(str(pdf_path))
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    pages: list[tuple[int, np.ndarray]] = []

    for i in range(len(doc)):
        pix = doc.load_page(i).get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        pages.append((i + 1, img))

    return pages


def binarize_for_lines(bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        15,
    )


def detect_table_lines_mask(bgr: np.ndarray) -> np.ndarray:
    bw = binarize_for_lines(bgr)
    h, w = bw.shape[:2]

    k_h = max(20, w // 60)
    k_v = 31

    horiz = cv2.morphologyEx(
        bw,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (k_h, 1)),
    )

    vert = cv2.morphologyEx(
        bw,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_v)),
    )

    return cv2.bitwise_or(horiz, vert)


def draw_overlay_stage1(bgr: np.ndarray, line_mask: np.ndarray, out_png: Path) -> None:
    out = bgr.copy()

    mask2 = cv2.dilate(
        line_mask,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        1,
    )

    out[mask2 > 0] = (0, 255, 0)
    cv2.imwrite(str(out_png), out)


def save_cleaner_debug_png(clean_bgr: np.ndarray, page_stem: str, doc_out: Path) -> Path:
    out_path = doc_out / f"{page_stem}__cleaner.png"
    cv2.imwrite(str(out_path), clean_bgr)
    return out_path


def process_stage1_page(
    bgr: np.ndarray,
    page_stem: str,
    doc_out: Path,
    source: dict,
) -> None:
    lines = detect_table_lines_mask(bgr)
    lines_clean = thin_lines_ximgproc(lines)

    overlay_path = doc_out / f"{page_stem}__overlay.png"
    mask_json_path = doc_out / f"{page_stem}__mask.json"
    mask_png_path = doc_out / f"{page_stem}__mask.png"

    draw_overlay_stage1(bgr, lines_clean, overlay_path)

    # сохранить бинарную маску как PNG
    cv2.imwrite(str(mask_png_path), lines_clean)

    save_mask_json(lines_clean, mask_json_path, page_stem, source=source)

    print("OK:", page_stem)


__all__ = [
    "binarize_for_lines",
    "detect_table_lines_mask",
    "draw_overlay_stage1",
    "load_mask_from_json",
    "prepare_binary_mask",
    "process_stage1_page",
    "render_pdf_to_images",
    "save_cleaner_debug_png",
    "save_mask_json",
    "thin_lines_ximgproc",
]
