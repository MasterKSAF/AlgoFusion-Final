from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_roi_by_doc_type(document_parser: Any, roi_path: Path, doc_type: str, *, page_id: str) -> dict[str, Any]:
    if doc_type == "payment_order":
        return document_parser.parse_payment_order(roi_path)
    if doc_type == "invoice":
        return document_parser.parse_invoice(roi_path)
    if doc_type == "waybill":
        return document_parser.parse_waybill(roi_path)
    if doc_type == "account_prot":
        return document_parser.parse_account_protocol(roi_path)

    fallback_type = document_parser.detect_doc_type(roi_path)
    if fallback_type == "payment_order":
        return document_parser.parse_payment_order(roi_path)
    if fallback_type == "invoice":
        return document_parser.parse_invoice(roi_path)
    if fallback_type == "waybill":
        return document_parser.parse_waybill(roi_path)
    if fallback_type == "account_prot":
        return document_parser.parse_account_protocol(roi_path)
    raise ValueError(f"Unsupported doc type for page {page_id}: {doc_type}")
