from __future__ import annotations

from typing import Any

import numpy as np

from src.modules.runtime_page_signal_precomputed import analyze_page_signals_from_precomputed as _analyze_page_signals_from_precomputed_impl
from src.modules.runtime_page_signal_titles import (
    detect_waybill_document_type_text as _detect_waybill_document_type_text_impl,
    has_invoice_header_like as _has_invoice_header_like_impl,
)
from src.modules.runtime_page_signal_v3 import analyze_page_signals_v3 as _analyze_page_signals_v3_impl
from src.modules.runtime_services import CleanerLayoutService


def _has_invoice_header_like(top_text: str) -> bool:
    return _has_invoice_header_like_impl(top_text)


def _detect_waybill_document_type_text(top_text: str) -> str | None:
    return _detect_waybill_document_type_text_impl(top_text)


def analyze_page_signals_from_precomputed(
    page_id: str,
    page_no: int,
    clean_bgr: np.ndarray,
    roi_payload: dict[str, Any],
    ocr_payload: dict[str, Any],
    page_dir,
    force_doc_type: str | None = None,
) -> dict[str, Any]:
    return _analyze_page_signals_from_precomputed_impl(
        page_id=page_id,
        page_no=page_no,
        clean_bgr=clean_bgr,
        roi_payload=roi_payload,
        ocr_payload=ocr_payload,
        page_dir=page_dir,
        force_doc_type=force_doc_type,
    )


def analyze_page_signals_v3(
    cleaner: CleanerLayoutService,
    page_id: str,
    page_no: int,
    clean_bgr: np.ndarray,
    mask: np.ndarray,
    ocr_payload: dict[str, Any],
    page_dir,
    force_doc_type: str | None = None,
) -> dict[str, Any]:
    return _analyze_page_signals_v3_impl(
        cleaner=cleaner,
        page_id=page_id,
        page_no=page_no,
        clean_bgr=clean_bgr,
        mask=mask,
        ocr_payload=ocr_payload,
        page_dir=page_dir,
        force_doc_type=force_doc_type,
    )


analyze_page_signals = analyze_page_signals_v3
