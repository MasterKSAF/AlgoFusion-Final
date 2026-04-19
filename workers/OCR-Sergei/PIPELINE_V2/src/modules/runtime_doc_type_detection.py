from __future__ import annotations

import re

from shared.resources.text_lexicon import (
    ACCOUNT_PROT_PATTERN,
    INVOICE_BASIS_PATTERN,
    INVOICE_BUYER_PATTERN,
    INVOICE_DATE_PATTERN,
    INVOICE_NUMBER_PATTERN,
    INVOICE_SELLER_PATTERN,
    INVOICE_SUPPLIER_PATTERN,
    PAYMENT_ORDER_PATTERN,
    WAYBILL_BASIS_PATTERN,
    WAYBILL_DOC_PATTERN,
    WAYBILL_RECEIVER_PATTERN,
    WAYBILL_RELEASE_PATTERN,
    WAYBILL_SENDER_PATTERN,
)
from src.modules.runtime_text_quality import _clean_inline_text
from src.modules.runtime_types import PageWorkItem


def _signal_text(item: PageWorkItem, key: str) -> str:
    return _clean_inline_text(((item.signals or {}).get(key))) or ""


def _hard_signal_doc_type(item: PageWorkItem) -> str | None:
    signals = item.signals or {}
    top_text = _signal_text(item, "top_text")
    full_text = _signal_text(item, "full_text")
    title_text = _signal_text(item, "page_document_type_text")
    combined = " ".join(part for part in [title_text, top_text, full_text] if part)

    if not combined:
        return None
    if re.search(ACCOUNT_PROT_PATTERN, combined, flags=re.I):
        return "account_prot"
    if re.search(PAYMENT_ORDER_PATTERN, combined, flags=re.I):
        return "payment_order"
    if (
        title_text
        or re.search(WAYBILL_DOC_PATTERN, combined, flags=re.I)
        or (
            re.search(WAYBILL_SENDER_PATTERN, combined, flags=re.I)
            and re.search(WAYBILL_RECEIVER_PATTERN, combined, flags=re.I)
            and (
                re.search(WAYBILL_BASIS_PATTERN, combined, flags=re.I)
                or re.search(WAYBILL_RELEASE_PATTERN, combined, flags=re.I)
            )
        )
    ):
        return "waybill"
    if (
        (
            re.search(INVOICE_NUMBER_PATTERN, combined, flags=re.I)
            or re.search(INVOICE_DATE_PATTERN, combined, flags=re.I)
        )
        and not re.search(WAYBILL_DOC_PATTERN, combined, flags=re.I)
        and (
            (
                re.search(INVOICE_SELLER_PATTERN, combined, flags=re.I)
                and re.search(INVOICE_BUYER_PATTERN, combined, flags=re.I)
            )
            or (
                re.search(INVOICE_SUPPLIER_PATTERN, combined, flags=re.I)
                and re.search(INVOICE_BUYER_PATTERN, combined, flags=re.I)
            )
            or re.search(INVOICE_BASIS_PATTERN, combined, flags=re.I)
        )
    ):
        return "invoice"
    return None


def hard_signal_doc_type(item: PageWorkItem) -> str | None:
    return _hard_signal_doc_type(item)


def segment_doc_type(items: list[PageWorkItem]) -> str | None:
    first_page_hard: list[str] = []
    hard_counts: dict[str, int] = {}
    for item in items:
        hard_doc_type = _hard_signal_doc_type(item)
        if not hard_doc_type:
            continue
        hard_counts[hard_doc_type] = hard_counts.get(hard_doc_type, 0) + 1
        role_hint = ((item.signals or {}).get("role_hint") or "").lower()
        if role_hint in {"single_candidate", "first_candidate"}:
            first_page_hard.append(hard_doc_type)

    if first_page_hard:
        distinct_first = set(first_page_hard)
        if len(distinct_first) == 1:
            return first_page_hard[0]
        return None

    if hard_counts:
        ordered = sorted(hard_counts.items(), key=lambda pair: (-pair[1], pair[0]))
        best_type, best_count = ordered[0]
        if len(ordered) == 1 or ordered[1][1] < best_count:
            return best_type
        return None

    totals = {"invoice": 0, "waybill": 0, "payment_order": 0, "account_prot": 0}
    for item in items:
        scores = (item.signals or {}).get("scores") or {}
        for key in totals:
            totals[key] += int(scores.get(key, 0))
    winner = max(totals, key=totals.get)
    return winner if totals[winner] > 0 else None
