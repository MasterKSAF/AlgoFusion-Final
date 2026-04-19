from __future__ import annotations

from pathlib import Path

from src.modules.runtime_documents import assemble_segment_prediction, parse_roi_pages, finalize_document, run_roi_routing
from src.modules.runtime_io import ensure_dir, mkdir_clean, read_json, save_png, write_json
from src.modules.runtime_page_ops import build_stage1_artifacts, run_cleaner_debug, run_raw_ocr_page
from src.modules.runtime_page_signals import analyze_page_signals
from src.modules.runtime_render import render_input_pages
from src.modules.runtime_segmentation import build_segments
from src.modules.runtime_services import PipelineRuntimeServices
from src.modules.runtime_structure import build_role_aware_structure_v2
from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_header import run_waybill_header_crop_ocr


def run_multipage_debug_pipeline(
    input_path: str | Path,
    output_root: str | Path,
    run_name: str = "mp_debug",
    max_pages: int | None = None,
    force_doc_type: str | None = None,
) -> dict[str, object]:
    services = PipelineRuntimeServices.load()

    input_path = Path(input_path)
    output_root = Path(output_root)
    run_dir = mkdir_clean(output_root / run_name)
    pages_dir = ensure_dir(run_dir / "pages")
    stage1_dir = ensure_dir(run_dir / "stage1")
    stage2_tmp_dir = ensure_dir(run_dir / "stage2_raw")
    docs_dir = ensure_dir(run_dir / "docs")

    rendered_pages = render_input_pages(input_path, dpi=services.cleaner_layout.default_dpi, max_pages=max_pages)
    page_items: list[PageWorkItem] = []
    all_raw: list[dict[str, object]] = []

    for page in rendered_pages:
        page_id = page["page_id"]
        page_dir = ensure_dir(pages_dir / page_id)

        cleaner_debug = run_cleaner_debug(services.cleaner_layout, page["bgr"], page["input_dpi"], page_dir)
        clean_bgr = cleaner_debug["clean_bgr"]
        mask, mask_json_path = build_stage1_artifacts(services.cleaner_layout, page_id, clean_bgr, page["source"], page_dir, stage1_dir)

        no_lines_bgr = services.roi_render.remove_lines(clean_bgr, mask)
        save_png(page_dir / "11_noln.png", no_lines_bgr)

        raw_payload, raw_json_path = run_raw_ocr_page(services.raw_ocr, page_id, no_lines_bgr, page_dir)
        all_raw.append(raw_payload)

        item = PageWorkItem(
            page_id=page_id,
            page_no=int(page["page_no"]),
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
            page_dir,
            force_doc_type=force_doc_type,
        )
        page_items.append(item)

    write_json(run_dir / "all_pages_ocr_raw.json", all_raw)

    segments = build_segments(page_items)
    manifest = {
        "input_path": str(input_path),
        "run_name": run_name,
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
    write_json(run_dir / "documents_manifest.json", manifest)

    all_roi: list[dict[str, object]] = []
    final_outputs: list[dict[str, object]] = []

    pages_by_segment: dict[str, list[PageWorkItem]] = {}
    for item in page_items:
        if item.segment_id is None:
            continue
        pages_by_segment.setdefault(item.segment_id, []).append(item)

    for segment in segments:
        seg_id = segment["segment_id"]
        seg_items = sorted(pages_by_segment.get(seg_id, []), key=lambda x: x.page_no)
        if not seg_items:
            continue

        for item in seg_items:
            page_dir = pages_dir / item.page_id
            build_role_aware_structure_v2(services, item, page_dir, stage2_tmp_dir)
            run_waybill_header_crop_ocr(services.raw_ocr, item, item.roi_coords_path, page_dir, page_dir)
            run_roi_routing(services, item, page_dir)
            all_roi.append(read_json(item.roi_text_path))

        seg_dir = ensure_dir(docs_dir / seg_id)
        page_predictions = parse_roi_pages(services, seg_items, seg_dir)
        assembled_pred = assemble_segment_prediction(services, input_path.stem, segment, page_predictions, seg_items)
        file_name = next(iter(next(iter(assembled_pred.values())).keys()))
        final_json = finalize_document(services, assembled_pred, seg_dir, file_name=file_name)
        if segment["doc_type"] == "waybill" and isinstance(final_json, dict) and list(final_json.keys()) == [file_name]:
            final_json = final_json[file_name]
            write_json(seg_dir / "final.json", final_json)
        final_outputs.append(
            {
                "segment_id": seg_id,
                "doc_type": segment["doc_type"],
                "final_json_path": str(seg_dir / "final.json"),
                "file_key": file_name,
                "page_ids": [item.page_id for item in seg_items],
            }
        )

    write_json(run_dir / "all_pages_roi_text.json", all_roi)

    summary = {
        "run_dir": str(run_dir),
        "page_count": len(page_items),
        "segment_count": len(segments),
        "final_outputs": final_outputs,
    }
    write_json(run_dir / "summary.json", summary)
    return summary
