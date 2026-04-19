from __future__ import annotations

import copy
from typing import Any, Callable

from src.modules.runtime_text_quality import _clean_inline_text, _is_review_field_marker
from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_header_fallback import (
    build_waybill_raw_header_overlay as _build_waybill_raw_header_overlay,
    has_waybill_header_anchor_noise as _has_waybill_header_anchor_noise,
    load_waybill_header_number as _load_waybill_header_number,
    overlay_waybill_header_fallback as _overlay_waybill_header_fallback,
    waybill_party_payload_suspicious as _waybill_party_payload_suspicious,
)
from src.modules.runtime_waybill_raw import (
    build_waybill_raw_fallback as _build_waybill_raw_fallback,
    repair_waybill_review_item_names_from_raw as _repair_waybill_review_item_names_from_raw,
    repair_waybill_review_items_from_raw as _repair_waybill_review_items_from_raw,
)
from src.modules.runtime_waybill_text import finalize_waybill_payload_text as _finalize_waybill_payload_text


def _waybill_totals_payload_coherent(totals: dict[str, Any] | None, *, to_float_soft: Callable[[Any], float | None]) -> bool:
    if not isinstance(totals, dict):
        return False
    cost = to_float_soft(totals.get("cost_total"))
    vat = to_float_soft(totals.get("vat_total"))
    total = to_float_soft(totals.get("cost_with_vat_total"))
    if total is None:
        return False
    if cost is not None and total + 0.01 < cost:
        return False
    if vat is not None and total + 0.01 < vat:
        return False
    if cost is not None and vat is not None and abs((cost + vat) - total) > 0.2:
        return False
    return True


def _waybill_should_prefer_raw_totals(
    current_totals: dict[str, Any] | None,
    raw_totals: dict[str, Any] | None,
    *,
    is_missing: Callable[[Any], bool],
    to_float_soft: Callable[[Any], float | None],
) -> bool:
    if not _waybill_totals_payload_coherent(raw_totals, to_float_soft=to_float_soft):
        return False
    if not isinstance(current_totals, dict):
        return True
    if not _waybill_totals_payload_coherent(current_totals, to_float_soft=to_float_soft):
        return True
    for field in ("quantity_total", "cost_total", "vat_total", "cost_with_vat_total"):
        if is_missing(current_totals.get(field)) and not is_missing(raw_totals.get(field)):
            return True
    return False


def _waybill_totals_need_raw_fallback(
    payload: dict[str, Any] | None,
    *,
    is_missing: Callable[[Any], bool],
    to_float_soft: Callable[[Any], float | None],
) -> bool:
    if not isinstance(payload, dict):
        return True
    totals = payload.get("totals")
    if not isinstance(totals, dict):
        return True
    if is_missing(totals.get("cost_with_vat_total")):
        return True
    if is_missing(totals.get("cost_with_vat_total_words")):
        return True
    if not _waybill_totals_payload_coherent(totals, to_float_soft=to_float_soft):
        return True
    if is_missing(totals.get("vat_total")) and not is_missing(totals.get("cost_with_vat_total")):
        return True
    if is_missing(totals.get("vat_total_words")) and not is_missing(totals.get("vat_total")):
        return True
    return False


def _apply_waybill_raw_totals(
    out: dict[str, Any],
    raw_fallback: dict[str, Any],
    *,
    is_missing: Callable[[Any], bool],
    to_float_soft: Callable[[Any], float | None],
) -> dict[str, Any]:
    raw_totals = raw_fallback.get("totals")
    if not isinstance(raw_totals, dict):
        return out
    current_totals = out.get("totals")
    if not _waybill_should_prefer_raw_totals(current_totals, raw_totals, is_missing=is_missing, to_float_soft=to_float_soft):
        return out

    next_out = copy.deepcopy(out)
    next_out.setdefault("totals", {})
    next_out["totals"] = copy.deepcopy(next_out.get("totals") or {})
    for field in (
        "quantity_total",
        "cost_total",
        "vat_total",
        "cost_with_vat_total",
        "vat_total_words",
        "cost_with_vat_total_words",
    ):
        if not is_missing(raw_totals.get(field)):
            next_out["totals"][field] = copy.deepcopy(raw_totals.get(field))
    return next_out


