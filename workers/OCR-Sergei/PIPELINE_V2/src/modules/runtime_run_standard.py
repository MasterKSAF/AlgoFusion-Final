from __future__ import annotations

from pathlib import Path
from typing import Any

from src.modules.runtime_artifacts import copy_standard_stage1_outputs, save_standard_cleaner_output
from src.modules.runtime_documents import (
    assemble_segment_prediction,
    parse_roi_pages,
    run_roi_routing,
    sanitize_final_json_payload,
)
from src.modules.runtime_io import copy_file, ensure_dir, read_json, save_png, write_json
from src.modules.runtime_page_ops import build_stage1_artifacts, run_cleaner_debug, run_raw_ocr_page
from src.modules.runtime_page_signals import analyze_page_signals
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
from src.modules.runtime_structure import build_role_aware_structure_v2
from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_header import run_waybill_header_crop_ocr


def run_standard_output_pipeline(
    services: PipelineRuntimeServices,
    input_path: Path,
    base_dir: Path,
    max_pages: int | None = None,
    force_doc_type: str | None = None,
) -> dict[str, Any]:
    source_stem = input_path.stem
    run_dirs = init_pipeline_run_dirs(base_dir, source_stem, include_docs_debug=True)

    rendered_pages = render_input_pages(input_path, dpi=services.cleaner_layout.default_dpi, max_pages=max_pages)
    page_items: list[PageWorkItem] = []
    all_raw: list[dict[str, Any]] = []

    for page in rendered_pages:
        page_id = page["page_id"]
        page_no = int(page["page_no"])
        debug_page_dir = ensure_dir(run_dirs.pages_dir / page_id)
        roi_page_dir = ensure_dir(run_dirs.roi_root / page_id)

        cleaner_debug = run_cleaner_debug(services.cleaner_layout, page["bgr"], page["input_dpi"], debug_page_dir)
        clean_bgr = cleaner_debug["clean_bgr"]
        save_standard_cleaner_output(clean_bgr, run_dirs.cleaner_dir, source_stem, page_no)

        mask, mask_json_path = build_stage1_artifacts(
            services.cleaner_layout,
            page_id,
            clean_bgr,
            page["source"],
            debug_page_dir,
            run_dirs.stage1_doc_dir,
        )
        copy_file(debug_page_dir / "09_a4.png", run_dirs.stage1_doc_dir / f"{page_id}__cleaner.png")
        copy_standard_stage1_outputs(page_id, debug_page_dir, run_dirs.stage1_doc_dir)

        no_lines_bgr = services.roi_render.remove_lines(clean_bgr, mask)
        save_png(debug_page_dir / "11_noln.png", no_lines_bgr)
        save_png(roi_page_dir / f"{page_id}__clean.png", no_lines_bgr)

        raw_payload, raw_json_path = run_raw_ocr_page(services.raw_ocr, page_id, no_lines_bgr, roi_page_dir)
        all_raw.append(raw_payload)

        item = PageWorkItem(
            page_id=page_id,
            page_no=page_no,
            source_bgr=page["bgr"],
            clean_bgr=clean_bgr,
            no_lines_bgr=no_lines_bgr,
            mask=mask,
            mask_json_path=mask_json_path,
            raw_ocr_json_path=raw_json_path,
            full_text=raw_payload.get("text", ""),
            ocr_items=raw_payload.get("ocr_items", []),
        )
        item.signals = analyze_page_signals(
            services.cleaner_layout,
            page_id,
            item.page_no,
            clean_bgr,
            mask,
            raw_payload,
            debug_page_dir,
            force_doc_type=force_doc_type,
        )
        write_json(roi_page_dir / f"{page_id}__signals.json", item.signals)
        page_items.append(item)

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
            roi_page_dir = run_dirs.roi_root / item.page_id
            build_role_aware_structure_v2(services, item, debug_page_dir, run_dirs.stage2_dir, roi_dir=roi_page_dir)
            run_waybill_header_crop_ocr(services.raw_ocr, item, item.roi_coords_path, roi_page_dir, debug_page_dir)
            run_roi_routing(services, item, roi_page_dir, html_dir=debug_page_dir)
            all_roi.append(read_json(item.roi_text_path))

        seg_debug_dir = ensure_dir(run_dirs.docs_debug_dir / seg_id)
        page_predictions = parse_roi_pages(services, seg_items, seg_debug_dir)
        file_key = f"{source_stem}_{seg_id}.pdf" if multi_segment else f"{source_stem}.pdf"
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


def run_job_pipeline_v2(
    input_path: str | Path,
    base_dir: str | Path,
    max_pages: int | None = None,
    force_doc_type: str | None = None,
) -> dict[str, Any]:
    input_path = Path(input_path)
    base_dir = Path(base_dir)
    ensure_dir(base_dir)
    return run_standard_output_pipeline(
        PipelineRuntimeServices.load(),
        input_path=input_path,
        base_dir=base_dir,
        max_pages=max_pages,
        force_doc_type=force_doc_type,
    )
