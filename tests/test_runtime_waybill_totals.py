from __future__ import annotations

from src.modules.runtime_waybill_totals import compute_waybill_totals_from_items, fill_waybill_totals_from_safe_sources


def test_compute_waybill_totals_from_items_sums_numeric_fields() -> None:
    assert compute_waybill_totals_from_items(
        [
            {"quantity": 2, "cost": 10, "vat_amount": 2, "cost_with_vat": 12},
            {"quantity": 1, "cost": 5, "vat_amount": 1, "cost_with_vat": 6},
        ]
    ) == {
        "quantity_total": 3,
        "cost_total": 15,
        "vat_total": 3,
        "cost_with_vat_total": 18,
    }


def test_fill_waybill_totals_from_safe_sources_backfills_from_totals_and_items() -> None:
    payload = {
        "totals": {"cost_total": 15, "vat_total": 3, "cost_with_vat_total": None, "quantity_total": None},
        "items": [
            {"quantity": 2, "cost": 10, "vat_amount": 2, "cost_with_vat": 12},
            {"quantity": 1, "cost": 5, "vat_amount": 1, "cost_with_vat": 6},
        ],
    }

    fill_waybill_totals_from_safe_sources(payload)

    assert payload["totals"]["cost_with_vat_total"] == 18
    assert payload["totals"]["quantity_total"] == 3
