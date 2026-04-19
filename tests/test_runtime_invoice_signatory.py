from __future__ import annotations

from src.modules.runtime_invoice_signatory import extract_invoice_signatory_from_text


def test_extract_invoice_signatory_from_text_reads_position_and_fio() -> None:
    position, name = extract_invoice_signatory_from_text(
        "\u0414\u0438\u0440\u0435\u043a\u0442\u043e\u0440 \u0418\u0432\u0430\u043d\u043e\u0432 \u0418.\u0418."
    )

    assert position == "\u0414\u0438\u0440\u0435\u043a\u0442\u043e\u0440"
    assert name == "\u0418\u0432\u0430\u043d\u043e\u0432 \u0418.\u0418."


def test_extract_invoice_signatory_from_text_handles_manager_phrase() -> None:
    position, name = extract_invoice_signatory_from_text(
        "\u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440 \u043f\u043e \u043f\u0440\u043e\u0434\u0430\u0436\u0430\u043c: \u041f\u0435\u0442\u0440\u043e\u0432 \u041f.\u041f."
    )

    assert position == "\u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440 \u043f\u043e \u043f\u0440\u043e\u0434\u0430\u0436\u0430\u043c"
    assert name == "\u041f\u0435\u0442\u0440\u043e\u0432 \u041f.\u041f."
