from __future__ import annotations

from src.modules.runtime_page_signal_roles import infer_page_role_hint_v3, infer_precomputed_role_hint


def test_infer_precomputed_role_hint_orders_basic_roles() -> None:
    assert infer_precomputed_role_hint(blank=True, has_title=True, has_footer=True, continuation_like=True) == "blank"
    assert infer_precomputed_role_hint(blank=False, has_title=True, has_footer=True, continuation_like=False) == "single_candidate"
    assert infer_precomputed_role_hint(blank=False, has_title=False, has_footer=False, continuation_like=True) == "middle_candidate"


def test_infer_page_role_hint_v3_handles_payment_orders_as_single_page() -> None:
    assert (
        infer_page_role_hint_v3(
            page_doc_type="payment_order",
            page_no=1,
            layout_type="form",
            blank=False,
            has_title=True,
            has_footer=False,
            continuation_like=False,
        )
        == "single_candidate"
    )
    assert (
        infer_page_role_hint_v3(
            page_doc_type="payment_order",
            page_no=2,
            layout_type="table",
            blank=False,
            has_title=False,
            has_footer=False,
            continuation_like=True,
        )
        == "unknown"
    )


def test_infer_page_role_hint_v3_marks_later_table_pages_as_middle_candidates() -> None:
    assert (
        infer_page_role_hint_v3(
            page_doc_type="invoice",
            page_no=2,
            layout_type="table",
            blank=False,
            has_title=False,
            has_footer=False,
            continuation_like=False,
        )
        == "middle_candidate"
    )
