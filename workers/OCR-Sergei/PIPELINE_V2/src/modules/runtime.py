from __future__ import annotations

from src.modules.runtime_account_prot import (
    looks_like_account_prot_table_header as _looks_like_account_prot_table_header,
    make_row_region as _make_row_region,
    merge_account_prot_item_row as _merge_account_prot_item_row,
    normalize_account_prot_total_row as _normalize_account_prot_total_row,
    repair_account_prot_roi_payload as _repair_account_prot_roi_payload,
    repair_shifted_account_prot_item as _repair_shifted_account_prot_item,
    rewrite_account_prot_row_text_from_ocr as _rewrite_account_prot_row_text_from_ocr,
    text_from_ocr_items_in_bbox as _text_from_ocr_items_in_bbox,
)
from src.modules.runtime_artifacts import (
    copy_standard_stage1_outputs as _copy_standard_stage1_outputs,
    save_standard_cleaner_output as _save_standard_cleaner_output,
)
from src.modules.runtime_common import (
    bbox_value as _bbox_value,
    bbox_xyxy as _bbox_xyxy,
    copy_if_exists as _copy_if_exists,
    doc_stem_from_page_id as _doc_stem_from_page_id,
    has_any as _has_any,
    keyword_score as _keyword_score,
    ocr_text_from_items as _ocr_text_from_items,
    page_no_from_page_id as _page_no_from_page_id,
    region_bbox_xyxy as _region_bbox_xyxy,
    set_bbox_value as _set_bbox_value,
    strip_ocr_markup as _strip_ocr_markup,
    zone_text as _zone_text,
)
from src.modules.runtime_documents import (
    assemble_segment_prediction,
    count_present_fields as _count_present_fields,
    finalize_document,
    infer_doc_type_from_name as _infer_doc_type_from_name,
    item_identity as _item_identity,
    merge_items as _merge_items,
    parse_roi_pages,
    prefer_last as _prefer_last,
    repair_roi_text_payload_for_v2 as _repair_roi_text_payload_for_v2,
    run_roi_routing,
    sanitize_final_json_payload as _sanitize_final_json_payload,
    segment_header_keys as _segment_header_keys,
    segment_tail_keys as _segment_tail_keys,
    unwrap_prediction_for_item as _unwrap_prediction_for_item,
)
from src.modules.runtime_invoice_items import (
    canonicalize_invoice_items as _canonicalize_invoice_items,
    clean_invoice_description_value as _clean_invoice_description_value,
    extract_invoice_article_token as _extract_invoice_article_token,
    extract_invoice_barcode_cell_description as _extract_invoice_barcode_cell_description,
    extract_invoice_lead_fields as _extract_invoice_lead_fields,
    extract_invoice_lead_parts as _extract_invoice_lead_parts,
    invoice_barcode_cell_idx as _invoice_barcode_cell_idx,
    invoice_item_suspicious as _invoice_item_suspicious,
    looks_like_integer_text as _looks_like_integer_text,
    looks_like_invoice_article_cell as _looks_like_invoice_article_cell,
    looks_like_invoice_qty_unit_cell as _looks_like_invoice_qty_unit_cell,
    looks_like_invoice_unit_cell as _looks_like_invoice_unit_cell,
    looks_like_money_text as _looks_like_money_text,
    looks_like_percent_text as _looks_like_percent_text,
    normalize_invoice_article_value as _normalize_invoice_article_value,
    normalize_invoice_unit_v2 as _normalize_invoice_unit_v2,
    parse_invoice_region_row as _parse_invoice_region_row,
    split_invoice_qty_unit as _split_invoice_qty_unit,
)
from src.modules.runtime_invoice_postprocess import (
    build_invoice_items_overlay as _build_invoice_items_overlay,
    build_invoice_raw_direct_rows_overlay as _build_invoice_raw_direct_rows_overlay,
    build_invoice_raw_fallback as _build_invoice_raw_fallback,
    finalize_invoice_payload_text as _finalize_invoice_payload_text,
    infer_invoice_page_vat_rate as _infer_invoice_page_vat_rate,
    invoice_unit_suspicious as _invoice_unit_suspicious,
    looks_like_invoice_raw_direct_row as _looks_like_invoice_raw_direct_row,
    repair_invoice_roi_payload as _repair_invoice_roi_payload,
    trim_invoice_note_noise as _trim_invoice_note_noise,
)
from src.modules.runtime_invoice_raw import (
    build_invoice_raw_fallback_from_lines as _build_invoice_raw_fallback_from_lines,
    looks_like_invoice_index_row as _looks_like_invoice_index_row,
    looks_like_invoice_table_header as _looks_like_invoice_table_header,
    repair_invoice_shifted_tail_item as _repair_invoice_shifted_tail_item,
)
from src.modules.runtime_io import (
    copy_file as _copy_file,
    ensure_dir as _ensure_dir,
    mkdir_clean as _mkdir_clean,
    save_png as _save_png,
    write_json as _write_json,
    write_text as _write_text,
)
from src.modules.runtime_numbers import (
    coerce_number as _coerce_number,
    extract_first_numeric_token as _extract_first_numeric_token,
    to_float_soft as _to_float_soft,
)
from src.modules.runtime_numeric_reconciliation import (
    canonical_invoice_rate_text as _canonical_invoice_rate_text,
    finalize_invoice_numeric_row as _finalize_invoice_numeric_row,
    finalize_waybill_numeric_row as _finalize_waybill_numeric_row,
    parse_percent_number as _parse_percent_number,
)
from src.modules.runtime_page_ops import (
    build_stage1_artifacts,
    run_cleaner_debug,
    run_raw_ocr_page,
)
from src.modules.runtime_page_signals import (
    _detect_waybill_document_type_text,
    _has_invoice_header_like,
    analyze_page_signals,
    analyze_page_signals_from_precomputed,
    analyze_page_signals_v3,
)
from src.modules.runtime_payment_order import (
    build_payment_order_raw_fallback_from_lines as _build_payment_order_raw_fallback_from_lines,
    extract_belarus_iban as _extract_belarus_iban,
)
from src.modules.runtime_postprocess import (
    blank_like as _blank_like,
    build_payment_order_raw_fallback as _build_payment_order_raw_fallback,
    clean_company_like_noise as _clean_company_like_noise,
    deep_fill as _deep_fill,
    is_missing as _is_missing,
    postprocess_page_prediction as _postprocess_page_prediction,
    unwrap_page_prediction as _unwrap_page_prediction,
)
from src.modules.runtime_regions import (
    group_ocr_lines as _group_ocr_lines,
    group_region_lines as _group_region_lines,
    group_regions_by_rows as _group_regions_by_rows,
    load_roi_text_regions as _load_roi_text_regions,
    row_join_text as _row_join_text,
    row_texts as _row_texts,
    row_to_pipe_text as _row_to_pipe_text,
)
from src.modules.runtime_render import (
    bgr_from_pil as _bgr_from_pil,
    pil_from_bgr as _pil_from_bgr,
    render_input_pages,
    render_pdf_pages as _render_pdf_pages,
    thin_lines_safe as _thin_lines_safe,
)
from src.modules.runtime_runs import (
    import_helper_module,
    run_job_pipeline_v2,
    run_job_pipeline_v2_from_precomputed,
    run_multipage_debug_pipeline,
    run_standard_output_pipeline as _run_standard_output_pipeline,
)
from src.modules.runtime_segmentation import (
    build_segments_v2,
    segment_doc_type as _segment_doc_type,
    select_structure_profile as _select_structure_profile,
)
from src.modules.runtime_structure import (
    apply_waybill_first_page_footer_guard as _apply_waybill_first_page_footer_guard,
    build_role_aware_structure_from_precomputed,
    build_role_aware_structure_v2,
)
from src.modules.runtime_text_quality import (
    BAD_SYMBOL_RE,
    _clean_inline_text,
    _review_marker_or_none,
    _sanitize_final_text_or_review,
)
from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_header import (
    build_waybill_header_crop_bbox as _build_waybill_header_crop_bbox,
    build_waybill_header_crop_info as _build_waybill_header_crop_info,
    count_waybill_ocr_hits as _count_waybill_ocr_hits,
    extract_waybill_number_from_crop_text as _extract_waybill_number_from_crop_text,
    is_waybill_candidate_by_layout as _is_waybill_candidate_by_layout,
    run_waybill_header_crop_ocr,
)
from src.modules.runtime_waybill_raw import (
    build_waybill_raw_fallback as _build_waybill_raw_fallback,
    build_waybill_raw_header_overlay as _build_waybill_raw_header_overlay,
    extract_between_markers as _extract_between_markers,
    extract_company_name_address as _extract_company_name_address,
    extract_first_ru_date as _extract_first_ru_date,
    has_waybill_header_anchor_noise as _has_waybill_header_anchor_noise,
    load_waybill_header_number as _load_waybill_header_number,
    looks_like_address_only as _looks_like_address_only,
    overlay_waybill_header_fallback as _overlay_waybill_header_fallback,
    score_waybill_party_value as _score_waybill_party_value,
    split_person_value_pair as _split_person_value_pair,
    strip_leading_form_label as _strip_leading_form_label,
    text_after_anchor as _text_after_anchor,
    text_before_anchor as _text_before_anchor,
    waybill_party_candidate_confident as _waybill_party_candidate_confident,
    waybill_party_payload_suspicious as _waybill_party_payload_suspicious,
)
from src.modules.runtime_waybill_text import (
    extract_waybill_unit_token as _extract_waybill_unit_token,
    finalize_waybill_payload_text as _finalize_waybill_payload_text,
    normalize_waybill_document_number as _normalize_waybill_document_number,
    normalize_waybill_document_number_or_review as _normalize_waybill_document_number_or_review,
    sanitize_money_words_or_review as _sanitize_money_words_or_review,
    sanitize_waybill_approval_or_review as _sanitize_waybill_approval_or_review,
    sanitize_waybill_approval_text as _sanitize_waybill_approval_text,
    sanitize_waybill_page_items as _sanitize_waybill_page_items,
    waybill_unit_suspicious as _waybill_unit_suspicious,
)


build_segments = build_segments_v2
build_role_aware_structure = build_role_aware_structure_v2


__all__ = [name for name in globals() if not name.startswith("__")]
