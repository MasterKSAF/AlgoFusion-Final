from __future__ import annotations

import copy
import re

from src.modules.runtime_common import region_bbox_xyxy
from src.modules.runtime_io import read_json
from src.modules.runtime_regions import group_ocr_lines, load_roi_text_regions
from src.modules.runtime_text_quality import _clean_inline_text, _is_review_field_marker
from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_header import extract_waybill_number_from_crop_text
from src.modules.runtime_waybill_header_party import (
    extract_company_name_address,
    has_waybill_header_anchor_noise,
    is_missing,
    looks_like_address_only,
    score_waybill_party_value,
    waybill_party_candidate_confident,
    waybill_party_payload_suspicious,
)
from src.modules.runtime_waybill_text import normalize_waybill_document_number_or_review


def _tax_id_needs_overlay(value: Any) -> bool:
    return is_missing(value) or _is_review_field_marker(value)


def overlay_waybill_header_fallback(base: dict, raw_fallback: dict) -> dict:
    out = copy.deepcopy(base)

    for key in ["document_type", "document_series", "date"]:
        if is_missing(out.get(key)) and not is_missing(raw_fallback.get(key)):
            out[key] = copy.deepcopy(raw_fallback.get(key))

    raw_basis = _clean_inline_text(raw_fallback.get("basis"))
    cur_basis = _clean_inline_text(out.get("basis"))
    current_basis_missing_date = cur_basis and not re.search(r"[0-3]?\d[./][01]?\d[./]20\d{2}", cur_basis)
    raw_basis_has_date = raw_basis and re.search(r"[0-3]?\d[./][01]?\d[./]20\d{2}", raw_basis)
    if (
        not cur_basis
        or has_waybill_header_anchor_noise(cur_basis)
        or (current_basis_missing_date and raw_basis_has_date)
    ) and raw_basis:
        out["basis"] = raw_basis

    cur_sender = out.get("sender") if isinstance(out.get("sender"), dict) else {}
    cur_receiver = out.get("receiver") if isinstance(out.get("receiver"), dict) else {}
    raw_sender = raw_fallback.get("sender") if isinstance(raw_fallback.get("sender"), dict) else {}
    raw_receiver = raw_fallback.get("receiver") if isinstance(raw_fallback.get("receiver"), dict) else {}

    cur_sender_name = _clean_inline_text(cur_sender.get("name"))
    cur_receiver_name = _clean_inline_text(cur_receiver.get("name"))
    raw_sender_name = _clean_inline_text(raw_sender.get("name"))
    raw_receiver_name = _clean_inline_text(raw_receiver.get("name"))

    same_current_party = bool(cur_sender_name and cur_receiver_name and cur_sender_name == cur_receiver_name)
    distinct_raw_parties = bool(raw_sender_name and raw_receiver_name and raw_sender_name != raw_receiver_name)

    if same_current_party and distinct_raw_parties:
        out["sender"] = copy.deepcopy(raw_sender)
        out["receiver"] = copy.deepcopy(raw_receiver)
    else:
        if raw_sender and (is_missing(cur_sender_name) or (waybill_party_payload_suspicious(cur_sender) and not waybill_party_payload_suspicious(raw_sender))):
            out["sender"] = copy.deepcopy(raw_sender)
        if raw_receiver and (is_missing(cur_receiver_name) or (waybill_party_payload_suspicious(cur_receiver) and not waybill_party_payload_suspicious(raw_receiver))):
            out["receiver"] = copy.deepcopy(raw_receiver)

    if isinstance(raw_fallback.get("payer"), dict) and is_missing((out.get("payer") or {}).get("name")):
        out["payer"] = copy.deepcopy(raw_fallback.get("payer"))

    for party_key in ("sender", "receiver", "payer"):
        raw_party = raw_fallback.get(party_key) if isinstance(raw_fallback.get(party_key), dict) else None
        if not isinstance(raw_party, dict):
            continue
        raw_tax_id = _clean_inline_text(raw_party.get("tax_id"))
        if not raw_tax_id:
            continue
        current_party = out.get(party_key) if isinstance(out.get(party_key), dict) else None
        if not isinstance(current_party, dict):
            out[party_key] = {"tax_id": raw_tax_id}
            continue
        if _tax_id_needs_overlay(current_party.get("tax_id")):
            current_party["tax_id"] = raw_tax_id

    return out


