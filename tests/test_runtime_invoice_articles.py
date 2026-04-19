from __future__ import annotations

from src.modules.runtime_invoice_articles import (
    clean_invoice_description_value,
    extract_invoice_article_candidate,
    extract_invoice_article_token,
    extract_invoice_lead_fields,
)


def test_extract_invoice_article_token_supports_cyrillic_and_latin() -> None:
    assert extract_invoice_article_token("A 10/16") == "A10/16"
    assert extract_invoice_article_token("\u0410\u041110/16 \u0428\u0430\u043c\u043f\u0443\u043d\u044c") == "\u0410\u041110/16"


def test_extract_invoice_article_candidate_strips_embedded_line_number() -> None:
    assert extract_invoice_article_candidate("12AB12/34", line_number=12) == "AB12/34"


def test_extract_invoice_lead_fields_splits_line_article_description() -> None:
    line_number, article, description = extract_invoice_lead_fields(["7", "A10/16", "Shampoo"], 3)

    assert line_number == 7
    assert article == "A10/16"
    assert description == "Shampoo"


def test_clean_invoice_description_value_removes_leading_article() -> None:
    assert clean_invoice_description_value("A10/16 Shampoo", article="A10/16") == "Shampoo"
