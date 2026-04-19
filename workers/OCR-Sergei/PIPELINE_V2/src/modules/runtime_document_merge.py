from __future__ import annotations

import copy
from typing import Any

from src.modules.runtime_postprocess import is_missing as _is_missing


def prefer_last(base: dict[str, Any], last_payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key in keys:
        if key in last_payload and not _is_missing(last_payload[key]):
            out[key] = copy.deepcopy(last_payload[key])
    return out


def count_present_fields(payload: dict[str, Any], keys: list[str]) -> int:
    return sum(0 if _is_missing(payload.get(key)) else 1 for key in keys)


def item_identity(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(item.get("line_number") or "").strip().lower(),
        str(item.get("sku") or "").strip().lower(),
        str(item.get("barcode") or "").strip().lower(),
        str(item.get("article") or "").strip().lower(),
        str(item.get("name") or "").strip().lower(),
        str(item.get("description") or "").strip().lower(),
        str(item.get("unit") or "").strip().lower(),
        str(item.get("quantity") or "").strip().lower(),
        str(item.get("price") or "").strip().lower(),
        str(item.get("free_unit_price_excl_vat") or "").strip().lower(),
        str(item.get("unit_price_excl_vat") or "").strip().lower(),
        str(item.get("cost") or "").strip().lower(),
        str(item.get("total_excl_vat") or "").strip().lower(),
        str(item.get("vat_rate") or "").strip().lower(),
        str(item.get("vat_amount") or "").strip().lower(),
        str(item.get("cost_with_vat") or "").strip().lower(),
        str(item.get("total_incl_vat") or "").strip().lower(),
        str(item.get("extra_charge") or "").strip().lower(),
        str(item.get("note") or "").strip().lower(),
    )


def merge_items(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for payload in payloads:
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            key = item_identity(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(copy.deepcopy(item))
    return merged


def segment_header_keys(doc_type: str) -> list[str]:
    if doc_type == "waybill":
        return ["document_type", "document_series", "document_number", "date", "sender", "receiver", "payer", "basis"]
    if doc_type == "invoice":
        return ["document_type", "number", "date", "supplier", "buyer", "basis", "payment_deadline"]
    if doc_type == "account_prot":
        return ["document_number", "document_date", "supplier", "customer", "contract_basis", "document_status", "notes"]
    if doc_type == "payment_order":
        return ["document_type", "number", "date", "payer", "payee", "amount", "purpose"]
    return ["document_type", "number", "date"]


def segment_tail_keys(doc_type: str) -> list[str]:
    if doc_type == "waybill":
        return ["totals", "approvals", "footer"]
    if doc_type == "invoice":
        return ["totals", "signatory", "note", "payment_deadline"]
    if doc_type == "account_prot":
        return ["totals", "document_status", "notes"]
    return []
