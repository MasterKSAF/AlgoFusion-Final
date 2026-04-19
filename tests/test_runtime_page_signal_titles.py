from __future__ import annotations

from src.modules.runtime_page_signal_titles import (
    detect_waybill_document_type_text,
    has_invoice_header_like,
)


def test_has_invoice_header_like_detects_numbered_invoice() -> None:
    assert has_invoice_header_like("Счет № INV-30 от 01.04.2026") is True


def test_has_invoice_header_like_detects_party_header_pair() -> None:
    assert has_invoice_header_like("Продавец: ООО Тест Покупатель: ООО Клиент") is True


def test_detect_waybill_document_type_text_prefers_transport_waybill() -> None:
    assert detect_waybill_document_type_text("Товарно-транспортная накладная") == "ТОВАРНО-ТРАНСПОРТНАЯ НАКЛАДНАЯ"


def test_detect_waybill_document_type_text_detects_regular_waybill() -> None:
    assert detect_waybill_document_type_text("Товарная накладная") == "ТОВАРНАЯ НАКЛАДНАЯ"
