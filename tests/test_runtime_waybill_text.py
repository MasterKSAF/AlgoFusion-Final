from __future__ import annotations

from src.modules.runtime_text_quality import REVIEW_FIELD_MARKER
from src.modules.runtime_waybill_text import (
    finalize_waybill_payload_text,
    normalize_waybill_document_number_or_review,
    sanitize_money_words_or_review,
    sanitize_waybill_approval_text,
    sanitize_waybill_page_items,
)


def test_normalize_waybill_document_number_or_review_marks_bad_number() -> None:
    assert normalize_waybill_document_number_or_review("\u2116 0513092") == "0513092"
    assert normalize_waybill_document_number_or_review("001577") == REVIEW_FIELD_MARKER


def test_sanitize_waybill_approval_text_extracts_person_tail() -> None:
    value = sanitize_waybill_approval_text(
        "\u041e\u0442\u043f\u0443\u0441\u043a \u0440\u0430\u0437\u0440\u0435\u0448\u0438\u043b "
        "\u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440 \u0418\u0432\u0430\u043d\u043e\u0432 "
        "\u0418.\u0418. \u043f\u043e \u0434\u043e\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u0438 "
        "\u2116 5",
        field_name="released_by",
    )

    assert value == "\u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440 \u0418\u0432\u0430\u043d\u043e\u0432 \u0418.\u0418"


def test_sanitize_waybill_page_items_normalizes_unit_and_line_numbers() -> None:
    rows = sanitize_waybill_page_items(
        [
            {
                "line_number": 7,
                "name": "\u0422\u043e\u0432\u0430\u0440 1",
                "quantity": 2,
                "price": 5,
                "cost": 10,
                "vat_rate": "20%",
                "vat_amount": 2,
                "cost_with_vat": 12,
                "unit": "\u0448\u0442.",
                "note": None,
            }
        ],
        page_role="single",
    )

    assert len(rows) == 1
    assert rows[0]["line_number"] == 1
    assert rows[0]["unit"] == "\u0448\u0442"
    assert rows[0]["cost_with_vat"] == 12


def test_sanitize_waybill_page_items_drops_garbage_review_row() -> None:
    rows = sanitize_waybill_page_items(
        [
            {
                "line_number": 28,
                "name": "OTOTA",
                "quantity": REVIEW_FIELD_MARKER,
                "price": REVIEW_FIELD_MARKER,
                "cost": REVIEW_FIELD_MARKER,
                "vat_rate": REVIEW_FIELD_MARKER,
                "vat_amount": REVIEW_FIELD_MARKER,
                "cost_with_vat": REVIEW_FIELD_MARKER,
                "unit": None,
                "note": None,
            }
        ],
        page_role="single",
    )

    assert rows == []


def test_finalize_waybill_payload_text_normalizes_main_fields() -> None:
    payload = finalize_waybill_payload_text(
        {
            "document_number": "\u2116 0513092",
            "basis": None,
            "sender": {
                "address": "\u0433. \u041c\u0438\u043d\u0441\u043a",
                "name": "\u041e\u041e\u041e \u0420\u043e\u043c\u0430\u0448\u043a\u0430",
                "tax_id": None,
            },
            "receiver": {
                "address": "\u0433. \u0413\u0440\u043e\u0434\u043d\u043e",
                "name": "\u041e\u041e\u041e \u0412\u0430\u0441\u0438\u043b\u0435\u043a",
                "tax_id": None,
            },
            "payer": {
                "address": "\u0433. \u0411\u0440\u0435\u0441\u0442",
                "name": "\u041e\u041e\u041e \u041f\u043b\u0430\u0442\u0435\u043b\u044c\u0449\u0438\u043a",
                "tax_id": None,
            },
            "approvals": {
                "accepted_for_delivery": "\u041f\u0435\u0442\u0440\u043e\u0432 \u041f.\u041f. W-12",
                "released_by": (
                    "\u041e\u0442\u043f\u0443\u0441\u043a \u0440\u0430\u0437\u0440\u0435\u0448\u0438\u043b "
                    "\u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440 \u0418\u0432\u0430\u043d\u043e\u0432 \u0418.\u0418."
                ),
                "handed_by": "\u0421\u0438\u0434\u043e\u0440\u043e\u0432 \u0421.\u0421.",
                "received_by": "\u041a\u043e\u0437\u043b\u043e\u0432 \u041a.\u041a.",
                "documents_transferred": "\u0422\u0422\u041d-1",
            },
            "totals": {
                "vat_total": 20,
                "cost_with_vat_total": 120,
                "vat_total_words": "\u0414\u0432\u0430\u0434\u0446\u0430\u0442\u044c \u0440\u0443\u0431\u043b\u0435\u0439 00 \u043a\u043e\u043f\u0435\u0435\u043a",
                "cost_with_vat_total_words": "\u0421\u0442\u043e \u0434\u0432\u0430\u0434\u0446\u0430\u0442\u044c \u0440\u0443\u0431\u043b\u0435\u0439 00 \u043a\u043e\u043f\u0435\u0435\u043a",
            },
            "items": [
                {
                    "line_number": 3,
                    "name": "\u0422\u043e\u0432\u0430\u0440 1",
                    "quantity": 2,
                    "price": 5,
                    "cost": 10,
                    "vat_rate": "20%",
                    "vat_amount": 2,
                    "cost_with_vat": 12,
                    "unit": "\u0448\u0442.",
                    "note": None,
                }
            ],
        },
        page_role="single",
    )

    assert payload["document_number"] == "0513092"
    assert payload["approvals"]["accepted_for_delivery"] == "\u041f\u0435\u0442\u0440\u043e\u0432 \u041f.\u041f"
    assert payload["approvals"]["released_by"] == "\u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440 \u0418\u0432\u0430\u043d\u043e\u0432 \u0418.\u0418"
    assert payload["items"][0]["line_number"] == 1
    assert payload["items"][0]["unit"] == "\u0448\u0442"


def test_sanitize_money_words_or_review_rebuilds_missing_text() -> None:
    assert sanitize_money_words_or_review(None, 142.36) == "\u0421\u0442\u043e \u0441\u043e\u0440\u043e\u043a \u0434\u0432\u0430 \u0440\u0443\u0431. 36 \u043a\u043e\u043f"
