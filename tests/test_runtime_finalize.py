from __future__ import annotations

from src.modules.runtime_document_type_resolution import infer_doc_type_from_name


def test_infer_doc_type_from_file_name() -> None:
    assert infer_doc_type_from_name("Waybill_22.pdf") == "waybill"
    assert infer_doc_type_from_name("Invoice 1.pdf") == "invoice"
    assert infer_doc_type_from_name("Account_prot_3-14.pdf") == "account_prot"
    assert infer_doc_type_from_name("payment_order_1.pdf") == "payment_order"
