from __future__ import annotations

from src.modules.runtime_prediction_artifacts import build_prediction_artifacts
from src.modules.runtime_services import PipelineRuntimeServices


class _CleanerConfig:
    output_dpi = 240


def _make_namespaces() -> dict[str, dict]:
    return {
        "cleaner_layout": {
            "NB_CLEANER": _CleanerConfig(),
            "process_form_page": lambda *args: True,
            "process_table_page": lambda *args: True,
            "has_form_structure": lambda mask: bool(mask),
        },
        "roi_render": {
            "remove_lines": lambda clean_bgr, mask: ("nolines", clean_bgr, mask),
            "draw_rois_on_clean": lambda image, rois: {"image": image, "rois": rois},
        },
        "raw_ocr": {"raw_ocr": "stub"},
        "roi_assignment": {
            "run_roi_assignment_pipeline": lambda clean_png, roi_coords_path, raw_ocr_json_path: (
                {"ok": True},
                "<html/>",
            )
        },
        "document_parser": {
            "detect_doc_type": lambda roi_path: "invoice",
            "parse_payment_order": lambda roi_path: {"payment_order": {"doc": {"number": "1"}}},
            "parse_invoice": lambda roi_path: {"invoice": {"doc": {"number": "2"}}},
            "parse_waybill": lambda roi_path: {"document_number": "3"},
            "parse_account_protocol": lambda roi_path: {"account_prot": {"doc": {"number": "4"}}},
        },
        "prediction_normalizer": {"normalize_pred": lambda pred: {"normalized": pred}},
        "prediction_reconciler": {"build_pred_reconciled": lambda pred: {"reconciled": pred}},
        "final_json_builder": {"build_final_json": lambda pred, *, file_key: {"file_key": file_key, "payload": pred}},
    }


def test_build_prediction_artifacts_uses_services_contract() -> None:
    services = PipelineRuntimeServices.from_namespaces(_make_namespaces())

    artifacts = build_prediction_artifacts(
        services,
        {"invoice": {"doc.pdf": {"number": "1"}}},
        file_key="doc.pdf",
        outer_type="invoice",
        sanitize_final_json_payload=lambda outer_type, payload: {"outer_type": outer_type, "payload": payload},
    )

    assert artifacts.pred_norm == {"normalized": {"invoice": {"doc.pdf": {"number": "1"}}}}
    assert artifacts.pred_recon == {"reconciled": {"normalized": {"invoice": {"doc.pdf": {"number": "1"}}}}}
    assert artifacts.final_json == {
        "outer_type": "invoice",
        "payload": {
            "file_key": "doc.pdf",
            "payload": {"reconciled": {"normalized": {"invoice": {"doc.pdf": {"number": "1"}}}}},
        },
    }
