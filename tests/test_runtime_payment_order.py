from __future__ import annotations

from src.modules.runtime_payment_order import (
    build_payment_order_raw_fallback_from_lines,
    extract_belarus_iban,
)


def test_extract_belarus_iban_returns_direct_match() -> None:
    iban = "BY12ALFA30123456789012345678"
    assert extract_belarus_iban(f"Счет № {iban}") == iban


def test_extract_belarus_iban_rebuilds_from_digits_and_bank_code() -> None:
    assert extract_belarus_iban("BY12 3012 3456 7890 1234 5678", "ALFA") == "BY12ALFA30123456789012345678"


def test_build_payment_order_raw_fallback_from_lines_fills_missing_accounts() -> None:
    lines = [
        "Плательщик: ООО Тест",
        "Счет № BY12ALFA30123456789012345678",
        "Бенефициар: ООО Получатель",
        "Счет № BY34BETA98765432109876543210",
    ]
    current_payload = {
        "payer": {"bank_code": "ALFA", "bank_account": None},
        "payee": {"bank_code": "BETA", "bank_account": ""},
    }

    out = build_payment_order_raw_fallback_from_lines(lines, current_payload)

    assert out == {
        "payer": {"bank_account": "BY12ALFA30123456789012345678"},
        "payee": {"bank_account": "BY34BETA98765432109876543210"},
    }
