from __future__ import annotations

from src.modules.runtime_common import (
    region_bbox_xyxy as _region_bbox_xyxy,
    strip_ocr_markup as _strip_ocr_markup,
)
from src.modules.runtime_numbers import (
    extract_first_numeric_token as _extract_first_numeric_token,
)
from src.modules.runtime_page_signals import _detect_waybill_document_type_text
from src.modules.runtime_regions import (
    group_ocr_lines as _group_ocr_lines,
    group_region_lines as _group_region_lines,
    load_roi_text_regions as _load_roi_text_regions,
)
from src.modules.runtime_text_quality import _clean_inline_text, _review_marker_or_none
from src.modules.runtime_waybill_footer_totals import (
    extract_waybill_footer_totals_from_text as _extract_waybill_footer_totals_from_text,
    normalize_waybill_total_number as _normalize_waybill_total_number,
    parse_waybill_footer_numeric_token as _parse_waybill_footer_numeric_token,
    waybill_totals_incoherent as _waybill_totals_incoherent,
)
from src.modules.runtime_waybill_header_fallback import (
    build_waybill_raw_header_overlay as _build_waybill_raw_header_overlay,
    extract_company_name_address as _extract_company_name_address,
    has_waybill_header_anchor_noise as _has_waybill_header_anchor_noise,
    load_waybill_header_number as _load_waybill_header_number,
    looks_like_address_only as _looks_like_address_only,
    overlay_waybill_header_fallback as _overlay_waybill_header_fallback,
    score_waybill_party_value as _score_waybill_party_value,
    split_person_value_pair as _split_person_value_pair,
    waybill_party_candidate_confident as _waybill_party_candidate_confident,
    waybill_party_payload_suspicious as _waybill_party_payload_suspicious,
)
from src.modules.runtime_waybill_numeric_candidates import (
    dominant_waybill_repair_unit as _dominant_waybill_repair_unit,
    normalize_waybill_raw_unit_token as _normalize_waybill_raw_unit_token,
    waybill_build_numeric_candidate as _waybill_build_numeric_candidate,
    waybill_extract_total_before_note as _waybill_extract_total_before_note,
    waybill_find_tail_unit as _waybill_find_tail_unit,
    waybill_find_tail_unit_with_end as _waybill_find_tail_unit_with_end,
    waybill_numeric_token_values as _waybill_numeric_token_values,
    waybill_parse_inline_numeric_tail as _waybill_parse_inline_numeric_tail,
    waybill_parse_numeric_candidate_from_text as _waybill_parse_numeric_candidate_from_text,
    waybill_parse_percent_text as _waybill_parse_percent_text,
)
from src.modules.runtime_waybill_raw_repair import (
    _extract_between_markers,
    _extract_first_ru_date,
    _extract_waybill_words_after_anchor,
    _is_missing,
    _strip_leading_form_label,
    _text_after_anchor,
    _text_before_anchor,
    _waybill_group_raw_line_texts,
    _waybill_leading_item_code,
    _waybill_numeric_review_count,
    _waybill_numeric_review_present,
    _waybill_trim_window_before_next_barcode,
    repair_waybill_review_items_from_raw,
    repair_waybill_review_item_names_from_raw,
)
from src.modules.runtime_waybill_review_candidates import (
    split_waybill_raw_cells as _split_waybill_raw_cells,
    waybill_review_row_candidate_from_window as _waybill_review_row_candidate_from_window,
    waybill_trim_window_to_row as _waybill_trim_window_to_row,
)
from src.modules.runtime_waybill_review_windows import (
    extract_waybill_barcode_from_name as _extract_waybill_barcode_from_name,
    waybill_find_review_row_index as _waybill_find_review_row_index,
    waybill_iter_review_row_windows as _waybill_iter_review_row_windows,
    waybill_significant_name_tokens as _waybill_significant_name_tokens,
)
from src.modules.runtime_waybill_text import (
    normalize_waybill_document_number_or_review as _normalize_waybill_document_number_or_review,
)

build_waybill_raw_header_overlay = _build_waybill_raw_header_overlay
extract_between_markers = _extract_between_markers
extract_company_name_address = _extract_company_name_address
extract_first_ru_date = _extract_first_ru_date
has_waybill_header_anchor_noise = _has_waybill_header_anchor_noise
load_waybill_header_number = _load_waybill_header_number
looks_like_address_only = _looks_like_address_only
overlay_waybill_header_fallback = _overlay_waybill_header_fallback
score_waybill_party_value = _score_waybill_party_value
split_person_value_pair = _split_person_value_pair
strip_leading_form_label = _strip_leading_form_label
text_after_anchor = _text_after_anchor
text_before_anchor = _text_before_anchor
waybill_party_candidate_confident = _waybill_party_candidate_confident
waybill_party_payload_suspicious = _waybill_party_payload_suspicious

__all__ = [
    "_is_missing",
    "_extract_between_markers",
    "_extract_first_ru_date",
    "_strip_leading_form_label",
    "_text_before_anchor",
    "_text_after_anchor",
    "_extract_waybill_words_after_anchor",
    "_normalize_waybill_total_number",
    "_parse_waybill_footer_numeric_token",
    "_extract_waybill_footer_totals_from_text",
    "_waybill_totals_incoherent",
    "_extract_waybill_barcode_from_name",
    "_waybill_significant_name_tokens",
    "_waybill_group_raw_line_texts",
    "_waybill_find_review_row_index",
    "_waybill_iter_review_row_windows",
    "_split_waybill_raw_cells",
    "_waybill_parse_percent_text",
    "_normalize_waybill_raw_unit_token",
    "_dominant_waybill_repair_unit",
    "_waybill_numeric_token_values",
    "_waybill_find_tail_unit",
    "_waybill_find_tail_unit_with_end",
    "_waybill_build_numeric_candidate",
    "_waybill_parse_numeric_candidate_from_text",
    "_waybill_extract_total_before_note",
    "_waybill_parse_inline_numeric_tail",
    "_waybill_review_row_candidate_from_window",
    "_waybill_trim_window_to_row",
    "_waybill_leading_item_code",
    "_waybill_trim_window_before_next_barcode",
    "_waybill_numeric_review_present",
    "_waybill_numeric_review_count",
    "repair_waybill_review_items_from_raw",
    "repair_waybill_review_item_names_from_raw",
    "_looks_like_address_only",
    "_has_waybill_header_anchor_noise",
    "_waybill_party_payload_suspicious",
    "_overlay_waybill_header_fallback",
    "_load_waybill_header_number",
    "_build_waybill_raw_header_overlay",
    "_score_waybill_party_value",
    "_split_person_value_pair",
    "_waybill_party_candidate_confident",
    "_extract_company_name_address",
    "_clean_inline_text",
    "_detect_waybill_document_type_text",
    "_extract_first_numeric_token",
    "_group_ocr_lines",
    "_group_region_lines",
    "_load_roi_text_regions",
    "_normalize_waybill_document_number_or_review",
    "_region_bbox_xyxy",
    "_review_marker_or_none",
    "_strip_ocr_markup",
    "build_waybill_raw_header_overlay",
    "extract_between_markers",
    "extract_company_name_address",
    "extract_first_ru_date",
    "has_waybill_header_anchor_noise",
    "load_waybill_header_number",
    "looks_like_address_only",
    "overlay_waybill_header_fallback",
    "score_waybill_party_value",
    "split_person_value_pair",
    "strip_leading_form_label",
    "text_after_anchor",
    "text_before_anchor",
    "waybill_party_candidate_confident",
    "waybill_party_payload_suspicious",
]
