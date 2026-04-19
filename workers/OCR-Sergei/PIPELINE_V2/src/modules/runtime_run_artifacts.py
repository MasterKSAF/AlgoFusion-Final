from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.modules.runtime_io import ensure_dir, mkdir_clean
from src.modules.runtime_prediction_artifacts import build_prediction_artifacts
from src.modules.runtime_services import PipelineRuntimeServices
from src.modules.runtime_types import PageWorkItem


@dataclass(frozen=True)
class PipelineRunDirs:
    cleaner_dir: Path
    stage1_root: Path
    stage1_doc_dir: Path
    stage2_dir: Path
    roi_root: Path
    data_root: Path
    pred_dir: Path
    pred_norm_dir: Path
    pred_recon_dir: Path
    final_json_dir: Path
    debug_dir: Path
    pages_dir: Path
    docs_debug_dir: Path | None = None


def init_pipeline_run_dirs(base_dir: Path, source_stem: str, *, include_docs_debug: bool) -> PipelineRunDirs:
    cleaner_dir = mkdir_clean(base_dir / "cleaner")
    stage1_root = mkdir_clean(base_dir / "out_table_merge")
    stage1_doc_dir = ensure_dir(stage1_root / source_stem)
    stage2_dir = mkdir_clean(base_dir / "final_rebuilt_auto")
    roi_root = ensure_dir(stage2_dir / "_clean_page_plus_roi_json")
    data_root = ensure_dir(base_dir / "data")
    pred_dir = mkdir_clean(data_root / "pred")
    pred_norm_dir = mkdir_clean(data_root / "pred_normalized")
    pred_recon_dir = mkdir_clean(data_root / "pred_reconciled")
    final_json_dir = mkdir_clean(data_root / "final_json")
    debug_dir = mkdir_clean(base_dir / "_pipeline_v2_debug")
    pages_dir = ensure_dir(debug_dir / "pages")
    docs_debug_dir = ensure_dir(debug_dir / "docs") if include_docs_debug else None
    return PipelineRunDirs(
        cleaner_dir=cleaner_dir,
        stage1_root=stage1_root,
        stage1_doc_dir=stage1_doc_dir,
        stage2_dir=stage2_dir,
        roi_root=roi_root,
        data_root=data_root,
        pred_dir=pred_dir,
        pred_norm_dir=pred_norm_dir,
        pred_recon_dir=pred_recon_dir,
        final_json_dir=final_json_dir,
        debug_dir=debug_dir,
        pages_dir=pages_dir,
        docs_debug_dir=docs_debug_dir,
    )


def build_documents_manifest(
    input_path: Path,
    segments: list[dict[str, Any]],
    page_items: list[PageWorkItem],
) -> dict[str, Any]:
    return {
        "input_path": str(input_path),
        "segments": segments,
        "pages": [
            {
                "page_id": item.page_id,
                "page_no": item.page_no,
                "segment_id": item.segment_id,
                "doc_type": item.segment_doc_type,
                "page_role": item.page_role,
                "signals": item.signals,
            }
            for item in page_items
        ],
    }


def group_pages_by_segment(page_items: list[PageWorkItem]) -> dict[str, list[PageWorkItem]]:
    pages_by_segment: dict[str, list[PageWorkItem]] = {}
    for item in page_items:
        if item.segment_id is None:
            continue
        pages_by_segment.setdefault(item.segment_id, []).append(item)
    return pages_by_segment


def persist_segment_prediction_outputs(
    services: PipelineRuntimeServices,
    assembled_pred: dict[str, Any],
    *,
    file_key: str,
    pred_dir: Path,
    pred_norm_dir: Path,
    pred_recon_dir: Path,
    final_json_dir: Path,
    sanitize_final_json_payload: Callable[[Any], Any],
    write_json: Callable[[Path, Any], Any],
    segment_id: str,
    doc_type: str,
    page_ids: list[str],
) -> dict[str, Any]:
    out_name = Path(file_key).with_suffix(".json").name
    pred_path = pred_dir / out_name
    pred_norm_path = pred_norm_dir / out_name
    pred_recon_path = pred_recon_dir / out_name
    final_json_path = final_json_dir / out_name

    final_outer_type = next(iter(assembled_pred.keys()))
    artifacts = build_prediction_artifacts(
        services,
        assembled_pred,
        file_key=file_key,
        outer_type=final_outer_type,
        sanitize_final_json_payload=sanitize_final_json_payload,
    )
    final_json = artifacts.final_json
    if final_outer_type == "waybill" and isinstance(final_json, dict) and list(final_json.keys()) == [file_key]:
        final_json = final_json[file_key]

    write_json(pred_path, assembled_pred)
    write_json(pred_norm_path, artifacts.pred_norm)
    write_json(pred_recon_path, artifacts.pred_recon)
    write_json(final_json_path, final_json)
    return {
        "segment_id": segment_id,
        "doc_type": doc_type,
        "file_key": file_key,
        "pred_path": str(pred_path),
        "pred_norm_path": str(pred_norm_path),
        "pred_recon_path": str(pred_recon_path),
        "final_json_path": str(final_json_path),
        "page_ids": page_ids,
    }


def build_pipeline_summary(
    *,
    base_dir: Path,
    input_path: Path,
    page_items: list[PageWorkItem],
    segments: list[dict[str, Any]],
    final_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "base_dir": str(base_dir),
        "input_path": str(input_path),
        "page_count": len(page_items),
        "segment_count": len(segments),
        "final_outputs": final_outputs,
    }
