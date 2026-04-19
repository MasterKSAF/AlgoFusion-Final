from __future__ import annotations

from pathlib import Path
from typing import Any

from src.modules.runtime_document_assembly import (
    assemble_segment_prediction as _assemble_segment_prediction_impl,
    parse_roi_pages as _parse_roi_pages_impl,
    repair_roi_text_payload_for_v2 as _repair_roi_text_payload_for_v2_impl,
    resolve_page_doc_type as _resolve_page_doc_type_impl,
    run_roi_routing as _run_roi_routing_impl,
    unwrap_prediction_for_item as _unwrap_prediction_for_item_impl,
)
from src.modules.runtime_document_finalize import (
    finalize_document as _finalize_document_impl,
    sanitize_final_json_payload as _sanitize_final_json_payload_impl,
)
from src.modules.runtime_document_type_resolution import (
    infer_doc_type_from_name as _infer_doc_type_from_name_impl,
)
from src.modules.runtime_document_merge import (
    count_present_fields as _count_present_fields_impl,
    item_identity as _item_identity_impl,
    merge_items as _merge_items_impl,
    prefer_last as _prefer_last_impl,
    segment_header_keys as _segment_header_keys_impl,
    segment_tail_keys as _segment_tail_keys_impl,
)
from src.modules.runtime_services import PipelineRuntimeServices
from src.modules.runtime_types import PageWorkItem


def sanitize_final_json_payload(outer_type: str, final_json: dict[str, Any]) -> dict[str, Any]:
    return _sanitize_final_json_payload_impl(outer_type, final_json)


def infer_doc_type_from_name(file_name: str) -> str:
    return _infer_doc_type_from_name_impl(file_name)


def repair_roi_text_payload_for_v2(item: PageWorkItem) -> bool:
    return _repair_roi_text_payload_for_v2_impl(item)


def run_roi_routing(
    services: PipelineRuntimeServices,
    item: PageWorkItem,
    page_dir: Path,
    html_dir: Path | None = None,
) -> Path:
    return _run_roi_routing_impl(services, item, page_dir, html_dir=html_dir)


def prefer_last(base: dict[str, Any], last_payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return _prefer_last_impl(base, last_payload, keys)


def count_present_fields(payload: dict[str, Any], keys: list[str]) -> int:
    return _count_present_fields_impl(payload, keys)


def item_identity(item: dict[str, Any]) -> tuple[Any, ...]:
    return _item_identity_impl(item)


def merge_items(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _merge_items_impl(payloads)


def segment_header_keys(doc_type: str) -> list[str]:
    return _segment_header_keys_impl(doc_type)


def segment_tail_keys(doc_type: str) -> list[str]:
    return _segment_tail_keys_impl(doc_type)


def unwrap_prediction_for_item(item: PageWorkItem, pred: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    return _unwrap_prediction_for_item_impl(item, pred)


def resolve_page_doc_type(
    services: PipelineRuntimeServices,
    item: PageWorkItem,
    roi_path: Path,
) -> str:
    return _resolve_page_doc_type_impl(services, item, roi_path)


def assemble_segment_prediction(
    services: PipelineRuntimeServices,
    source_stem: str,
    segment: dict[str, Any],
    page_predictions: list[dict[str, Any]],
    items: list[PageWorkItem],
    file_key: str | None = None,
) -> dict[str, Any]:
    return _assemble_segment_prediction_impl(
        services,
        source_stem,
        segment,
        page_predictions,
        items,
        file_key=file_key,
    )


def parse_roi_pages(
    services: PipelineRuntimeServices,
    items: list[PageWorkItem],
    docs_dir: Path,
) -> list[dict[str, Any]]:
    return _parse_roi_pages_impl(services, items, docs_dir)


def finalize_document(
    services: PipelineRuntimeServices,
    pred: dict[str, Any],
    docs_dir: Path,
    file_name: str,
) -> dict[str, Any]:
    return _finalize_document_impl(services, pred, docs_dir, file_name)
