from __future__ import annotations

from typing import Any

from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_header_overlay import (
    build_waybill_raw_header_overlay as _build_waybill_raw_header_overlay_impl,
    load_waybill_header_number as _load_waybill_header_number_impl,
    overlay_waybill_header_fallback as _overlay_waybill_header_fallback_impl,
)
from src.modules.runtime_waybill_header_party import (
    extract_company_name_address as _extract_company_name_address_impl,
    has_waybill_header_anchor_noise as _has_waybill_header_anchor_noise_impl,
    is_missing as _is_missing_impl,
    looks_like_address_only as _looks_like_address_only_impl,
    score_waybill_party_value as _score_waybill_party_value_impl,
    split_person_value_pair as _split_person_value_pair_impl,
    waybill_party_candidate_confident as _waybill_party_candidate_confident_impl,
    waybill_party_payload_suspicious as _waybill_party_payload_suspicious_impl,
)


def _is_missing(value: Any) -> bool:
    return _is_missing_impl(value)


def looks_like_address_only(text: str) -> bool:
    return _looks_like_address_only_impl(text)


def has_waybill_header_anchor_noise(text: str | None) -> bool:
    return _has_waybill_header_anchor_noise_impl(text)


def waybill_party_payload_suspicious(payload: Any) -> bool:
    return _waybill_party_payload_suspicious_impl(payload)


def overlay_waybill_header_fallback(base: dict[str, Any], raw_fallback: dict[str, Any]) -> dict[str, Any]:
    return _overlay_waybill_header_fallback_impl(base, raw_fallback)


def load_waybill_header_number(item: PageWorkItem) -> str | None:
    return _load_waybill_header_number_impl(item)


def score_waybill_party_value(text: str) -> int:
    return _score_waybill_party_value_impl(text)


def split_person_value_pair(text: str) -> tuple[str | None, str | None]:
    return _split_person_value_pair_impl(text)


def waybill_party_candidate_confident(name: str | None, address: str | None = None) -> bool:
    return _waybill_party_candidate_confident_impl(name, address)


def extract_company_name_address(text: str) -> tuple[str | None, str | None]:
    return _extract_company_name_address_impl(text)


def build_waybill_raw_header_overlay(item: PageWorkItem) -> dict[str, Any] | None:
    return _build_waybill_raw_header_overlay_impl(item)
