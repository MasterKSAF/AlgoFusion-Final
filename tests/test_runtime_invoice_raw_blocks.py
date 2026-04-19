from __future__ import annotations

from src.modules.runtime_invoice_raw_blocks import collect_invoice_raw_item_blocks


def test_collect_invoice_raw_item_blocks_starts_after_table_header_and_stops_at_total() -> None:
    blocks = collect_invoice_raw_item_blocks(
        [
            "\u0421\u0447\u0435\u0442 \u2116 INV-77 \u043e\u0442 01.02.2024",
            "\u0410\u0440\u0442\u0438\u043a\u0443\u043b | \u041d\u0430\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u043d\u0438\u0435 | \u0426\u0435\u043d\u0430 | \u0421\u0443\u043c\u043c\u0430 | \u041d\u0414\u0421",
            "men.",
            "A10/16 Shampoo",
            "\u0448\u0442 | 2 | 60,00 | 100,00 | 20% | 20,00 | 120,00",
            "B20/10 Soap",
            "\u0448\u0442 | 1 | 50,00 | 50,00 | 20% | 10,00 | 60,00",
            "\u0418\u0442\u043e\u0433\u043e 150,00 30,00 180,00",
            "\u0421\u0447\u0435\u0442 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0442\u0435\u043b\u0435\u043d",
        ]
    )

    assert blocks == [
        ["A10/16 Shampoo", "\u0448\u0442 | 2 | 60,00 | 100,00 | 20% | 20,00 | 120,00"],
        ["B20/10 Soap", "\u0448\u0442 | 1 | 50,00 | 50,00 | 20% | 10,00 | 60,00"],
    ]
