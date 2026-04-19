from __future__ import annotations

import re

from src.modules.runtime_document_parser_common import clean_text
from src.modules.runtime_account_protocol_common import (
    _account_prot_cleanup_bank_name,
    _account_prot_cleanup_company_name,
    _account_prot_extract_bic_after_label,
    _account_prot_normalize_address,
    _account_prot_trim_by_stop_words,
)
from src.modules.runtime_document_parser_common import (
    extract_bank_account,
    extract_bic,
    extract_company_names,
    extract_email,
    extract_phone,
    extract_tax_id,
    normalize_account,
)


def _account_prot_parse_supplier(block):
    out = {
        "name": None,
        "tax_id": extract_tax_id(block),
        "address": None,
        "bank_account": extract_bank_account(block),
        "bank_name": None,
        "bank_address": None,
        "bank_code": extract_bic(block) or _account_prot_extract_bic_after_label(block),
        "phone": extract_phone(block),
        "email": extract_email(block),
    }
    text = clean_text(block)
    if not text:
        return out

    party_text = clean_text(re.split(r'\bБанк:\s*', text, maxsplit=1, flags=re.I)[0]) or text
    companies = extract_company_names(party_text)
    if companies:
        out["name"] = _account_prot_cleanup_company_name(companies[0])

    address_match = re.search(r'(\d{6}.*)', party_text, flags=re.I)
    if address_match:
        out["address"] = _account_prot_normalize_address(
            _account_prot_trim_by_stop_words(
                address_match.group(1),
                (
                    r'\bр/с\b',
                    r'№\s*BY',
                    r'№\s*[A-Za-zА-Яа-я0-9]{12,}',
                    r'\bБанк:',
                    r'\bБИК\b',
                    r'\bBIC\b',
                    r'\bтел\.',
                    r'\bE-mail:',
                    r'\bУНП\b',
                    r'\bсогласования\b',
                    r'\bсчет[-\s]*протокол\b',
                    r'№\s*[A-Za-zА-Яа-я0-9\-/]+\s*от',
                ),
            )
        )

    bank_name_match = re.search(
        r'Банк:\s*(.*?)(?=\s*\d{6}|\s*БИК|\s*BIC|\s*тел\.|\s*E-mail:|\s*УНП|$)',
        text,
        flags=re.I,
    )
    if bank_name_match:
        out["bank_name"] = _account_prot_cleanup_bank_name(bank_name_match.group(1))

    bank_address_match = re.search(
        r'Банк:\s*.*?(\d{6}.*?)(?=\s*БИК|\s*BIC|\s*тел\.|\s*E-mail:|\s*УНП|$)',
        text,
        flags=re.I,
    )
    if bank_address_match:
        out["bank_address"] = _account_prot_normalize_address(bank_address_match.group(1))

    if not out["bank_code"]:
        out["bank_code"] = _account_prot_extract_bic_after_label(text)

    return out

def _account_prot_parse_customer(block):
    out = {
        "name": None,
        "tax_id": extract_tax_id(block),
        "address": None,
        "bank_account": extract_bank_account(block),
        "bank_name": None,
        "bank_address": None,
        "bank_code": extract_bic(block) or _account_prot_extract_bic_after_label(block),
        "phone": extract_phone(block),
    }
    text = clean_text(block)
    if not text:
        return out

    party_text = clean_text(re.split(r'\bБанк:\s*', text, maxsplit=1, flags=re.I)[0]) or text
    companies = extract_company_names(party_text)
    if companies:
        out["name"] = _account_prot_cleanup_company_name(companies[0])

    address_source = None
    address_match = re.search(r'адрес:\s*(.*)', party_text, flags=re.I)
    if address_match:
        address_source = address_match.group(1)
    elif out["name"] and out["name"] in party_text:
        address_source = party_text.split(out["name"], 1)[1]
        address_source = re.sub(r'^\s*(?:и\s+его\s+)?адрес:\s*', '', address_source, flags=re.I)

    if address_source:
        out["address"] = _account_prot_normalize_address(
            _account_prot_trim_by_stop_words(
                address_source,
                (
                    r'\bр/с\b',
                    r'№\s*BY',
                    r'№\s*[A-Za-zА-Яа-я0-9]{12,}',
                    r'\bБанк:',
                    r'\bБИК\b',
                    r'\bBIC\b',
                    r'\bтел\.',
                    r'\bУНП\b',
                    r'$',
                ),
            )
        )

    bank_name_match = re.search(
        r'Банк:\s*(.*?)(?=\s*\d{6}|\s*БИК|\s*BIC|\s*тел\.|\s*УНП|$)',
        text,
        flags=re.I,
    )
    if bank_name_match:
        out["bank_name"] = _account_prot_cleanup_bank_name(bank_name_match.group(1))

    bank_address_match = re.search(
        r'Банк:\s*.*?(\d{6}.*?)(?=\s*БИК|\s*BIC|\s*тел\.|\s*УНП|$)',
        text,
        flags=re.I,
    )
    if bank_address_match:
        out["bank_address"] = _account_prot_normalize_address(bank_address_match.group(1))

    if out["address"] and out["name"]:
        escaped_name = re.escape(out["name"])
        out["address"] = clean_text(re.sub(r'^' + escaped_name + r'[\s,;:]*', '', out["address"], flags=re.I))

    if not out["bank_code"]:
        out["bank_code"] = _account_prot_extract_bic_after_label(text)

    return out
