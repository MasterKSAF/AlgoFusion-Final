from __future__ import annotations

from src.modules.runtime_text_quality import REVIEW_FIELD_MARKER
from src.modules.runtime_waybill_parties import (
    mark_waybill_required_header_fields,
    split_waybill_address_and_basis,
)


def test_mark_waybill_required_header_fields_marks_missing_sender_and_receiver_fields() -> None:
    payload = {
        "sender": {"name": "ООО Ромашка", "address": "г. Минск", "tax_id": None},
        "receiver": {"name": "ООО Василек", "address": None, "tax_id": None},
        "payer": {"name": "ООО Плательщик", "address": None, "tax_id": None},
    }

    mark_waybill_required_header_fields(payload)

    assert payload["sender"]["tax_id"] == REVIEW_FIELD_MARKER
    assert payload["receiver"]["address"] == REVIEW_FIELD_MARKER
    assert payload["receiver"]["tax_id"] == REVIEW_FIELD_MARKER
    assert payload["payer"]["address"] is None


def test_split_waybill_address_and_basis_extracts_basis_tail() -> None:
    address, basis = split_waybill_address_and_basis(
        "г. Минск, ул. Ленина 1 Договор № 15 от 01.02.2026",
        None,
    )

    assert address == "г. Минск, ул. Ленина 1"
    assert basis == "Договор № 15 от 01.02.2026"
