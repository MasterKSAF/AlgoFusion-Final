from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_text_quality import _clean_inline_text


LATIN_LOOKALIKE_MAP = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "С": "C",
        "Е": "E",
        "Н": "H",
        "К": "K",
        "М": "M",
        "О": "O",
        "Р": "P",
        "Т": "T",
        "У": "Y",
        "Х": "X",
        "Ј": "J",
        "а": "A",
        "в": "B",
        "с": "C",
        "е": "E",
        "н": "H",
        "к": "K",
        "м": "M",
        "о": "O",
        "р": "P",
        "т": "T",
        "у": "Y",
        "х": "X",
        "ј": "J",
    }
)


def normalize_latin_lookalikes(text: Any) -> str | None:
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return None
    normalized = cleaned.translate(LATIN_LOOKALIKE_MAP).upper()
    normalized = re.sub(r"\s+", "", normalized)
    return normalized or None


def extract_belarus_iban(text: Any, bank_code: Any = None) -> str | None:
    normalized = normalize_latin_lookalikes(text) or ""
    if not normalized:
        return None

    direct_match = re.search(r"BY\d{2}[A-Z]{4}[A-Z0-9]{20}", normalized)
    if direct_match:
        return direct_match.group(0)

    bank_prefix = None
    if bank_code:
        bank_norm = normalize_latin_lookalikes(bank_code) or ""
        bank_match = re.search(r"[A-Z]{4}", bank_norm)
        if bank_match:
            bank_prefix = bank_match.group(0)

    digits = "".join(re.findall(r"\d", normalized))
    if bank_prefix and len(digits) >= 22:
        checksum = digits[:2]
        account_tail = digits[2:22]
        if len(account_tail) == 20:
            return f"BY{checksum}{bank_prefix}{account_tail}"
    return None


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0 or all(_is_missing(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0 or all(_is_missing(item) for item in value.values())
    return False


def build_payment_order_raw_fallback_from_lines(
    lines: list[str],
    current_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cleaned_lines = [_clean_inline_text(line) or "" for line in lines if _clean_inline_text(line)]
    if not cleaned_lines:
        return None

    payee_payload = current_payload.get("payee") if isinstance(current_payload, dict) and isinstance(current_payload.get("payee"), dict) else {}
    payer_payload = current_payload.get("payer") if isinstance(current_payload, dict) and isinstance(current_payload.get("payer"), dict) else {}

    payee_bank_code = _clean_inline_text(payee_payload.get("bank_code"))
    payer_bank_code = _clean_inline_text(payer_payload.get("bank_code"))

    payer_account = None
    payee_account = None

    payer_anchor = r"^\s*Плательщик\s*:"
    payee_anchor = r"^\s*Бенефициар\s*:"
    account_anchor = r"Счет\s*(?:№|No|N)"

    for idx, line in enumerate(cleaned_lines):
        if re.search(payer_anchor, line, flags=re.I):
            for probe in cleaned_lines[idx + 1 : idx + 5]:
                if re.search(account_anchor, probe, flags=re.I):
                    payer_account = extract_belarus_iban(probe, payer_bank_code)
                    if payer_account:
                        break
        if re.search(payee_anchor, line, flags=re.I):
            for probe in cleaned_lines[idx + 1 : idx + 5]:
                if re.search(account_anchor, probe, flags=re.I):
                    payee_account = extract_belarus_iban(probe, payee_bank_code)
                    if payee_account:
                        break

    out: dict[str, Any] = {}
    if payer_account and _is_missing((payer_payload or {}).get("bank_account")):
        out["payer"] = {"bank_account": payer_account}
    if payee_account and _is_missing((payee_payload or {}).get("bank_account")):
        out["payee"] = {"bank_account": payee_account}
    return out or None