def postprocess_waybill_prediction(
    item: PageWorkItem,
    payload: dict[str, Any],
    *,
    signals: dict[str, Any],
    is_missing: Callable[[Any], bool],
    deep_fill: Callable[[Any, Any], Any],
    blank_like: Callable[[Any], Any],
    to_float_soft: Callable[[Any], float | None],
) -> dict[str, Any]:
    out = copy.deepcopy(payload)

    current_sender_name = _clean_inline_text(((out.get("sender") or {}) if isinstance(out.get("sender"), dict) else {}).get("name"))
    current_receiver_name = _clean_inline_text(((out.get("receiver") or {}) if isinstance(out.get("receiver"), dict) else {}).get("name"))
    if item.page_role in {"first", "single"} and is_missing(out.get("document_number")):
        header_number = _load_waybill_header_number(item)
        if header_number:
            out["document_number"] = header_number
    if item.page_role in {"middle", "last"}:
        for key in ["document_type", "document_series", "document_number", "date", "sender", "receiver", "payer", "basis"]:
            if key in out:
                out[key] = blank_like(out[key])
    if item.page_role in {"first", "single"}:
        title_text = signals.get("page_document_type_text")
        if title_text and not out.get("document_type"):
            out["document_type"] = title_text
    out = _finalize_waybill_payload_text(out, item.page_role)
    sender_tax_id = ((out.get("sender") or {}) if isinstance(out.get("sender"), dict) else {}).get("tax_id")
    receiver_tax_id = ((out.get("receiver") or {}) if isinstance(out.get("receiver"), dict) else {}).get("tax_id")

    needs_raw_fallback = (
        (
            is_missing(out.get("basis"))
            and is_missing((out.get("sender") or {}).get("name"))
            and is_missing((out.get("receiver") or {}).get("name"))
            and not (out.get("items") or [])
        )
        or (
            item.page_role in {"first", "single"}
            and (
                is_missing((out.get("sender") or {}).get("name"))
                or is_missing((out.get("receiver") or {}).get("name"))
                or is_missing(out.get("basis"))
            )
        )
        or (
            item.page_role in {"first", "single"}
            and (
                is_missing(sender_tax_id)
                or is_missing(receiver_tax_id)
                or _is_review_field_marker(sender_tax_id)
                or _is_review_field_marker(receiver_tax_id)
            )
        )
        or (
            item.page_role in {"first", "single"}
            and current_sender_name
            and current_receiver_name
            and current_sender_name == current_receiver_name
        )
        or (
            item.page_role in {"first", "single"}
            and (
                _waybill_party_payload_suspicious(out.get("sender"))
                or _waybill_party_payload_suspicious(out.get("receiver"))
                or _has_waybill_header_anchor_noise(out.get("basis"))
            )
        )
        or (
            item.page_role in {"first", "single"}
            and _waybill_totals_need_raw_fallback(out, is_missing=is_missing, to_float_soft=to_float_soft)
        )
    )
    if needs_raw_fallback:
        raw_fallback = _build_waybill_raw_fallback(item)
        if raw_fallback:
            out = deep_fill(out, raw_fallback)
            out = _apply_waybill_raw_totals(out, raw_fallback, is_missing=is_missing, to_float_soft=to_float_soft)
            if item.page_role in {"first", "single"}:
                out = _overlay_waybill_header_fallback(out, raw_fallback)
    if item.page_role in {"first", "single"} and (
        is_missing((out.get("sender") or {}).get("name"))
        or is_missing((out.get("receiver") or {}).get("name"))
        or is_missing(out.get("basis"))
    ):
        raw_header_overlay = _build_waybill_raw_header_overlay(item)
        if raw_header_overlay:
            out = deep_fill(out, raw_header_overlay)
            out = _overlay_waybill_header_fallback(out, raw_header_overlay)
            cur_sender_name = _clean_inline_text(((out.get("sender") or {}) if isinstance(out.get("sender"), dict) else {}).get("name"))
            cur_receiver_name = _clean_inline_text(((out.get("receiver") or {}) if isinstance(out.get("receiver"), dict) else {}).get("name"))
            raw_sender_name = _clean_inline_text(((raw_header_overlay.get("sender") or {}) if isinstance(raw_header_overlay.get("sender"), dict) else {}).get("name"))
            raw_receiver_name = _clean_inline_text(((raw_header_overlay.get("receiver") or {}) if isinstance(raw_header_overlay.get("receiver"), dict) else {}).get("name"))
            if cur_sender_name and cur_receiver_name and cur_sender_name == cur_receiver_name and raw_receiver_name and not raw_sender_name:
                out["sender"] = blank_like(out.get("sender"))
    if isinstance(out.get("items"), list):
        out["items"] = _repair_waybill_review_items_from_raw(item, out["items"])
        out["items"] = _repair_waybill_review_item_names_from_raw(item, out["items"])
    out = _finalize_waybill_payload_text(out, item.page_role)
    if isinstance(out.get("items"), list):
        out["items"] = _repair_waybill_review_items_from_raw(item, out["items"])
        out["items"] = _repair_waybill_review_item_names_from_raw(item, out["items"])
    return out
