from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import cv2

from src.modules.runtime_artifacts import save_standard_cleaner_output
from src.modules.runtime_common import ocr_text_from_items, page_no_from_page_id
from src.modules.runtime_documents import (
    assemble_segment_prediction,
    parse_roi_pages,
    run_roi_routing,
    sanitize_final_json_payload,
)
from src.modules.runtime_io import copy_file, ensure_dir, read_json, save_png, write_json
from src.modules.runtime_page_ops import build_stage1_artifacts, run_cleaner_debug
from src.modules.runtime_page_signals import analyze_page_signals_v3
from src.modules.runtime_render import render_input_pages
from src.modules.runtime_run_artifacts import (
    build_documents_manifest,
    build_pipeline_summary,
    group_pages_by_segment,
    init_pipeline_run_dirs,
    persist_segment_prediction_outputs,
)
from src.modules.runtime_segmentation import build_segments
from src.modules.runtime_services import PipelineRuntimeServices
from src.modules.runtime_structure import (
    build_role_aware_structure_from_precomputed,
    build_role_aware_structure_v2,
)
from src.modules.runtime_types import PageWorkItem


def run_job_pipeline_v2_from_precomputed(
    input_path: str | Path,
    base_dir: str | Path,
    page_specs: list[dict[str, Any]],
    header_ocr_by_page: dict[str, dict[str, Any]] | None = None,
    force_doc_type: str | None = None,
) -> dict[str, Any]:
    services = PipelineRuntimeServices.load()

    input_path = Path(input_path)
    base_dir = Path(base_dir)
    ensure_dir(base_dir)

    source_stem = input_path.stem
    run_dirs = init_pipeline_run_dirs(base_dir, source_stem, include_docs_debug=False)

    page_items: list[PageWorkItem] = []
    precomputed_roi_by_page: dict[str, dict[str, Any]] = {}
    all_raw: list[dict[str, Any]] = []
    rendered_pages = render_input_pages(input_path, dpi=services.cleaner_layout.default_dpi)
    rendered_by_no = {int(page["page_no"]): page for page in rendered_pages}

    for spec in sorted(page_specs, key=lambda row: (page_no_from_page_id(row.get("page_id") or ""), str(row.get("page_id") or ""))):
        page_id = str(spec["page_id"])
        page_no = int(spec.get("page_no") or page_no_from_page_id(page_id))
        page_dir = ensure_dir(run_dirs.roi_root / page_id)
        debug_page_dir = ensure_dir(run_dirs.pages_dir / page_id)

        clean_src = Path(spec["clean_png"])
        roi_src = Path(spec["roi_coords"]) if spec.get("roi_coords") else None
        raw_payload = copy.deepcopy(spec.get("raw_payload") or {})
        if not raw_payload and spec.get("raw_ocr"):
            raw_payload = read_json(Path(spec["raw_ocr"]))
        raw_payload["page_id"] = page_id
        if not raw_payload.get("text"):
            raw_payload["text"] = ocr_text_from_items(raw_payload.get("ocr_items") or [])

        roi_payload = copy.deepcopy(spec.get("roi_payload") or {})
        if not roi_payload and roi_src and roi_src.exists():
            roi_payload = read_json(roi_src)
        roi_payload["page_id"] = page_id

        rendered = rendered_by_no.get(page_no)
        if rendered is not None:
            cleaner_debug = run_cleaner_debug(services.cleaner_layout, rendered["bgr"], rendered["input_dpi"], debug_page_dir)
            clean_bgr = cleaner_debug["clean_bgr"]
            source_bgr = rendered["bgr"]
            save_standard_cleaner_output(clean_bgr, run_dirs.cleaner_dir, source_stem, page_no)
        else:
            clean_dst = page_dir / f"{page_id}__clean.png"
            copy_file(clean_src, clean_dst)
            copy_file(clean_src, debug_page_dir / f"{page_id}__clean.png")
            clean_bgr = cv2.imread(str(clean_dst))
            if clean_bgr is None:
                raise FileNotFoundError(f"Cannot read precomputed clean image: {clean_dst}")
            source_bgr = clean_bgr.copy()
        save_png(debug_page_dir / "11_noln.png", clean_bgr)
        save_png(page_dir / f"{page_id}__clean.png", clean_bgr)

        raw_json_path = write_json(page_dir / f"{page_id}__ocr_raw.json", raw_payload)
        write_json(debug_page_dir / f"{page_id}__ocr_raw.json", raw_payload)

        mask, mask_json_path = build_stage1_artifacts(
            services.cleaner_layout,
            page_id,
            clean_bgr,
            {"mode": "precomputed", "input_path": str(input_path)},
            debug_page_dir,
            run_dirs.stage1_doc_dir,
        )

        item = PageWorkItem(
            page_id=page_id,
            page_no=page_no,
            source_bgr=source_bgr.copy(),
            clean_bgr=clean_bgr.copy(),
            no_lines_bgr=clean_bgr.copy(),
            mask=mask,
            mask_json_path=mask_json_path,
            raw_ocr_json_path=raw_json_path,
            full_text=raw_payload.get("text", ""),
            ocr_items=raw_payload.get("ocr_items", []),
        )
        item.signals = analyze_page_signals_v3(
            services.cleaner_layout,
            page_id,
            page_no,
            clean_bgr,
            mask,
            raw_payload,
            debug_page_dir,
            force_doc_type=force_doc_type,
        )
        page_items.append(item)
        precomputed_roi_by_page[page_id] = roi_payload
        all_raw.append(raw_payload)

    write_json(run_dirs.roi_root / "all_pages_ocr_raw.json", all_raw)

    segments = build_segments(page_items)
    manifest = build_documents_manifest(input_path, segments, page_items)
    write_json(run_dirs.debug_dir / "documents_manifest.json", manifest)

    all_roi: list[dict[str, Any]] = []
    final_outputs: list[dict[str, Any]] = []
    pages_by_segment = group_pages_by_segment(page_items)
    multi_segment = len(segments) > 1
    for segment in segments:
        seg_id = segment["segment_id"]
        seg_items = sorted(pages_by_segment.get(seg_id, []), key=lambda x: x.page_no)
        if not seg_items:
            continue

        for item in seg_items:
            debug_page_dir = run_dirs.pages_dir / item.page_id
            page_dir = run_dirs.roi_root / item.page_id
            page_dir.mkdir(parents=True, exist_ok=True)
            try:
                build_role_aware_structure_v2(services, item, debug_page_dir, run_dirs.stage2_dir, roi_dir=page_dir)
            except Exception as exc:
                write_json(
                    debug_page_dir / "14_structure_fallback.json",
                    {
                        "page_id": item.page_id,
                        "reason": str(exc),
                        "mode": "precomputed_roi_fallback",
                    },
                )
                build_role_aware_structure_from_precomputed(services, item, page_dir, precomputed_roi_by_page[item.page_id])
            page_dir.mkdir(parents=True, exist_ok=True)
            header_payload = (header_ocr_by_page or {}).get(item.page_id)
            if header_payload is not None:
                item.header_ocr_json_path = write_json(page_dir / f"{item.page_id}__waybill_header_ocr.json", header_payload)
            run_roi_routing(services, item, page_dir, page_dir)
            all_roi.append(read_json(item.roi_text_path))

        page_predictions = parse_roi_pages(services, seg_items, run_dirs.debug_dir / seg_id)
        file_key = f"{input_path.stem}_{seg_id}.pdf" if multi_segment else f"{input_path.stem}.pdf"
        assembled_pred = assemble_segment_prediction(
            services,
            input_path.stem,
            segment,
            page_predictions,
            seg_items,
            file_key=file_key,
        )
        final_outputs.append(
            persist_segment_prediction_outputs(
                services,
                assembled_pred,
                file_key=file_key,
                pred_dir=run_dirs.pred_dir,
                pred_norm_dir=run_dirs.pred_norm_dir,
                pred_recon_dir=run_dirs.pred_recon_dir,
                final_json_dir=run_dirs.final_json_dir,
                sanitize_final_json_payload=sanitize_final_json_payload,
                write_json=write_json,
                segment_id=seg_id,
                doc_type=segment["doc_type"],
                page_ids=[item.page_id for item in seg_items],
            )
        )

    write_json(run_dirs.roi_root / "all_pages_roi_text.json", all_roi)
    summary = build_pipeline_summary(
        base_dir=base_dir,
        input_path=input_path,
        page_items=page_items,
        segments=segments,
        final_outputs=final_outputs,
    )
    write_json(run_dirs.debug_dir / "summary.json", summary)
    return summary
