from __future__ import annotations

from src.modules.runtime_numeric_reconciliation import (
    finalize_invoice_numeric_row,
    finalize_waybill_numeric_row,
    reconcile_waybill_item_vat_rate,
)
from src.modules.runtime_text_quality import REVIEW_FIELD_MARKER


def test_reconcile_waybill_item_vat_rate_from_amounts() -> None:
    assert reconcile_waybill_item_vat_rate({"cost": 100, "vat_amount": 20, "cost_with_vat": 120}) == "20%"


def test_finalize_waybill_numeric_row_recovers_missing_vat_amount() -> None:
    row = {
        "quantity": 2,
        "price": 50,
        "cost": None,
        "vat_rate": "20 %",
        "vat_amount": None,
        "cost_with_vat": 120,
    }

    finalized = finalize_waybill_numeric_row(row)

    assert finalized["cost"] == 100
    assert finalized["vat_amount"] == 20
    assert finalized["cost_with_vat"] == 120
    assert finalized["vat_rate"] == "20%"


def test_finalize_waybill_numeric_row_marks_linked_fields_when_unreliable() -> None:
    row = {"quantity": 2, "price": 50, "cost": 103, "vat_rate": "20%", "vat_amount": 20, "cost_with_vat": 120}

    finalized = finalize_waybill_numeric_row(row)

    assert all(finalized[field] == REVIEW_FIELD_MARKER for field in ("quantity", "price", "cost", "vat_rate", "vat_amount", "cost_with_vat"))


def test_finalize_invoice_numeric_row_recovers_no_discount_amounts() -> None:
    row = {
        "quantity": 2,
        "unit_price_incl_vat": 60,
        "amount_no_disc_incl_vat": None,
        "amount_with_disc_excl_vat": None,
        "vat_rate": "20%",
        "vat_amount": None,
        "total_with_disc_incl_vat": None,
    }

    finalized = finalize_invoice_numeric_row(row)

    assert finalized["amount_no_disc_incl_vat"] == 120
    assert finalized["amount_with_disc_excl_vat"] == 100
    assert finalized["vat_amount"] == 20
    assert finalized["total_with_disc_incl_vat"] == 120


def test_finalize_invoice_numeric_row_marks_linked_fields_when_inconsistent() -> None:
    row = {
        "quantity": 2,
        "unit_price_incl_vat": 60,
        "amount_no_disc_incl_vat": 130,
        "amount_with_disc_excl_vat": 100,
        "vat_rate": "20%",
        "vat_amount": 20,
        "total_with_disc_incl_vat": 120,
    }

    finalized = finalize_invoice_numeric_row(row)

    expected_fields = (
        "quantity",
        "unit_price_incl_vat",
        "amount_no_disc_incl_vat",
        "amount_with_disc_excl_vat",
        "vat_rate",
        "vat_amount",
        "total_with_disc_incl_vat",
    )
    assert all(finalized[field] == REVIEW_FIELD_MARKER for field in expected_fields)