def load_waybill_header_number(item: PageWorkItem) -> str | None:
    if not item.header_ocr_json_path or not item.header_ocr_json_path.exists():
        return None
    try:
        payload = read_json(item.header_ocr_json_path)
    except Exception:
        return None
    recomputed = extract_waybill_number_from_crop_text(
        str(payload.get("full_text") or ""),
        payload.get("ocr_items") if isinstance(payload.get("ocr_items"), list) else [],
    )
    if recomputed:
        return normalize_waybill_document_number_or_review(recomputed)
    return normalize_waybill_document_number_or_review(payload.get("header_doc_number"))


def build_waybill_raw_header_overlay(item: PageWorkItem) -> dict | None:
    if not item.ocr_items:
        return None

    table_y1_min = 10_000
    for region in load_roi_text_regions(item):
        if region.get("kind") == "table_cell":
            table_y1_min = min(table_y1_min, region_bbox_xyxy(region)[1])
    header_limit = table_y1_min - 16 if table_y1_min < 10_000 else 650
    header_rows = [row for row in group_ocr_lines(item.ocr_items, y_tol=10) if float(row.get("yc", 0.0)) <= header_limit]
    header_lines = [_clean_inline_text(row.get("text")) or "" for row in header_rows if _clean_inline_text(row.get("text"))]
    if not header_lines:
        return None

    sender_anchor = r"\u0413\u0440\u0443\u0437\u043e\u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u0435\u043b\u044c"
    receiver_anchor = r"\u0413\u0440\u0443\u0437\u043e\u043f\u043e\u043b\u0443\u0447\u0430\u0442\u0435\u043b\u044c"
    basis_anchor = r"\u041e\u0441\u043d\u043e\u0432\u0430\u043d\u0438\u0435\s+\u043e\u0442\u043f\u0443\u0441\u043a\u0430"
    stop_anchor = re.compile(
        r"|".join(
            [
                sender_anchor,
                receiver_anchor,
                basis_anchor,
                r"\u041f\u0443\u043d\u043a\u0442\s+\u043f\u043e\u0433\u0440\u0443\u0437\u043a\u0438",
                r"\u041f\u0443\u043d\u043a\u0442\s+\u0440\u0430\u0437\u0433\u0440\u0443\u0437\u043a\u0438",
                r"\u0422\u041e\u0412\u0410\u0420\u041d\u042b\u0419\s+\u0420\u0410\u0417\u0414\u0415\u041b",
            ]
        ),
        flags=re.I,
    )

    def extract_value(anchor_pattern: str, scorer) -> str | None:
        best_value = None
        best_score = -10_000
        for idx, line in enumerate(header_lines):
            match = re.search(anchor_pattern, line, flags=re.I)
            if not match:
                continue
            parts = [_clean_inline_text(line[match.end() :].lstrip(" |:;,")) or ""]
            for nxt in header_lines[idx + 1 : idx + 3]:
                if not nxt or stop_anchor.search(nxt):
                    break
                if nxt.startswith("("):
                    continue
                parts.append(nxt)
                break
            merged = _clean_inline_text(" ".join(part for part in parts if part))
            if not merged:
                continue
            score = scorer(merged)
            if score > best_score:
                best_score = score
                best_value = merged
        return best_value

    sender_chunk = extract_value(sender_anchor, score_waybill_party_value)
    receiver_chunk = extract_value(receiver_anchor, score_waybill_party_value)
    basis_chunk = extract_value(
        basis_anchor,
        lambda text: len(text) + (50 if re.search(r"\u0414\u043e\u0433\u043e\u0432\u043e\u0440", text, flags=re.I) else 0),
    )

    sender_name, sender_address = extract_company_name_address(sender_chunk or "")
    receiver_name, receiver_address = extract_company_name_address(receiver_chunk or "")
    if looks_like_address_only(receiver_chunk or ""):
        receiver_name = None
        receiver_address = _clean_inline_text(receiver_chunk)

    out: dict = {}
    if waybill_party_candidate_confident(sender_name, sender_address):
        out["sender"] = {"name": sender_name, "address": sender_address}
    if waybill_party_candidate_confident(receiver_name, receiver_address):
        out["receiver"] = {"name": receiver_name, "address": receiver_address}
    if basis_chunk:
        contract_match = re.search(r"(.+?\b\u043e\u0442\s+[0-3]?\d[./][01]?\d[./]20\d{2})", basis_chunk, flags=re.I)
        out["basis"] = _clean_inline_text(contract_match.group(1) if contract_match else basis_chunk)
    return out or None
