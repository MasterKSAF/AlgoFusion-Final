from __future__ import annotations

from src.modules.runtime_invoice_item_quality import invoice_item_suspicious


def test_invoice_item_suspicious_accepts_clean_item() -> None:
    assert (
        invoice_item_suspicious(
            {
                "line_number": 1,
                "article": "A10/16",
                "description": "Shampoo",
                "unit": "\u0448\u0442",
                "vat_rate": "20%",
            }
        )
        is False
    )


def test_invoice_item_suspicious_rejects_invalid_vat_rate() -> None:
    assert invoice_item_suspicious({"vat_rate": "21%"}) is True


def test_invoice_item_suspicious_rejects_noisy_unit() -> None:
    assert invoice_item_suspicious({"unit": "120,00"}) is True
    assert invoice_item_suspicious({"unit": "1234567"}) is True


def test_invoice_item_suspicious_rejects_barcode_description() -> None:
    assert invoice_item_suspicious({"description": "4810123456789"}) is True
