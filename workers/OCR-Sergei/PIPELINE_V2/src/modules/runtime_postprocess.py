from __future__ import annotations

import copy
import re
from typing import Any

from src.modules.runtime_account_prot import repair_shifted_account_prot_item as _repair_shifted_account_prot_item
from src.modules.runtime_invoice_page_postprocess import postprocess_invoice_prediction as _postprocess_invoice_prediction
from src.modules.runtime_numbers import to_float_soft as _to_float_soft
from src.modules.runtime_payment_order import build_payment_order_raw_fallback_from_lines as _build_payment_order_raw_fallback_from_lines
from src.modules.runtime_regions import group_ocr_lines as _group_ocr_lines
from src.modules.runtime_text_quality import _clean_inline_text, _review_marker_or_none
from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_postprocess import postprocess_waybill_prediction as _postprocess_waybill_prediction


def _clean_company_like_noise(text: str | None) -> str | None:
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r"\s*:\s*", " ", cleaned)
    cleaned = re.sub(r"\b\u0442\u043e\u0432\u0430\u0440\u044b\s*\([^)]*\)\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _build_payment_order_raw_fallback(
    item: PageWorkItem,
    current_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not item.ocr_items:
        return None

    rows = _group_ocr_lines(item.ocr_items, y_tol=10)
    lines = [_clean_inline_text(row.get("text")) or "" for row in rows if _clean_inline_text(row.get("text"))]
    return _build_payment_order_raw_fallback_from_lines(lines, current_payload)


def _unwrap_page_prediction(pred: dict[str, Any], doc_type_hint: str) -> tuple[str, str | None, dict[str, Any]]:
    if doc_type_hint == "waybill":
        return "waybill", None, pred
    if not isinstance(pred, dict) or len(pred) != 1:
        raise ValueError(f"Unexpected prediction shape for {doc_type_hint}")
    outer_type, docs = next(iter(pred.items()))
    if not isinstance(docs, dict) or len(docs) != 1:
        raise ValueError(f"Unexpected wrapped payload for {outer_type}")
    file_key, payload = next(iter(docs.items()))
    return outer_type, str(file_key), payload


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0 or all(_is_missing(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0 or all(_is_missing(item) for item in value.values())
    return False


def _deep_fill(base: Any, other: Any) -> Any:
    if _is_missing(base):
        return copy.deepcopy(other)
    if isinstance(base, dict) and isinstance(other, dict):
        out = copy.deepcopy(base)
        for key, value in other.items():
            if key not in out:
                out[key] = copy.deepcopy(value)
            else:
                out[key] = _deep_fill(out[key], value)
        return out
    return base


def _blank_like(value: Any) -> Any:
    if isinstance(value, dict):
        return {}
    if isinstance(value, list):
        return []
    return None


def _postprocess_page_prediction(item: PageWorkItem, outer_type: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    doc_type = item.segment_doc_type or outer_type or "unknown"
    signals = item.signals or {}
    out = copy.deepcopy(payload)

    if doc_type == "waybill":
        out = _postprocess_waybill_prediction(
            item,
            out,
            signals=signals,
            is_missing=_is_missing,
            deep_fill=_deep_fill,
            blank_like=_blank_like,
            to_float_soft=_to_float_soft,
        )
    elif doc_type == "invoice":
        out = _postprocess_invoice_prediction(
            item,
            out,
            is_missing=_is_missing,
            deep_fill=_deep_fill,
            review_marker_or_none=_review_marker_or_none,
        )
    elif doc_type == "account_prot":
        supplier = out.get("supplier")
        if isinstance(supplier, dict):
            supplier["name"] = _clean_company_like_noise(supplier.get("name"))
            supplier["bank_name"] = _clean_company_like_noise(supplier.get("bank_name"))
        customer = out.get("customer")
        if isinstance(customer, dict):
            customer["name"] = _clean_company_like_noise(customer.get("name"))
            customer["bank_name"] = _clean_company_like_noise(customer.get("bank_name"))
        repaired_items = []
        for row in out.get("items") or []:
            if isinstance(row, dict):
                repaired_items.append(_repair_shifted_account_prot_item(row))
            else:
                repaired_items.append(row)
        out["items"] = repaired_items
    elif doc_type == "payment_order":
        if item.page_role in {"first", "single"}:
            raw_fallback = _build_payment_order_raw_fallback(item, out)
            if raw_fallback:
                out = _deep_fill(out, raw_fallback)
        if item.page_role != "single":
            for key in ["document_type", "number", "date", "payer", "payee", "amount", "purpose"]:
                if key in out and item.page_role != "first":
                    out[key] = _blank_like(out[key])

    out["_page_role"] = item.page_role
    out["_page_id"] = item.page_id
    return outer_type, out


blank_like = _blank_like
build_payment_order_raw_fallback = _build_payment_order_raw_fallback
clean_company_like_noise = _clean_company_like_noise
deep_fill = _deep_fill
is_missing = _is_missing
postprocess_page_prediction = _postprocess_page_prediction
unwrap_page_prediction = _unwrap_page_prediction
