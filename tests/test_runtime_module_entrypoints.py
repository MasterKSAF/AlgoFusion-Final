from __future__ import annotations

from src.modules import runtime_cleaner_extract as cleaner_extract
from src.modules import runtime_document_parsers as document_parsers
from src.modules import runtime_final_json_builder as final_json_builder
from src.modules import runtime_prediction_reconciler as prediction_reconciler


def test_prediction_reconciler_import_is_side_effect_free() -> None:
    assert callable(prediction_reconciler.build_pred_reconciled)
    assert prediction_reconciler.build_pred_reconciled({}) == {}


def test_document_parsers_import_is_side_effect_free() -> None:
    assert callable(document_parsers.detect_doc_type)
    assert callable(document_parsers.parse_account_protocol)
    assert callable(document_parsers.parse_invoice)
    assert callable(document_parsers.parse_payment_order)
    assert callable(document_parsers.parse_waybill)


def test_cleaner_extract_import_is_side_effect_free() -> None:
    assert callable(cleaner_extract.NotebookCleanerConfig)
    assert callable(cleaner_extract.process_form_page)
    assert callable(cleaner_extract.process_table_page)


def test_final_json_builder_import_is_side_effect_free() -> None:
    assert callable(final_json_builder.build_final_json)

    payload = {"document_type": "waybill", "items": [], "_debug": {"drop": True}}
    final_json = final_json_builder.build_final_json(payload)

    assert final_json == {"document_type": "waybill", "items": []}
