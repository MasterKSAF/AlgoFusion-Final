from __future__ import annotations

from src.modules.runtime_page_signals import _detect_waybill_document_type_text, _has_invoice_header_like


def test_detect_waybill_document_type_text() -> None:
    assert _detect_waybill_document_type_text("Товарно-транспортная накладная") == "ТОВАРНО-ТРАНСПОРТНАЯ НАКЛАДНАЯ"
    assert _detect_waybill_document_type_text("Товарная накладная") == "ТОВАРНАЯ НАКЛАДНАЯ"


def test_has_invoice_header_like() -> None:
    assert _has_invoice_header_like("Счет № INV-30 от 01.04.2026") is True
    assert _has_invoice_header_like("Продавец: ООО Тест Покупатель: ООО Клиент") is True
