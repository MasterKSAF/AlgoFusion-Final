from __future__ import annotations

from src.modules.runtime_invoice_items import (
    extract_invoice_lead_fields,
    extract_invoice_lead_parts,
    invoice_item_suspicious,
)
from src.modules.runtime_invoice_postprocess import (
    finalize_invoice_payload_text,
    looks_like_invoice_raw_direct_row,
)
from src.modules.runtime_text_quality import REVIEW_FIELD_MARKER, _sanitize_final_text_or_review


def test_sanitize_final_text_or_review_keeps_clean_invoice_description() -> None:
    text = (
        "\u0411\u0430\u043b\u044c\u0437\u0430\u043c \u0434\u043b\u044f \u0432\u043e\u043b\u043e\u0441 "
        "\u0421\u0442\u0430\u0431\u0438\u043b\u0438\u0437\u0430\u0442\u043e\u0440 \u0446\u0432\u0435\u0442\u0430 "
        "DE LUXE"
    )

    assert _sanitize_final_text_or_review(text, invoice_description=True, item_text=True) == text


def test_finalize_invoice_payload_text_keeps_missing_signatory_as_none() -> None:
    payload = {
        "items": [],
        "totals": {
            "total_with_disc_incl_vat": 12,
            "total_in_words": "\u0414\u0432\u0435\u043d\u0430\u0434\u0446\u0430\u0442\u044c "
            "\u0440\u0443\u0431\u043b\u0435\u0439 00 \u043a\u043e\u043f\u0435\u0435\u043a",
        },
        "signatory": {"position": None, "name": ""},
    }

    finalized = finalize_invoice_payload_text(payload)

    assert finalized["signatory"]["position"] is None
    assert finalized["signatory"]["name"] is None


def test_finalize_invoice_payload_text_marks_required_counterparty_fields_for_review() -> None:
    payload = {
        "items": [],
        "supplier": {"name": "OOO Supplier", "address": None, "bank_account": "", "bic": None, "tax_id": ""},
        "customer": {"name": "OOO Customer", "address": "", "tax_id": None},
        "totals": {"total_with_disc_incl_vat": 12, "total_in_words": ""},
    }

    finalized = finalize_invoice_payload_text(payload)

    assert finalized["supplier"]["address"] == REVIEW_FIELD_MARKER
    assert finalized["supplier"]["bank_account"] == REVIEW_FIELD_MARKER
    assert finalized["supplier"]["bic"] == REVIEW_FIELD_MARKER
    assert finalized["supplier"]["tax_id"] == REVIEW_FIELD_MARKER
    assert finalized["customer"]["address"] == REVIEW_FIELD_MARKER
    assert finalized["customer"]["tax_id"] == REVIEW_FIELD_MARKER
    assert finalized["totals"]["total_in_words"] not in {None, REVIEW_FIELD_MARKER}


def test_finalize_invoice_payload_text_recovers_article_and_barcode_from_description() -> None:
    payload = {
        "items": [
            {
                "article": None,
                "barcode": "",
                "description": "AB12/34 Shampoo 4601234567890",
                "unit": "\u0448\u0442",
                "vat_rate": "20%",
            }
        ],
        "totals": {"total_with_disc_incl_vat": 12, "total_in_words": "Twelve rubles 00 kopecks"},
    }

    finalized = finalize_invoice_payload_text(payload)
    row = finalized["items"][0]

    assert row["article"] == "AB12/34"
    assert row["barcode"] == "4601234567890"
    assert row["description"] == "Shampoo 4601234567890"


def test_looks_like_invoice_raw_direct_row_accepts_row_without_barcode_cell() -> None:
    text = (
        "28 | MU/PEB | \u041f\u0435\u043d\u044c\u044e\u0430\u0440 "
        "\u043e\u0434\u043d\u043e\u0440\u0430\u0437\u043e\u0432\u044b\u0439 \u043f/\u044d "
        "\u0434\u043b\u044f \u043f\u0430\u0440\u0438\u043a\u043c\u0430\u0445\u0435\u0440\u0441\u043a\u0438\u0445 "
        "\u0440\u0430\u0431\u043e\u0442 ESTEL M'USE (50 \u0448\u0442), (120\u00b0160) | 1 | \u0443\u043f\u0430\u043a | "
        "14,00 | 11,67 | 20% | 2,33 | 14,00"
    )

    assert looks_like_invoice_raw_direct_row(text) is True


def test_invoice_item_suspicious_flags_glued_row_number_in_article() -> None:
    item = {
        "line_number": 27,
        "article": "27HC/VT",
        "description": "\u041d\u0430\u0431\u043e\u0440 Volute",
        "quantity": 27,
        "unit": "\u0448\u0442",
        "unit_price_incl_vat": None,
        "amount_no_disc_incl_vat": None,
        "vat_rate": "20%",
    }

    assert invoice_item_suspicious(item) is True


def test_extract_invoice_lead_parts_reads_trailing_line_number() -> None:
    assert extract_invoice_lead_parts("IN/BC4/U 1", 1) == (1, "IN/BC4/U")


def test_extract_invoice_lead_fields_uses_noisy_second_article_cell() -> None:
    line_number, article, description = extract_invoice_lead_fields(
        ["12", "SEN10/:6", "U/16 \u0411\u0435\u0437\u0430\u043c\u043c\u0438\u0430\u0447\u043d\u0430\u044f \u043a\u0440\u0430\u0441\u043a\u0430"],
        12,
    )

    assert line_number == 12
    assert article == "SEN10/16"
    assert description == "U/16 \u0411\u0435\u0437\u0430\u043c\u043c\u0438\u0430\u0447\u043d\u0430\u044f \u043a\u0440\u0430\u0441\u043a\u0430"
