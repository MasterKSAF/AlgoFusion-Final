from __future__ import annotations

from src.modules.runtime_final_json_builder import build_final_json


def test_build_final_json_wraps_invoice_payload_and_strips_private_fields() -> None:
    pred_reconciled = {
        "invoice": {
            "doc.pdf": {
                "doc": {"number": "42", "_debug": "drop"},
                "_trace": "drop",
            }
        }
    }

    assert build_final_json(pred_reconciled) == {
        "invoice": {
            "doc.pdf": {
                "doc": {"number": "42"},
            }
        }
    }


def test_build_final_json_returns_flat_waybill_payload() -> None:
    pred_reconciled = {
        "document_type": "waybill",
        "items": [{"name": "item"}],
        "_trace": "drop",
    }

    assert build_final_json(pred_reconciled, file_key="ignored.pdf") == {
        "document_type": "waybill",
        "items": [{"name": "item"}],
    }
