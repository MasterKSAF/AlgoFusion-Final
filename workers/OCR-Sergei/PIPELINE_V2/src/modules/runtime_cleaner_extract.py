from __future__ import annotations

"""Compatibility facade for the split cleaner runtime modules."""

from src.modules.runtime_cleaner_form import (
    detect_form_closed_regions,
    detect_header_form_rois_with_outer_rebuild,
    draw_form_geometry_overlay,
    extract_form_geometry_segments,
    process_form_page,
)
from src.modules.runtime_cleaner_layout import (
    build_axis_masks,
    build_grid_mask,
    build_table_axis_masks,
    col_horizontal_support,
    count_intersections,
    detect_layout_type,
    detect_table_start_row_by_dense_verticals,
    extract_h_segments,
    extract_rows_cols_from_grid_mask,
    extract_v_segments,
    find_continuation_table_block,
    find_main_table_block,
    find_strict_table_block,
    has_form_structure,
    rebuild_grid,
    restore_missing_left_col_from_rows,
    restore_right_border_from_horizontal_ends,
    row_vertical_support,
    vertical_coverage,
)
from src.modules.runtime_cleaner_page_objects import (
    build_overlay_objects_for_form,
    build_overlay_objects_for_table,
    build_page_ocr_json,
    build_table_cells,
    clip_box_to_image,
    extend_cols_with_page_boxes,
    filter_table_rows,
    is_header_row,
    is_index_row,
    is_total_row,
    make_bbox,
    merge_close_values,
)
from src.modules.runtime_cleaner_preprocess import (
    NB_CLEANER,
    NotebookCleanerConfig,
    convert_from_path,
    nb_clean_page_bgr_exact,
    nb_detect_rotation_angle,
    nb_extract_input_dpi,
    nb_find_mask_json_for_page,
    nb_fit_to_a4_canvas,
    nb_get_a4_size,
    nb_load_input_image_with_dpi,
    nb_normalize_to_working_dpi,
    nb_preprocess_page_bgr,
    nb_preprocessing_stage_4_1,
    nb_preprocessing_stage_4_2,
    nb_preprocessing_stage_4_3,
    nb_preprocessing_stage_5_2_background,
    nb_preprocessing_stage_5_2_binary_and_denoise,
    nb_read_json_maybe_gz,
    nb_rotate_image,
    nb_rotate_image_by_angle,
)
from src.modules.runtime_cleaner_sources import (
    _render_original_from_pdf,
    _resolve_image_path_by_name,
    nb_load_worker_clean_page,
    resolve_original_image,
)
from src.modules.runtime_cleaner_stage1 import (
    binarize_for_lines,
    detect_table_lines_mask,
    draw_overlay_stage1,
    load_mask_from_json,
    prepare_binary_mask,
    process_stage1_page,
    render_pdf_to_images,
    save_cleaner_debug_png,
    save_mask_json,
    thin_lines_ximgproc,
)
from src.modules.runtime_cleaner_table_page import process_table_page
from src.modules.runtime_cleaner_unp import _cm_to_px, detect_unp_cells
from src.modules.runtime_cleaner_visuals import (
    build_form_mask_above_table,
    build_form_overlay_mask,
    detect_footer_last_text_y,
    detect_header_last_text_y,
    draw_footer_blue_box,
    draw_header_green_box,
    make_overlay,
    make_overlay_two_colors,
)


DPI = 200
