from __future__ import annotations

from src.modules.runtime_page_signal_doc_type import select_page_doc_type


def test_select_page_doc_type_prefers_forced_type() -> None:
    assert (
        select_page_doc_type(
            force_doc_type="invoice",
            payment_title=True,
            waybill_title=True,
            protocol_title=True,
            scores={"invoice": 0, "waybill": 10, "payment_order": 10, "account_prot": 10},
        )
        == "invoice"
    )


def test_select_page_doc_type_prefers_explicit_titles_before_scores() -> None:
    assert (
        select_page_doc_type(
            force_doc_type=None,
            payment_title=False,
            waybill_title=True,
            protocol_title=False,
            scores={"invoice": 50, "waybill": 1, "payment_order": 0, "account_prot": 0},
        )
        == "waybill"
    )


def test_select_page_doc_type_uses_highest_positive_score() -> None:
    assert (
        select_page_doc_type(
            force_doc_type=None,
            payment_title=False,
            waybill_title=False,
            protocol_title=False,
            scores={"invoice": 3, "waybill": 7, "payment_order": 1, "account_prot": 5},
        )
        == "waybill"
    )


def test_select_page_doc_type_returns_unknown_when_scores_are_not_positive() -> None:
    assert (
        select_page_doc_type(
            force_doc_type=None,
            payment_title=False,
            waybill_title=False,
            protocol_title=False,
            scores={"invoice": 0, "waybill": 0, "payment_order": 0, "account_prot": 0},
        )
        == "unknown"
    )
