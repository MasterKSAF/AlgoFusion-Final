from __future__ import annotations

from src.modules.runtime_page_signal_footer import has_footer_for_doc_type, has_precomputed_footer


def test_has_precomputed_footer_uses_roi_marker_first() -> None:
    assert has_precomputed_footer(has_footer_box=True, bot_text="") is True


def test_has_precomputed_footer_detects_waybill_signature_text() -> None:
    assert has_precomputed_footer(has_footer_box=False, bot_text="Принял грузополучатель Иванов") is True


def test_has_footer_for_doc_type_detects_invoice_strong_footer_in_full_text() -> None:
    assert has_footer_for_doc_type(page_doc_type="invoice", footer_source="", full_text="Всего к оплате 120.00") is True


def test_has_footer_for_doc_type_detects_account_protocol_strong_footer() -> None:
    assert has_footer_for_doc_type(page_doc_type="account_prot", footer_source="", full_text="Сумма прописью сто рублей") is True


def test_has_footer_for_doc_type_falls_back_to_unknown_patterns() -> None:
    assert has_footer_for_doc_type(page_doc_type="unknown", footer_source="Подпись ответственного лица", full_text="") is True
