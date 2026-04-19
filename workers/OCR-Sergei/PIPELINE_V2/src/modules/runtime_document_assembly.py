from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from src.modules.runtime_account_prot import repair_account_prot_roi_payload
from src.modules.runtime_document_merge import (
    count_present_fields,
    merge_items,
    prefer_last,
    segment_header_keys,
    segment_tail_keys,
)
from src.modules.runtime_document_parser_routing import parse_roi_by_doc_type
from src.modules.runtime_document_type_resolution import choose_resolved_doc_type
from src.modules.runtime_invoice_postprocess import repair_invoice_roi_payload
from src.modules.runtime_io import read_json, write_json, write_text
from src.modules.runtime_postprocess import deep_fill, postprocess_page_prediction, unwrap_page_prediction
from src.modules.runtime_segmentation import hard_signal_doc_type
from src.modules.runtime_services import PipelineRuntimeServices
from src.modules.runtime_types import PageWorkItem


def repair_roi_text_payload_for_v2(item: PageWorkItem) -> bool:
    if item.roi_text_path is None or not item.roi_text_path.exists():
        return False

    payload = read_json(item.roi_text_path)
    doc_type = item.segment_doc_type or payload.get("doc_type") or "unknown"
    changed = False

    if doc_type == "account_prot" and item.page_role in {"first", "single"}:
        changed = repair_account_prot_roi_payload(payload, ocr_items=item.ocr_items) or changed
    if doc_type == "invoice" and item.page_role in {"first", "single"}:
        changed = repair_invoice_roi_payload(payload) or changed

    if changed:
        write_json(item.roi_text_path, payload)
    return changed


def run_roi_routing(
    services: PipelineRuntimeServices,
    item: PageWorkItem,
    page_dir: Path,
    html_dir: Path | None = None,
) -> Path:
    clean_png = page_dir / f"{item.page_id}__clean.png"
    if not clean_png.exists():
        clean_png = page_dir / "11_noln.png"
    _result_json, html_content = services.roi_assignment.run(
        str(clean_png),
        str(item.roi_coords_path),
        str(item.raw_ocr_json_path),
    )
    item.roi_text_path = page_dir / f"{item.page_id}_roi_text.json"
    if html_content:
        write_text((html_dir or page_dir) / "15_roi.html", html_content)
    repair_roi_text_payload_for_v2(item)
    return item.roi_text_path


def unwrap_prediction_for_item(item: PageWorkItem, pred: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    doc_type = item.segment_doc_type or "unknown"
    if doc_type == "waybill":
        return "waybill", copy.deepcopy(pred)
    outer_type, _old_key, payload = unwrap_page_prediction(pred, doc_type)
    return outer_type, copy.deepcopy(payload)


def resolve_page_doc_type(
    services: PipelineRuntimeServices,
    item: PageWorkItem,
    roi_path: Path,
) -> str:
    declared = item.segment_doc_type or "unknown"
    hard_type = hard_signal_doc_type(item)
    detected_type = services.document_parser.detect_doc_type(roi_path)
    return choose_resolved_doc_type(declared=declared, hard_type=hard_type, detected_type=detected_type)


def assemble_segment_prediction(
    services: PipelineRuntimeServices,
    source_stem: str,
    segment: dict[str, Any],
    page_predictions: list[dict[str, Any]],
    items: list[PageWorkItem],
    file_key: str | None = None,
) -> dict[str, Any]:
    doc_type = segment["doc_type"]
    file_key = file_key or f"{source_stem}_{segment['segment_id']}.pdf"
    normalized: list[tuple[str, dict[str, Any], PageWorkItem]] = []
    for item, pred in zip(items, page_predictions):
        outer_type, payload = unwrap_prediction_for_item(item, pred)
        outer_type, payload = postprocess_page_prediction(item, outer_type, payload)
        normalized.append((outer_type, payload, item))

    if not normalized:
        raise ValueError(f"No page predictions to assemble for {segment['segment_id']}")

    if doc_type == "payment_order":
        header_keys = segment_header_keys(doc_type)
        best_outer, best_payload, _best_item = max(
            normalized,
            key=lambda row: count_present_fields(row[1], header_keys),
        )
        best_payload.pop("_page_role", None)
        best_payload.pop("_page_id", None)
        return {best_outer: {file_key: best_payload}}

    outer_type = normalized[0][0]
    payloads = [payload for _outer, payload, _item in normalized]
    first_candidates = [payload for _outer, payload, item in normalized if item.page_role in {"first", "single"}]
    base_payload = copy.deepcopy(first_candidates[0] if first_candidates else payloads[0])

    assembled = copy.deepcopy(base_payload)
    for payload in payloads:
        assembled = deep_fill(assembled, payload)

    assembled["items"] = merge_items(payloads)

    tail_keys = segment_tail_keys(doc_type)
    if tail_keys:
        for payload in reversed(payloads):
            assembled = prefer_last(assembled, payload, tail_keys)

    if doc_type == "waybill" and not assembled.get("document_type"):
        for _outer, _payload, item in normalized:
            title_text = (item.signals or {}).get("page_document_type_text")
            if title_text:
                assembled["document_type"] = title_text
                break

    assembled.pop("_page_role", None)
    assembled.pop("_page_id", None)
    return {outer_type: {file_key: assembled}}


def parse_roi_pages(
    services: PipelineRuntimeServices,
    items: list[PageWorkItem],
    docs_dir: Path,
) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for item in items:
        roi_path = item.roi_text_path
        if roi_path is None:
            raise FileNotFoundError(f"ROI text path is missing for {item.page_id}")

        doc_type = resolve_page_doc_type(services, item, roi_path)
        item.segment_doc_type = doc_type
        pred = parse_roi_by_doc_type(services.document_parser, roi_path, doc_type, page_id=item.page_id)

        outer_type, payload = unwrap_prediction_for_item(item, pred)
        outer_type, payload = postprocess_page_prediction(item, outer_type, payload)
        page_pred = payload if doc_type == "waybill" else {outer_type: {item.page_id: payload}}
        parsed.append(page_pred)
        write_json(docs_dir / "page_preds" / f"{item.page_id}.json", page_pred)
    return parsed
