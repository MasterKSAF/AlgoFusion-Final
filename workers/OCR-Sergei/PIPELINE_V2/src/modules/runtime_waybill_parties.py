from __future__ import annotations

import re
from typing import Any

from shared.resources.text_lexicon import WAYBILL_ADDRESS_BASIS_PATTERN, WAYBILL_ADDRESS_STOP_PATTERN
from src.modules.runtime_text_quality import REVIEW_FIELD_MARKER, _clean_inline_text


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


def mark_waybill_required_header_fields(out: dict[str, Any]) -> None:
    for party_key in ("sender", "receiver"):
        party = out.get(party_key)
        if not isinstance(party, dict):
            continue
        has_party_payload = any(not _is_missing(party.get(field)) for field in ("name", "address", "tax_id"))
        if not has_party_payload:
            continue
        for field in ("address", "tax_id"):
            if _is_missing(party.get(field)):
                party[field] = REVIEW_FIELD_MARKER


def split_waybill_address_and_basis(address: str | None, basis: str | None) -> tuple[str | None, str | None]:
    clean_address = _clean_inline_text(address)
    clean_basis = _clean_inline_text(basis)
    if not clean_address:
        return None, clean_basis

    marker_match = re.search(WAYBILL_ADDRESS_BASIS_PATTERN, clean_address, flags=re.I)
    if not marker_match:
        return clean_address, clean_basis

    address_part = _clean_inline_text(clean_address[: marker_match.start()])
    tail = _clean_inline_text(clean_address[marker_match.start() :]) or ""
    if not clean_basis:
        stop_match = re.search(
            WAYBILL_ADDRESS_STOP_PATTERN,
            tail,
            flags=re.I,
        )
        if stop_match:
            tail = _clean_inline_text(tail[: stop_match.start()]) or tail
        clean_basis = tail
    return address_part or clean_address, clean_basis
