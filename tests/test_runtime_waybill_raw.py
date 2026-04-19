from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.modules.runtime_postprocess import postprocess_page_prediction
from src.modules.runtime_text_common import REVIEW_FIELD_MARKER
from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_raw import build_waybill_raw_fallback
from src.modules.runtime_waybill_raw_build import _extract_waybill_top_tax_ids_from_raw_ocr


def _dummy_page_item(tmp_path: Path, *, roi_payload: dict, ocr_items: list[dict]) -> PageWorkItem:
    roi_text_path = tmp_path / "Waybill_7-15__p0001_roi_text.json"
    raw_ocr_json_path = tmp_path / "Waybill_7-15__p0001__ocr_raw.json"
    roi_text_path.write_text(json.dumps(roi_payload, ensure_ascii=False), encoding="utf-8")
    raw_ocr_json_path.write_text(json.dumps({"ocr_items": ocr_items}, ensure_ascii=False), encoding="utf-8")

    zeros = np.zeros((1, 1, 3), dtype=np.uint8)
    mask = np.zeros((1, 1), dtype=np.uint8)
    return PageWorkItem(
        page_id="Waybill_7-15__p0001",
        page_no=1,
        source_bgr=zeros,
        clean_bgr=zeros,
        no_lines_bgr=zeros,
        mask=mask,
        mask_json_path=tmp_path / "mask.json",
        raw_ocr_json_path=raw_ocr_json_path,
        roi_text_path=roi_text_path,
        full_text="",
        ocr_items=ocr_items,
        signals={},
        segment_doc_type="waybill",
        page_role="single",
    )


def test_extract_waybill_top_tax_ids_from_raw_ocr_orders_values_left_to_right() -> None:
    ocr_items = [
        {"text": "193716061", "bbox": [930, 120, 1030, 138]},
        {"text": "690667789", "bbox": [720, 121, 829, 138]},
        {"text": "30.06.2016 № 58", "bbox": [1300, 160, 1450, 178]},
    ]

    assert _extract_waybill_top_tax_ids_from_raw_ocr(ocr_items) == ["690667789", "193716061"]


def test_build_waybill_raw_fallback_uses_top_raw_ocr_tax_ids_when_regions_are_sparse(tmp_path: Path) -> None:
    roi_payload = {
        "regions": [
            {"kind": "header_form_roi", "bbox": [80, 260, 500, 290], "text": "Товарная накладная"},
            {
                "kind": "header_form_roi",
                "bbox": [80, 320, 700, 350],
                "text": 'Грузоотправитель ООО "Отправитель", г. Минск',
            },
            {
                "kind": "header_form_roi",
                "bbox": [80, 360, 740, 390],
                "text": 'Грузополучатель ООО "Получатель", г. Гродно',
            },
            {"kind": "table_cell", "bbox": [80, 700, 150, 730], "text": "Товар"},
        ]
    }
    ocr_items = [
        {"text": "1-й экз. — грузополучателю", "bbox": [160, 118, 450, 136]},
        {"text": "690667789", "bbox": [720, 121, 829, 138]},
        {"text": "193716061", "bbox": [930, 120, 1030, 138]},
        {"text": "30.06.2016 № 58", "bbox": [1300, 160, 1450, 178]},
    ]
    item = _dummy_page_item(tmp_path, roi_payload=roi_payload, ocr_items=ocr_items)

    fallback = build_waybill_raw_fallback(item)

    assert fallback is not None
    assert fallback["sender"]["tax_id"] == "690667789"
    assert fallback["receiver"]["tax_id"] == "193716061"


def test_postprocess_waybill_prediction_recovers_tax_ids_from_raw_ocr_even_when_only_tax_id_is_on_review(tmp_path: Path) -> None:
    roi_payload = {
        "regions": [
            {"kind": "header_form_roi", "bbox": [80, 260, 500, 290], "text": "Товарная накладная"},
            {
                "kind": "header_form_roi",
                "bbox": [80, 320, 700, 350],
                "text": 'Грузоотправитель ООО "Отправитель", г. Минск',
            },
            {
                "kind": "header_form_roi",
                "bbox": [80, 360, 740, 390],
                "text": 'Грузополучатель ООО "Получатель", г. Гродно',
            },
            {"kind": "table_cell", "bbox": [80, 700, 150, 730], "text": "Товар"},
        ]
    }
    ocr_items = [
        {"text": "1-й экз. — грузополучателю", "bbox": [160, 118, 450, 136]},
        {"text": "690667789", "bbox": [720, 121, 829, 138]},
        {"text": "193716061", "bbox": [930, 120, 1030, 138]},
        {"text": "30.06.2016 № 58", "bbox": [1300, 160, 1450, 178]},
    ]
    item = _dummy_page_item(tmp_path, roi_payload=roi_payload, ocr_items=ocr_items)
    payload = {
        "document_type": "ТОВАРНАЯ НАКЛАДНАЯ",
        "document_number": "0513092",
        "basis": "Договор поставки от 01.01.2024",
        "sender": {"name": 'ООО "Отправитель"', "address": "г. Минск", "tax_id": REVIEW_FIELD_MARKER},
        "receiver": {"name": 'ООО "Получатель"', "address": "г. Гродно", "tax_id": REVIEW_FIELD_MARKER},
        "payer": {"name": None, "address": None, "tax_id": None},
        "items": [],
        "totals": {
            "cost_with_vat_total": 120.0,
            "cost_with_vat_total_words": "Сто двадцать рублей 00 копеек",
            "vat_total": 20.0,
            "vat_total_words": "Двадцать рублей 00 копеек",
        },
        "approvals": {},
        "footer": {"warning": None},
    }

    _, postprocessed = postprocess_page_prediction(item, "waybill", payload)

    assert postprocessed["sender"]["tax_id"] == "690667789"
    assert postprocessed["receiver"]["tax_id"] == "193716061"
