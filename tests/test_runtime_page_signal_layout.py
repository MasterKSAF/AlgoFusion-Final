from __future__ import annotations

from src.modules.runtime_page_signal_layout import analyze_precomputed_roi_layout


def test_analyze_precomputed_roi_layout_counts_table_geometry_and_markers() -> None:
    layout = analyze_precomputed_roi_layout(
        {
            "rois": [
                {"kind": "table_cell", "bbox": [0, 24, 50, 40]},
                {"kind": "table_cell", "bbox": [50, 25, 100, 40]},
                {"kind": "table_cell", "bbox": [0, 60, 50, 80]},
                {"id": "footer_box", "bbox": [0, 180, 100, 220]},
                {"id": "header_box", "bbox": [0, 0, 100, 30]},
                {"kind": "unp_cell", "bbox": [0, 30, 50, 50]},
                {"kind": "unp_cell", "bbox": [50, 30, 100, 50]},
            ]
        },
        page_height=200,
    )

    assert layout.layout_type == "table"
    assert layout.layout_stats == {"rows_n": 2, "cols_n": 2, "intersections": 4, "density": 0.75}
    assert layout.table_top_ratio == 0.12
    assert layout.has_footer_box is True
    assert layout.has_header_box is True
    assert layout.unp_cell_count == 2


def test_analyze_precomputed_roi_layout_detects_form_without_table_cells() -> None:
    layout = analyze_precomputed_roi_layout({"ocr_targets": [{"kind": "form_roi", "bbox": [0, 0, 10, 10]}]}, 100)

    assert layout.layout_type == "form"
    assert layout.layout_stats["density"] == 0.0
    assert layout.table_top_ratio is None


def test_analyze_precomputed_roi_layout_handles_missing_payload() -> None:
    layout = analyze_precomputed_roi_layout(None, 100)

    assert layout.layout_type == "unknown"
    assert layout.layout_stats == {"rows_n": 0, "cols_n": 0, "intersections": 0, "density": 0.0}
