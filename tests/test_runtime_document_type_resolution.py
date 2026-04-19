from __future__ import annotations

from src.modules.runtime_document_type_resolution import choose_resolved_doc_type, infer_doc_type_from_name


def test_infer_doc_type_from_name_detects_known_file_families() -> None:
    assert infer_doc_type_from_name("docs/Waybill_01.pdf") == "waybill"
    assert infer_doc_type_from_name("Invoice 6-19.pdf") == "invoice"
    assert infer_doc_type_from_name("account-prot.pdf") == "account_prot"
    assert infer_doc_type_from_name("payment order.pdf") == "payment_order"
    assert infer_doc_type_from_name("scan.pdf") == "unknown"


def test_choose_resolved_doc_type_prefers_matching_hard_and_detected_types() -> None:
    assert choose_resolved_doc_type(declared="invoice", hard_type="waybill", detected_type="waybill") == "waybill"


def test_choose_resolved_doc_type_keeps_declared_invoice_against_weak_invoice_hard_signal() -> None:
    assert choose_resolved_doc_type(declared="invoice", hard_type="invoice", detected_type=None) == "invoice"


def test_choose_resolved_doc_type_prefers_hard_structural_types_over_declared() -> None:
    assert choose_resolved_doc_type(declared="invoice", hard_type="payment_order", detected_type=None) == "payment_order"
    assert choose_resolved_doc_type(declared="invoice", hard_type="account_prot", detected_type=None) == "account_prot"


def test_choose_resolved_doc_type_falls_back_to_detected_then_unknown() -> None:
    assert choose_resolved_doc_type(declared="unknown", hard_type=None, detected_type="invoice") == "invoice"
    assert choose_resolved_doc_type(declared=None, hard_type=None, detected_type=None) == "unknown"
