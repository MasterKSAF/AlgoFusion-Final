from __future__ import annotations

from src.modules.runtime_page_signal_blank import is_blank_page_v3, is_precomputed_blank_page


def test_is_precomputed_blank_page_uses_compact_text_length() -> None:
    assert is_precomputed_blank_page("  a b c  ") is True
    assert is_precomputed_blank_page("Это достаточно длинный распознанный текст") is False


def test_is_blank_page_v3_requires_absent_title_and_footer() -> None:
    assert is_blank_page_v3(full_text="abc", has_title=False, has_footer=False) is True
    assert is_blank_page_v3(full_text="abc", has_title=True, has_footer=False) is False
    assert is_blank_page_v3(full_text="abc", has_title=False, has_footer=True) is False


def test_is_blank_page_v3_keeps_pages_with_enough_useful_text() -> None:
    assert is_blank_page_v3(full_text="товарная накладная строка сумма количество", has_title=False, has_footer=False) is False
