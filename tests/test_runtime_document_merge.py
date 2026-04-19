from __future__ import annotations

from src.modules.runtime_document_merge import merge_items, prefer_last, segment_header_keys, segment_tail_keys


def test_merge_items_deduplicates_by_item_identity() -> None:
    merged = merge_items(
        [
            {"items": [{"line_number": 1, "name": "Item A", "quantity": 2}]},
            {
                "items": [
                    {"line_number": 1, "name": "Item A", "quantity": 2},
                    {"line_number": 2, "name": "Item B", "quantity": 1},
                ]
            },
        ]
    )

    assert merged == [
        {"line_number": 1, "name": "Item A", "quantity": 2},
        {"line_number": 2, "name": "Item B", "quantity": 1},
    ]


def test_prefer_last_keeps_base_when_tail_value_missing() -> None:
    assert prefer_last({"totals": {"amount": 10}}, {"totals": {}}, ["totals"]) == {"totals": {"amount": 10}}
    assert prefer_last({"totals": {"amount": 10}}, {"totals": {"amount": 12}}, ["totals"]) == {"totals": {"amount": 12}}


def test_segment_key_profiles_are_document_type_specific() -> None:
    assert "sender" in segment_header_keys("waybill")
    assert "signatory" in segment_tail_keys("invoice")
    assert segment_tail_keys("payment_order") == []
