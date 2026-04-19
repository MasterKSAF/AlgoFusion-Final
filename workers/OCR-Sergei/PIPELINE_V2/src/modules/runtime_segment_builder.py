from __future__ import annotations

from src.modules.runtime_doc_type_detection import segment_doc_type
from src.modules.runtime_types import PageWorkItem


def _assign_segment_metadata(seg_id: str, doc_type: str, pages: list[PageWorkItem]) -> dict[str, object]:
    roles = ["single"] if len(pages) == 1 else ["first"] + ["middle"] * max(0, len(pages) - 2) + ["last"]
    for item, role in zip(pages, roles):
        item.segment_id = seg_id
        item.segment_doc_type = doc_type
        item.page_role = role
    return {
        "segment_id": seg_id,
        "doc_type": doc_type,
        "page_ids": [item.page_id for item in pages],
        "page_roles": {item.page_id: item.page_role for item in pages},
    }


def build_segments(page_items: list[PageWorkItem]) -> list[dict[str, object]]:
    non_blank = [item for item in page_items if not (item.signals or {}).get("blank")]
    segments: list[list[PageWorkItem]] = []
    current: list[PageWorkItem] = []

    for item in non_blank:
        sig = item.signals or {}
        if not current:
            current = [item]
            continue

        prev = current[-1]
        prev_sig = prev.signals or {}
        prev_type = segment_doc_type(current)
        cur_type = sig.get("page_doc_type")

        start_new = False
        if sig.get("role_hint") in {"single_candidate", "first_candidate"}:
            if prev_sig.get("role_hint") in {"single_candidate", "last_candidate"}:
                start_new = True
            elif prev_type and cur_type and cur_type not in {"unknown", prev_type}:
                start_new = True
            elif prev_sig.get("has_footer") and sig.get("has_title"):
                start_new = True

        if start_new:
            segments.append(current)
            current = [item]
        else:
            current.append(item)

    if current:
        segments.append(current)

    out: list[dict[str, object]] = []
    for idx, pages in enumerate(segments, 1):
        doc_type = segment_doc_type(pages) or "unknown"
        seg_id = f"doc_{idx:02d}"
        out.append(_assign_segment_metadata(seg_id, doc_type, pages))
    return out


def build_segments_v2(page_items: list[PageWorkItem]) -> list[dict[str, object]]:
    non_blank = [item for item in sorted(page_items, key=lambda x: x.page_no) if not (item.signals or {}).get("blank")]
    segments: list[list[PageWorkItem]] = []
    current: list[PageWorkItem] = []

    for item in non_blank:
        sig = item.signals or {}
        if not current:
            current = [item]
            continue

        prev = current[-1]
        prev_sig = prev.signals or {}
        prev_type = segment_doc_type(current)
        cur_type = sig.get("page_doc_type")

        consecutive = item.page_no == prev.page_no + 1
        strong_start = bool(sig.get("has_title")) and not sig.get("continuation_like")
        prev_closed = bool(prev_sig.get("has_footer")) or prev_sig.get("role_hint") in {"single_candidate", "last_candidate"}

        start_new = False
        if not consecutive:
            start_new = True
        elif cur_type == "payment_order" and strong_start:
            start_new = True
        elif strong_start and prev_closed:
            if prev_type and cur_type and cur_type not in {"unknown", prev_type}:
                start_new = True
            elif prev_sig.get("has_footer"):
                start_new = True

        if start_new:
            segments.append(current)
            current = [item]
        else:
            current.append(item)

    if current:
        segments.append(current)

    out: list[dict[str, object]] = []
    for idx, pages in enumerate(segments, 1):
        doc_type = segment_doc_type(pages) or "unknown"
        seg_id = f"doc_{idx:02d}"
        out.append(_assign_segment_metadata(seg_id, doc_type, pages))
    return out


def select_structure_profile(item: PageWorkItem) -> str:
    doc_type = item.segment_doc_type or "unknown"
    layout_hint = ((item.signals or {}).get("layout_type") or "table").lower()
    if doc_type == "payment_order":
        return "payment_order_form"
    if doc_type == "waybill":
        if item.page_role in {"middle", "last"}:
            return "waybill_continuation_table"
        return "waybill_first_table"
    if doc_type == "invoice":
        return f"invoice_{'continuation' if item.page_role in {'middle', 'last'} else 'lead'}_{layout_hint}"
    if doc_type == "account_prot":
        return f"account_prot_{'continuation' if item.page_role in {'middle', 'last'} else 'lead'}_{layout_hint}"
    return f"{doc_type}_{layout_hint}"
