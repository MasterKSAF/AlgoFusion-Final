from __future__ import annotations

from collections.abc import Mapping


def select_page_doc_type(
    *,
    force_doc_type: str | None,
    payment_title: bool,
    waybill_title: bool,
    protocol_title: bool,
    scores: Mapping[str, int],
) -> str:
    if force_doc_type:
        return force_doc_type
    if payment_title:
        return "payment_order"
    if waybill_title:
        return "waybill"
    if protocol_title:
        return "account_prot"
    page_doc_type = max(scores, key=scores.get)
    if scores[page_doc_type] <= 0:
        return "unknown"
    return page_doc_type
