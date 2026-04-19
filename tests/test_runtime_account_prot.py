from __future__ import annotations

from src.modules.runtime_account_prot import (
    looks_like_account_prot_table_header,
    repair_account_prot_roi_payload,
    repair_shifted_account_prot_item,
)


def test_looks_like_account_prot_table_header_detects_header() -> None:
    text = "Предмет счета | Ед. изм | Колич | Отпускн. цена | Ставка НДС | Сумма"
    assert looks_like_account_prot_table_header(text) is True


def test_repair_shifted_account_prot_item_restores_numeric_columns() -> None:
    repaired = repair_shifted_account_prot_item(
        {
            "unit": "ошибочныйтекст",
            "extra_charge": 12.5,
            "vat_rate": "20%",
            "vat_amount": 20,
            "total_incl_vat": 2.5,
            "total_excl_vat": 12.5,
        }
    )

    assert repaired["unit"] == "шт"
    assert repaired["free_unit_price_excl_vat"] == 12.5
    assert repaired["extra_charge"] is None
    assert repaired["unit_price_excl_vat"] == 12.5
    assert repaired["vat_rate"] == "20%"
    assert repaired["vat_amount"] == 2.5
    assert repaired["total_incl_vat"] == 15


def test_repair_account_prot_roi_payload_promotes_header_rows() -> None:
    payload = {
        "regions": [
            {"id": "r1", "kind": "table_cell", "bbox": [0, 0, 10, 10], "text": "Шапка"},
            {"id": "r2", "kind": "table_cell", "bbox": [20, 0, 30, 10], "text": "договора"},
            {"id": "r3", "kind": "table_cell", "bbox": [0, 20, 10, 30], "text": "Предмет счет"},
            {"id": "r4", "kind": "table_cell", "bbox": [20, 20, 30, 30], "text": "Ед. изм"},
            {"id": "r5", "kind": "table_cell", "bbox": [40, 20, 50, 30], "text": "Колич"},
            {"id": "r6", "kind": "table_cell", "bbox": [60, 20, 70, 30], "text": "Отпускн"},
            {"id": "r7", "kind": "table_cell", "bbox": [80, 20, 90, 30], "text": "Ставка НДС"},
            {"id": "r8", "kind": "table_cell", "bbox": [100, 20, 110, 30], "text": "Сумма"},
            {"id": "r9", "kind": "table_cell", "bbox": [0, 40, 10, 50], "text": "товар"},
            {"id": "r10", "kind": "table_cell", "bbox": [20, 40, 30, 50], "text": "шт"},
        ]
    }

    changed = repair_account_prot_roi_payload(payload, ocr_items=None)

    assert changed is True
    header_rows = [region for region in payload["regions"] if region.get("kind") == "header_form_roi"]
    assert len(header_rows) == 1
