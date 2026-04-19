from __future__ import annotations


def infer_precomputed_role_hint(
    *,
    blank: bool,
    has_title: bool,
    has_footer: bool,
    continuation_like: bool,
) -> str:
    if blank:
        return "blank"
    if has_title and has_footer:
        return "single_candidate"
    if has_title:
        return "first_candidate"
    if has_footer:
        return "last_candidate"
    if continuation_like:
        return "middle_candidate"
    return "unknown"


def infer_page_role_hint_v3(
    *,
    page_doc_type: str,
    page_no: int,
    layout_type: str,
    blank: bool,
    has_title: bool,
    has_footer: bool,
    continuation_like: bool,
) -> str:
    if blank:
        return "blank"
    if page_doc_type == "payment_order":
        return "single_candidate" if has_title else "unknown"
    if has_title and has_footer and not continuation_like:
        return "single_candidate"
    if has_title:
        return "first_candidate"
    if has_footer:
        return "last_candidate"
    if continuation_like or (page_no > 1 and layout_type == "table" and not has_title):
        return "middle_candidate"
    return "unknown"
