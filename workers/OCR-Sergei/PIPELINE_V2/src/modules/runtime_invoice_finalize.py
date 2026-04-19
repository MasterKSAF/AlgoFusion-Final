from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_invoice_items import (
    clean_invoice_description_value as _clean_invoice_description_value,
    extract_invoice_article_candidate as _extract_invoice_article_candidate,
    normalize_invoice_unit_v2 as _normalize_invoice_unit_v2,
)
from src.modules.runtime_money_words import _format_money_words_ru
from src.modules.runtime_numeric_reconciliation import finalize_invoice_numeric_row as _finalize_invoice_numeric_row
from src.modules.runtime_text_quality import (
    BAD_SYMBOL_RE,
    REVIEW_FIELD_MARKER,
    _clean_inline_text,
    _is_review_field_marker,
    _review_marker_or_none,
    _sanitize_final_text_or_review,
)


def _invoice_unit_suspicious(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return False
    normalized = _normalize_invoice_unit_v2(cleaned)
    if normalized in {"\u0448\u0442", "\u043a\u0433", "\u043c\u043b", "\u043b", "\u0443\u043f"}:
        return False
    if re.search(r"\d", cleaned):
        return True
    if BAD_SYMBOL_RE.search(cleaned):
        return True
    if any(char.isalpha() for char in cleaned):
        return True
    return False


def _trim_invoice_note_noise(text: Any) -> str | None:
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return None
    stop_pos = len(cleaned)
    for pattern in [
        r"\b\u0418\u0442\u043e\u0433\u043e\b",
        r"\b\u0412\u0441\u0435\u0433\u043e\s+\u043d\u0430\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u043d\u0438\u0439\b",
        r"\b\u0421\u0435\u043c\u044c\u0441\u043e\u0442\b",
        r"\b\u0428\u0435\u0441\u0442\u044c\u0441\u043e\u0442\b",
        r"\b\u041f\u044f\u0442\u044c\u0441\u043e\u0442\b",
        r"\b\u0427\u0435\u0442\u044b\u0440\u0435\u0441\u0442\u0430\b",
        r"\b\u0422\u0440\u0438\u0441\u0442\u0430\b",
        r"\b\u0414\u0432\u0435\u0441\u0442\u0438\b",
        r"\b\u0421\u0442\u043e\b",
        r"\b\u0421\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0441\u0442\s+\u043f\u043e\s+\u0440\u0430\u0431\u043e\u0442\u0435\b",
        r"\b\u0414\u0438\u0440\u0435\u043a\u0442\u043e\u0440\b",
        r"\|\s*\d+\s*\|",
    ]:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            stop_pos = min(stop_pos, match.start())
    cleaned = cleaned[:stop_pos]
    cleaned = re.sub(r"[|]+", " ", cleaned)
    cleaned = re.sub(r"[.]{3,}", "...", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-.")
    cleaned = re.sub(r"\s+[A-Za-z]$", "", cleaned).strip(" ,;:-.")
    return cleaned or None


def _sanitize_invoice_header_text_or_review(value: Any, *, allow_missing: bool = False) -> str | None:
    if _is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    cleaned = _sanitize_final_text_or_review(value, strict_text=True)
    if cleaned:
        return cleaned
    if not _clean_inline_text(value):
        return None if allow_missing else REVIEW_FIELD_MARKER
    return REVIEW_FIELD_MARKER


def _sanitize_invoice_code_or_review(value: Any) -> str:
    if _is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    cleaned = _clean_inline_text(value)
    if not cleaned:
        return REVIEW_FIELD_MARKER
    if BAD_SYMBOL_RE.search(cleaned) or re.search(r"[?\ufffd]", cleaned):
        return REVIEW_FIELD_MARKER
    return cleaned


def _extract_single_barcode_from_invoice_description(value: Any) -> str | None:
    cleaned = _clean_inline_text(value) or ""
    if not cleaned:
        return None
    matches = re.findall(r"(?<!\d)(\d{8,14})(?!\d)", cleaned)
    unique = list(dict.fromkeys(matches))
    return unique[0] if len(unique) == 1 else None


def _mark_invoice_required_header_fields(out: dict[str, Any]) -> None:
    supplier = out.get("supplier")
    if isinstance(supplier, dict) and _clean_inline_text(supplier.get("name")) is not None:
        for field in ("address", "bank_account", "bic", "tax_id"):
            if not _clean_inline_text(supplier.get(field)) and not _is_review_field_marker(supplier.get(field)):
                supplier[field] = REVIEW_FIELD_MARKER
            elif field == "address":
                supplier[field] = _sanitize_invoice_header_text_or_review(supplier.get(field))

    customer = out.get("customer")
    if isinstance(customer, dict) and _clean_inline_text(customer.get("name")) is not None:
        for field in ("address", "tax_id"):
            if not _clean_inline_text(customer.get(field)) and not _is_review_field_marker(customer.get(field)):
                customer[field] = REVIEW_FIELD_MARKER
            elif field == "address":
                customer[field] = _sanitize_invoice_header_text_or_review(customer.get(field))


def _finalize_invoice_payload_text(out: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(out, dict):
        return out

    items = out.get("items")
    if isinstance(items, list):
        for line_number, row in enumerate(items, start=1):
            if not isinstance(row, dict):
                continue
            row["line_number"] = line_number
            description_before_sanitize = _clean_inline_text(row.get("description"))
            if _is_review_field_marker(row.get("article")) or not _clean_inline_text(row.get("article")):
                article_candidate = _extract_invoice_article_candidate(description_before_sanitize, line_number=line_number)
                if article_candidate:
                    row["article"] = article_candidate
                    stripped = _clean_invoice_description_value(description_before_sanitize, article=article_candidate)
                    if stripped:
                        row["description"] = stripped
                        description_before_sanitize = stripped
            if _is_review_field_marker(row.get("barcode")) or not _clean_inline_text(row.get("barcode")):
                barcode_candidate = _extract_single_barcode_from_invoice_description(description_before_sanitize)
                if barcode_candidate:
                    row["barcode"] = barcode_candidate
            row["article"] = _sanitize_invoice_code_or_review(row.get("article"))
            row["barcode"] = _sanitize_invoice_code_or_review(row.get("barcode"))
            normalized_unit = _normalize_invoice_unit_v2(row.get("unit"))
            if normalized_unit and not _invoice_unit_suspicious(normalized_unit):
                row["unit"] = normalized_unit
            elif _invoice_unit_suspicious(row.get("unit")) or _invoice_unit_suspicious(normalized_unit):
                row["unit"] = _review_marker_or_none(row.get("unit"))
            if not _clean_inline_text(row.get("unit")):
                row["unit"] = REVIEW_FIELD_MARKER
            row["description"] = _sanitize_final_text_or_review(
                row.get("description"),
                invoice_description=True,
                item_text=True,
            )
            _finalize_invoice_numeric_row(row)

    totals = out.get("totals")
    if isinstance(totals, dict):
        total_value = totals.get("total_with_disc_incl_vat")
        if not _clean_inline_text(totals.get("total_in_words")):
            rebuilt_words = _format_money_words_ru(total_value)
            if rebuilt_words:
                totals["total_in_words"] = rebuilt_words
            else:
                totals["total_in_words"] = REVIEW_FIELD_MARKER
        else:
            totals["total_in_words"] = _sanitize_invoice_header_text_or_review(totals.get("total_in_words"))

    signatory = out.get("signatory")
    if isinstance(signatory, dict):
        signatory["position"] = _sanitize_invoice_header_text_or_review(
            signatory.get("position"),
            allow_missing=True,
        )
        signatory["name"] = _sanitize_invoice_header_text_or_review(
            signatory.get("name"),
            allow_missing=True,
        )

    _mark_invoice_required_header_fields(out)
    out["note"] = _trim_invoice_note_noise(out.get("note"))
    return out


finalize_invoice_payload_text = _finalize_invoice_payload_text
invoice_unit_suspicious = _invoice_unit_suspicious
sanitize_invoice_code_or_review = _sanitize_invoice_code_or_review
sanitize_invoice_header_text_or_review = _sanitize_invoice_header_text_or_review
trim_invoice_note_noise = _trim_invoice_note_noise
