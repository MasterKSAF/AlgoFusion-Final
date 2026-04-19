from __future__ import annotations

from src.modules.runtime_text_quality import (
    REVIEW_FIELD_MARKER,
    _clean_inline_text,
    _is_review_field_marker,
    _sanitize_final_text_or_review,
)


def test_clean_inline_text_normalizes_whitespace() -> None:
    assert _clean_inline_text("  \u041e\u0434\u0438\u043d\xa0  \u0434\u0432\u0430\n\u0442\u0440\u0438  ") == (
        "\u041e\u0434\u0438\u043d \u0434\u0432\u0430 \u0442\u0440\u0438"
    )


def test_sanitize_final_text_or_review_marks_unreliable_text() -> None:
    assert _sanitize_final_text_or_review("\u0421\u0443\u043c\u043c\u0430 NOT TROUBLETEN STOKE", strict_text=True) == REVIEW_FIELD_MARKER


def test_sanitize_final_text_or_review_keeps_allowed_product_latin() -> None:
    text = "\u0428\u0430\u043c\u043f\u0443\u043d\u044c ESTEL ALPHA MARINE PRO 1000 \u043c\u043b"

    assert _sanitize_final_text_or_review(text, item_text=True) == text


def test_sanitize_final_text_or_review_keeps_mixed_invoice_description() -> None:
    text = (
        'Macka "Vita-\u0442\u0435\u0440\u0430\u043f\u0438\u044f" '
        "\u0434\u043b\u044f \u043f\u043e\u0432\u0440\u0435\u0436\u0434\u0435\u043d\u043d\u044b\u0445 "
        "\u0432\u043e\u043b\u043e\u0441 CUREX THERAPY (500 \u043c\u043b), 4606453063850, "
        "\u0441\u0442\u0440\u0430\u043d\u0430 \u0432\u0432\u043e\u0437\u0430 \u0420\u041e\u0421\u0421\u0418\u042f"
    )

    assert _sanitize_final_text_or_review(text, invoice_description=True, item_text=True) == text


def test_is_review_field_marker_matches_exact_marker() -> None:
    assert _is_review_field_marker(REVIEW_FIELD_MARKER) is True


def test_sanitize_final_text_or_review_trims_edge_noise_tokens() -> None:
    assert _sanitize_final_text_or_review("\u2022 \u041a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u0442\u0435\u043a\u0441\u0442 \u2022", strict_text=True) == (
        "\u041a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u0442\u0435\u043a\u0441\u0442"
    )
