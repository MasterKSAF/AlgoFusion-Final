from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_numbers import to_float_soft
from src.modules.runtime_text_quality import (
    REVIEW_FIELD_MARKER,
    _clean_inline_text,
    _review_marker_or_none,
    _sanitize_final_text_or_review,
)
from src.modules.runtime_waybill_approvals import (
    normalize_waybill_document_number as _normalize_waybill_document_number_impl,
    normalize_waybill_document_number_or_review as _normalize_waybill_document_number_or_review_impl,
    sanitize_money_words_or_review as _sanitize_money_words_or_review_impl,
    sanitize_waybill_approval_or_review as _sanitize_waybill_approval_or_review_impl,
    sanitize_waybill_approval_text as _sanitize_waybill_approval_text_impl,
)
from src.modules.runtime_waybill_items import (
    extract_waybill_unit_token as _extract_waybill_unit_token_impl,
    sanitize_waybill_page_items as _sanitize_waybill_page_items_impl,
    waybill_unit_suspicious as _waybill_unit_suspicious_impl,
)
from src.modules.runtime_waybill_parties import (
    mark_waybill_required_header_fields as _mark_waybill_required_header_fields_impl,
    split_waybill_address_and_basis as _split_waybill_address_and_basis_impl,
)
from src.modules.runtime_waybill_totals import (
    coerce_waybill_total as _coerce_waybill_total_impl,
    compute_waybill_totals_from_items as _compute_waybill_totals_from_items_impl,
    fill_waybill_totals_from_safe_sources as _fill_waybill_totals_from_safe_sources_impl,
)


def normalize_waybill_document_number(value: Any) -> str | None:
    return _normalize_waybill_document_number_impl(value)


def normalize_waybill_document_number_or_review(value: Any) -> str | None:
    return _normalize_waybill_document_number_or_review_impl(value)


def sanitize_money_words_or_review(raw_value: Any, amount: Any) -> str | None:
    return _sanitize_money_words_or_review_impl(raw_value, amount)


def sanitize_waybill_approval_text(text: str | None, *, field_name: str) -> str | None:
    return _sanitize_waybill_approval_text_impl(text, field_name=field_name)


def sanitize_waybill_approval_or_review(raw_value: Any, *, field_name: str) -> str | None:
    return _sanitize_waybill_approval_or_review_impl(raw_value, field_name=field_name)


def extract_waybill_unit_token(text: Any) -> str | None:
    return _extract_waybill_unit_token_impl(text)


def waybill_unit_suspicious(text: Any) -> bool:
    return _waybill_unit_suspicious_impl(text)


def sanitize_waybill_page_items(items: list[dict[str, Any]], page_role: str) -> list[dict[str, Any]]:
    return _sanitize_waybill_page_items_impl(items, page_role)


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


def _coerce_waybill_total(value: float | None) -> int | float | None:
    return _coerce_waybill_total_impl(value)


def _compute_waybill_totals_from_items(items: list[dict[str, Any]]) -> dict[str, int | float | None]:
    return _compute_waybill_totals_from_items_impl(items)


def _fill_waybill_totals_from_safe_sources(out: dict[str, Any]) -> None:
    _fill_waybill_totals_from_safe_sources_impl(out)


def _mark_waybill_required_header_fields(out: dict[str, Any]) -> None:
    _mark_waybill_required_header_fields_impl(out)


def _split_waybill_address_and_basis(address: str | None, basis: str | None) -> tuple[str | None, str | None]:
    return _split_waybill_address_and_basis_impl(address, basis)

    clean_address = _clean_inline_text(address)
    clean_basis = _clean_inline_text(basis)
    if not clean_address:
        return None, clean_basis

    marker_match = re.search(r"\b(?:Основание\s+отпуска|Сснование\s+отпуска|Договор)\b", clean_address, flags=re.I)
    if not marker_match:
        return clean_address, clean_basis

    address_part = _clean_inline_text(clean_address[: marker_match.start()])
    tail = _clean_inline_text(clean_address[marker_match.start() :]) or ""
    if not clean_basis:
        stop_match = re.search(
            r"\b(?:I+[\.\s]+ТОВАРН|ТОВАРНЫЙ\s+РАЗДЕЛ|Принял\s+грузополучатель|С\s+товаром|220\d{3},\s*г\.)\b",
            tail,
            flags=re.I,
        )
        if stop_match:
            tail = _clean_inline_text(tail[: stop_match.start()]) or tail
        clean_basis = tail
    return address_part or clean_address, clean_basis


def finalize_waybill_payload_text(out: dict[str, Any], page_role: str) -> dict[str, Any]:
    out["document_number"] = normalize_waybill_document_number_or_review(out.get("document_number"))
    approvals = out.get("approvals")
    if isinstance(approvals, dict):
        accepted = _clean_inline_text(approvals.get("accepted_for_delivery"))
        if accepted:
            accepted = re.sub(r"\s+W[-\s]?\d+\s*$", "", accepted, flags=re.I)
        approvals["accepted_for_delivery"] = sanitize_waybill_approval_or_review(accepted, field_name="accepted_for_delivery")
        approvals["released_by"] = sanitize_waybill_approval_or_review(approvals.get("released_by"), field_name="released_by")
        approvals["handed_by"] = sanitize_waybill_approval_or_review(approvals.get("handed_by"), field_name="handed_by")
        approvals["received_by"] = sanitize_waybill_approval_or_review(approvals.get("received_by"), field_name="received_by")
        approvals["documents_transferred"] = sanitize_waybill_approval_or_review(
            approvals.get("documents_transferred"),
            field_name="documents_transferred",
        )

    _fill_waybill_totals_from_safe_sources(out)
    totals = out.get("totals")
    if isinstance(totals, dict):
        totals["vat_total_words"] = sanitize_money_words_or_review(totals.get("vat_total_words"), totals.get("vat_total"))
        totals["cost_with_vat_total_words"] = sanitize_money_words_or_review(
            totals.get("cost_with_vat_total_words"),
            totals.get("cost_with_vat_total"),
        )

    out["items"] = sanitize_waybill_page_items(out.get("items") or [], page_role)
    for row in out.get("items") or []:
        if not isinstance(row, dict):
            continue
        unit = _clean_inline_text(row.get("unit"))
        if not unit:
            continue
        unit_lc = unit.lower()
        if "шт" in unit_lc:
            row["unit"] = "шт"
        elif "кг" in unit_lc:
            row["unit"] = "кг"
        elif re.search(r"\bмл\b", unit_lc):
            row["unit"] = "мл"
        else:
            row["unit"] = _review_marker_or_none(unit) if waybill_unit_suspicious(unit) else unit

    for party_key in ("sender", "receiver", "payer"):
        party = out.get(party_key)
        if not isinstance(party, dict):
            continue
        fixed_address, maybe_basis = _split_waybill_address_and_basis(party.get("address"), out.get("basis"))
        party["address"] = fixed_address
        if _is_missing(out.get("basis")) and maybe_basis:
            out["basis"] = maybe_basis

    _mark_waybill_required_header_fields(out)
    out["basis"] = _sanitize_final_text_or_review(out.get("basis"), strict_text=True)
    return out
