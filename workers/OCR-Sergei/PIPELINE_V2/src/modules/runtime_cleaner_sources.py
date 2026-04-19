from __future__ import annotations

import gzip
import json
from pathlib import Path

import cv2
import fitz
import numpy as np

from src.modules.runtime_cleaner_preprocess import (
    NB_CLEANER,
    convert_from_path,
    nb_clean_page_bgr_exact,
    nb_load_input_image_with_dpi,
    nb_read_json_maybe_gz,
)

def nb_load_worker_clean_page(page_id: str, input_dir: Path, mask_json_path: Path):
    meta = nb_read_json_maybe_gz(mask_json_path)
    source = meta.get('source') or {}
    kind = source.get('kind')

    if kind == 'pdf':
        pdf_name = source.get('pdf_name')
        page_num_1based = source.get('page_num_1based')
        if pdf_name and page_num_1based is not None:
            pdf_path = _resolve_image_path_by_name(pdf_name, input_dir)
            if pdf_path is not None:
                orig_bgr = None
                if convert_from_path is not None:
                    try:
                        pages = convert_from_path(
                            str(pdf_path),
                            dpi=int(NB_CLEANER.default_dpi),
                            first_page=int(page_num_1based),
                            last_page=int(page_num_1based),
                        )
                        if pages:
                            rgb = np.array(pages[0].convert('RGB'))
                            orig_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                    except Exception:
                        orig_bgr = None
                if orig_bgr is None:
                    orig_bgr = _render_original_from_pdf(pdf_path, int(page_num_1based), int(NB_CLEANER.default_dpi))
                if orig_bgr is not None:
                    clean_bgr = nb_clean_page_bgr_exact(
                        orig_bgr,
                        input_dpi=NB_CLEANER.default_dpi,
                        working_dpi=NB_CLEANER.default_dpi,
                        target_dpi=NB_CLEANER.output_dpi,
                    )
                    return clean_bgr, pdf_path, NB_CLEANER.default_dpi

    if kind == 'image':
        file_name = source.get('file_name')
        if file_name:
            path = _resolve_image_path_by_name(file_name, input_dir)
            if path is not None:
                orig_bgr, input_dpi = nb_load_input_image_with_dpi(path)
                clean_bgr = nb_clean_page_bgr_exact(
                    orig_bgr,
                    input_dpi=input_dpi,
                    working_dpi=NB_CLEANER.default_dpi,
                    target_dpi=NB_CLEANER.output_dpi,
                )
                return clean_bgr, path, input_dpi

    orig_bgr, orig_path = resolve_original_image(page_id, input_dir, mask_json_path)
    if orig_bgr is None:
        return None, None, None

    clean_bgr = nb_clean_page_bgr_exact(
        orig_bgr,
        input_dpi=NB_CLEANER.assumed_input_dpi,
        working_dpi=NB_CLEANER.default_dpi,
        target_dpi=NB_CLEANER.output_dpi,
    )
    return clean_bgr, orig_path, NB_CLEANER.assumed_input_dpi


# =========================================================
# ОБЩИЕ УТИЛИТЫ
# =========================================================

def _resolve_image_path_by_name(file_name: str, input_dir: Path) -> Path | None:
    p = input_dir / file_name
    if p.exists():
        return p

    matches = sorted(
        p for p in input_dir.rglob("*")
        if p.is_file() and p.name == file_name
    )
    return matches[0] if matches else None


def _render_original_from_pdf(pdf_path: Path, page_num_1based: int, dpi: int) -> np.ndarray | None:
    try:
        doc = fitz.open(str(pdf_path))
        page_index = int(page_num_1based) - 1
        if page_index < 0 or page_index >= len(doc):
            return None

        zoom = float(dpi) / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = doc.load_page(page_index).get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        return img
    except Exception:
        return None


def resolve_original_image(page_id: str, input_dir: Path, mask_json_path: Path) -> tuple[np.ndarray | None, Path | None]:
    exts = [".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"]

    try:
        if str(mask_json_path).endswith(".gz"):
            with gzip.open(mask_json_path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(mask_json_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    source = data.get("source") or {}
    kind = source.get("kind")

    if kind == "image":
        file_name = source.get("file_name")
        if file_name:
            p = _resolve_image_path_by_name(file_name, input_dir)
            if p is not None:
                img = cv2.imread(str(p))
                if img is not None:
                    return img, p

    if kind == "pdf":
        pdf_name = source.get("pdf_name")
        page_num_1based = source.get("page_num_1based")
        dpi = int(source.get("dpi", 200))

        if pdf_name and page_num_1based is not None:
            pdf_path = _resolve_image_path_by_name(pdf_name, input_dir)
            if pdf_path is not None:
                img = _render_original_from_pdf(pdf_path, int(page_num_1based), dpi)
                if img is not None:
                    return img, pdf_path

    for ext in exts:
        p = input_dir / f"{page_id}{ext}"
        if p.exists():
            img = cv2.imread(str(p))
            if img is not None:
                return img, p

    matches = sorted(
        p for p in input_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in exts and p.stem == page_id
    )
    for p in matches:
        img = cv2.imread(str(p))
        if img is not None:
            return img, p

    return None, None


# =========================================================
# ЭТАП 2 — ОСИ, СЕГМЕНТЫ, ПОДДЕРЖКА
# =========================================================


__all__ = [
    "_render_original_from_pdf",
    "_resolve_image_path_by_name",
    "nb_load_worker_clean_page",
    "resolve_original_image",
]
