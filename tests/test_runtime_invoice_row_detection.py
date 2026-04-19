from __future__ import annotations

from src.modules.runtime_invoice_row_detection import looks_like_invoice_raw_direct_row


def test_looks_like_invoice_raw_direct_row_accepts_row_without_barcode_cell() -> None:
    text = (
        "28 | MU/PEB | Пеньюар "
        "одноразовый п/э для парикмахерских "
        "работ ESTEL M'USE (50 шт), (120°160) | 1 | упаков | "
        "14,00 | 11,67 | 20% | 2,33 | 14,00"
    )

    assert looks_like_invoice_raw_direct_row(text) is True
