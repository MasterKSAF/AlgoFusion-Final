from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_invoice_raw_blocks import collect_invoice_raw_item_blocks
from src.modules.runtime_invoice_raw_item_block import parse_invoice_raw_item_block
from src.modules.runtime_invoice_signatory import extract_invoice_signatory_from_text
from src.modules.runtime_invoice_totals import summarize_invoice_item_totals
from src.modules.runtime_numbers import coerce_number, to_float_soft
from src.modules.runtime_text_quality import _clean_inline_text


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


def build_invoice_raw_fallback_from_lines(lines: list[str], page_role: str | None = None) -> dict[str, Any] | None:
    cleaned_lines = [_clean_inline_text(line) or "" for line in lines if _clean_inline_text(line)]
    if not cleaned_lines:
        return None

    full_text = "\n".join(cleaned_lines)
    if not re.search(r"\bсчет\b(?![-\s]*протокол)", full_text, flags=re.I):
        return None

    out: dict[str, Any] = {
        "invoice_number": None,
        "invoice_date": None,
        "payment_deadline": None,
        "supplier": {
            "name": None,
            "address": None,
            "bank_account": None,
            "bank_name": None,
            "bic": None,
            "tax_id": None,
        },
        "customer": {
            "name": None,
            "address": None,
            "tax_id": None,
            "kpp": None,
            "phone": None,
        },
        "basis": None,
        "items": [],
        "totals": {
            "total_quantity": None,
            "subtotal_no_disc_incl_vat": None,
            "total_disc_amount": None,
            "subtotal_with_disc_excl_vat": None,
            "vat_amount": None,
            "total_with_disc_incl_vat": None,
            "total_in_words": None,
            "currency": "BYN",
        },
        "signatory": {
            "position": None,
            "name": None,
        },
        "note": None,
    }

    title_line = next((line for line in cleaned_lines if re.search(r"\bсчет\b.*(?:№|N|No)", line, flags=re.I)), "")
    title_match = re.search(
        r"\bсчет\b\s*(?:№|N|No)\s*([A-ZА-Я0-9./-]+).*?(?:от\s+([0-3]?\d[./][01]?\d[./]20\d{2}|[0-3]?\d\s+[А-Яа-яЁё]+\s+20\d{2}\s*г?\.?))",
        title_line,
        flags=re.I,
    )
    if title_match:
        out["invoice_number"] = _clean_inline_text(title_match.group(1))
        out["invoice_date"] = _clean_inline_text(title_match.group(2))

    deadline_match = re.search(r"счет\s+действителен\s+в\s+течение\s+([^\n.]+)", full_text, flags=re.I)
    if deadline_match:
        out["payment_deadline"] = _clean_inline_text(deadline_match.group(1))

    supplier_line = next((line for line in cleaned_lines if line.lower().startswith("продавец:")), "")
    if supplier_line:
        out["supplier"]["name"] = _clean_inline_text(supplier_line.split(":", 1)[1])

    supplier_account_line = next(
        (line for line in cleaned_lines if "УНП:" in line and ("р/сч:" in line or "код" in line) and "Покупатель" not in line),
        "",
    )
    if supplier_account_line:
        account_match = re.search(r"(BY[A-Z0-9]{10,}|ВУ[A-Z0-9]{10,})", supplier_account_line, flags=re.I)
        if account_match:
            out["supplier"]["bank_account"] = _clean_inline_text(account_match.group(1))
        tax_match = re.search(r"УНП:\s*(\d{9})", supplier_account_line, flags=re.I)
        if tax_match:
            out["supplier"]["tax_id"] = tax_match.group(1)
        bank_match = re.search(r"в\s+([^,]+)", supplier_account_line, flags=re.I)
        if bank_match:
            out["supplier"]["bank_name"] = _clean_inline_text(bank_match.group(1))
        bic_match = re.search(r"код\s+([A-Z0-9]{6,12})", supplier_account_line, flags=re.I)
        if bic_match:
            out["supplier"]["bic"] = _clean_inline_text(bic_match.group(1))

    supplier_addr_line = next((line for line in cleaned_lines if re.search(r"(юр\.\s*адрес|юрадрес)", line, flags=re.I)), "")
    if supplier_addr_line:
        parts = re.split(r"[:：]", supplier_addr_line, maxsplit=1)
        out["supplier"]["address"] = _clean_inline_text(parts[-1])

    customer_line = next((line for line in cleaned_lines if line.lower().startswith("покупатель:")), "")
    if customer_line:
        out["customer"]["name"] = _clean_inline_text(customer_line.split(":", 1)[1])

    payer_line = next((line for line in cleaned_lines if line.lower().startswith("плательщик:")), "")
    if payer_line and _is_missing(out["customer"]["name"]):
        out["customer"]["name"] = _clean_inline_text(payer_line.split(":", 1)[1])

    customer_details_line = next(
        (
            line
            for line in cleaned_lines
            if "УНП:" in line
            and "р/сч:" in line
            and "Покупатель" not in line
            and "Продавец" not in line
            and "191" not in line
        ),
        "",
    )
    if customer_details_line:
        tax_match = re.search(r"УНП:\s*(\d{9})", customer_details_line, flags=re.I)
        if tax_match:
            out["customer"]["tax_id"] = tax_match.group(1)
        kpp_values = re.findall(r"\b(\d{9})\b", customer_details_line)
        if len(kpp_values) >= 2:
            out["customer"]["kpp"] = kpp_values[-1]

    phone_match = re.search(r"(\+\d[\d()\-\s]{7,}\d|\(\d{2,4}\)\s*\d[\d\-\s]{5,}\d)", full_text)
    if phone_match:
        out["customer"]["phone"] = _clean_inline_text(phone_match.group(1))

    item_blocks = collect_invoice_raw_item_blocks(cleaned_lines)
    parsed_items: list[dict[str, Any]] = []
    for idx, block in enumerate(item_blocks, start=1):
        row = parse_invoice_raw_item_block(block, idx)
        if row:
            parsed_items.append(row)
    if parsed_items:
        out["items"] = parsed_items
        out["totals"].update(summarize_invoice_item_totals(parsed_items))

    total_line = next((line for line in cleaned_lines if re.search(r"\bитого\b|mroro", line, flags=re.I)), "")
    if total_line:
        total_values = re.findall(r"\d+[.,]\d{2}", total_line)
        if len(total_values) >= 3:
            out["totals"]["subtotal_with_disc_excl_vat"] = coerce_number(to_float_soft(total_values[0]))
            out["totals"]["vat_amount"] = coerce_number(to_float_soft(total_values[1]))
            out["totals"]["total_with_disc_incl_vat"] = coerce_number(to_float_soft(total_values[2]))

    total_words_match = re.search(r"Всего\s+к\s+оплате\s+на\s+сумму\s+с\s+НДС:\s*([^\n]+)", full_text, flags=re.I)
    if total_words_match:
        out["totals"]["total_in_words"] = _clean_inline_text(total_words_match.group(1))

    signatory_position, signatory_name = extract_invoice_signatory_from_text(full_text)
    if signatory_position:
        out["signatory"]["position"] = signatory_position
    if signatory_name:
        out["signatory"]["name"] = signatory_name

    note_parts: list[str] = []
    deadline_line = next((line for line in cleaned_lines if re.search(r"счет\s+действителен", line, flags=re.I)), "")
    if deadline_line:
        note_parts.append(deadline_line)
    if page_role in {"last", "single"} and not title_line:
        trimmed = _clean_inline_text(re.sub(r"\s+", " ", full_text))
        if trimmed:
            note_parts.append(trimmed)
    if note_parts:
        out["note"] = _clean_inline_text(" ".join(dict.fromkeys(note_parts)))

    meaningful = (
        not _is_missing(out.get("invoice_number"))
        or not _is_missing((out.get("supplier") or {}).get("name"))
        or bool(out.get("items"))
        or not _is_missing((out.get("totals") or {}).get("total_with_disc_incl_vat"))
        or not _is_missing((out.get("signatory") or {}).get("name"))
    )
    return out if meaningful else None
