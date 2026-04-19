from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import fitz
import numpy as np
from PIL import Image

try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None


def bgr_from_pil(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def pil_from_bgr(image: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


def render_pdf_pages(input_path: Path, dpi: int) -> list[tuple[int, np.ndarray]]:
    if convert_from_path is not None:
        pages = convert_from_path(str(input_path), dpi=dpi)
        out = []
        for idx, page in enumerate(pages, 1):
            out.append((idx, cv2.cvtColor(np.array(page.convert("RGB")), cv2.COLOR_RGB2BGR)))
        return out

    doc = fitz.open(str(input_path))
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    out: list[tuple[int, np.ndarray]] = []
    for idx in range(len(doc)):
        pix = doc.load_page(idx).get_pixmap(matrix=matrix, alpha=False)
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            rgb = cv2.cvtColor(rgb, cv2.COLOR_BGRA2BGR)
        out.append((idx + 1, rgb))
    return out


def render_input_pages(input_path: Path, dpi: int = 600, max_pages: int | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    stem = input_path.stem

    if input_path.suffix.lower() == ".pdf":
        for page_no, bgr in render_pdf_pages(input_path, dpi=dpi):
            if max_pages is not None and page_no > max_pages:
                break
            items.append(
                {
                    "page_id": f"{stem}__p{page_no:04d}",
                    "page_no": page_no,
                    "input_dpi": dpi,
                    "source": {
                        "kind": "pdf",
                        "pdf_name": input_path.name,
                        "page_num_1based": page_no,
                        "dpi": dpi,
                    },
                    "bgr": bgr,
                }
            )
        return items

    raw_bgr = cv2.imread(str(input_path))
    if raw_bgr is None:
        raise FileNotFoundError(f"Cannot open image: {input_path}")
    items.append(
        {
            "page_id": f"{stem}__p0001",
            "page_no": 1,
            "input_dpi": dpi,
            "source": {
                "kind": "image",
                "file_name": input_path.name,
            },
            "bgr": raw_bgr,
        }
    )
    return items


def thin_lines_safe(thinning_fn, lines: np.ndarray) -> np.ndarray:
    if hasattr(cv2, "ximgproc") and hasattr(cv2.ximgproc, "thinning"):
        return thinning_fn(lines)
    return cv2.dilate((lines > 0).astype(np.uint8) * 255, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)), 1)
