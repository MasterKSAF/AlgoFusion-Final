from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.modules.runtime_account_protocol_parser import parse_account_protocol as parse_account_protocol_from_module
from src.modules.runtime_document_parser_common import (
    clean_text,
    filter_table_rows,
    group_rows,
    normalize_percent,
    row_texts as parser_row_texts,
    to_float,
    to_int,
)
from src.modules.runtime_document_parsers import detect_doc_type as detect_doc_type_from_content
from src.modules.runtime_invoice_parser import (
    clean_invoice_footer_text,
    enrich_invoice_header,
    extract_invoice_note,
    extract_invoice_numeric_totals,
    extract_invoice_signatory,
    extract_invoice_total_in_words,
    is_valid_item_row,
    merge_multiline,
    normalize_unit,
    parse_invoice as parse_invoice_from_module,
    parse_invoice_header,
    parse_line_number,
)
from src.modules.runtime_invoice_postprocess import repair_invoice_roi_payload
from src.modules.runtime_invoice_raw import build_invoice_raw_fallback_from_lines
from src.modules.runtime_io import read_json
from src.modules.runtime_payment_order_parser import parse_payment_order as parse_payment_order_from_module
from src.modules.runtime_regions import row_texts
from src.modules.runtime_regions import group_regions_by_rows as group_table_regions_by_rows
from src.modules.runtime_text_quality import _clean_inline_text
from src.modules.runtime_waybill_parser import parse_waybill as parse_waybill_from_module


def _clean_line(value: Any) -> str | None:
    cleaned = _clean_inline_text(value)
    return cleaned or None


def _append_unique_line(lines: list[str], value: Any) -> None:
    cleaned = _clean_line(value)
    if not cleaned:
        return
    if lines and lines[-1] == cleaned:
        return
    lines.append(cleaned)


def _invoice_lines_from_roi_payload(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    regions = payload.get("regions")
    if not isinstance(regions, list):
        return lines

    table_rows = group_table_regions_by_rows(regions, kind="table_cell", tol=12)
    table_lines = []
    for row in table_rows:
        row_line = " | ".join(text for text in row_texts(row) if text)
        if row_line:
            table_lines.append(row_line)

    for region in regions:
        if not isinstance(region, dict):
            continue
        if region.get("kind") == "table_cell":
            continue

        header_lines = region.get("header_lines")
        if isinstance(header_lines, list):
            for entry in header_lines:
                if isinstance(entry, dict):
                    _append_unique_line(lines, entry.get("text"))
            continue

        footer_lines = region.get("footer_lines")
        if isinstance(footer_lines, list):
            for entry in footer_lines:
                if isinstance(entry, dict):
                    _append_unique_line(lines, entry.get("text"))
            continue

        _append_unique_line(lines, region.get("text"))

    for line in table_lines:
        _append_unique_line(lines, line)
    return lines


def _load_invoice_raw_ocr_items(roi_path: Path) -> list[dict[str, Any]]:
    for candidate in (
        roi_path.with_name(roi_path.name.replace("_roi_text.json", "__ocr_raw.json")),
        roi_path.with_name(roi_path.name.replace("_roi_text.json", "_ocr_raw.json")),
    ):
        if not candidate.exists():
            continue
        raw_data = read_json(candidate)
        raw_items = raw_data.get("ocr_items") if isinstance(raw_data, dict) else None
        if isinstance(raw_items, list):
            return raw_items
    return []


def _build_invoice_items_from_table_rows(table_cells: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_rows = group_rows(table_cells, tol=14)
    rows = filter_table_rows(all_rows)

    items: list[dict[str, Any]] = []
    line_no = 1
    totals = extract_invoice_numeric_totals(all_rows)

    for row in rows:
        texts = parser_row_texts(row)
        if not is_valid_item_row(texts):
            continue

        padded = texts + [""] * (13 - len(texts))
        items.append(
            {
                "line_number": parse_line_number(padded[0], line_no),
                "article": clean_text(padded[1]),
                "description": merge_multiline(padded[2]),
                "barcode": clean_text(padded[3]),
                "quantity": to_int(padded[4]),
                "unit": normalize_unit(padded[5]),
                "unit_price_incl_vat": to_float(padded[6]),
                "amount_no_disc_incl_vat": to_float(padded[7]),
                "disc_amount": to_float(padded[8]),
                "amount_with_disc_excl_vat": to_float(padded[9]),
                "vat_rate": normalize_percent(padded[10]),
                "vat_amount": to_float(padded[11]),
                "total_with_disc_incl_vat": to_float(padded[12]),
            }
        )
        line_no += 1

    return items, totals


def _build_invoice_payload_with_legacy_helpers(roi_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    regions = payload.get("regions")
    if not isinstance(regions, list):
        raise ValueError(f"ROI payload has no regions: {roi_path}")

    header_box = next((region for region in regions if region.get("id") == "header_box"), None)
    footer_box = next((region for region in regions if region.get("id") == "footer_box"), None)
    table_cells = [region for region in regions if region.get("kind") == "table_cell"]
    raw_ocr_items = _load_invoice_raw_ocr_items(roi_path)

    header_text = clean_text(header_box.get("text")) if header_box else None
    raw_footer_text = clean_text(footer_box.get("text")) if footer_box else None
    footer_text = clean_invoice_footer_text(raw_footer_text)

    header_lines = header_box.get("header_lines") if header_box else None
    head = enrich_invoice_header(
        parse_invoice_header(header_text, header_lines, raw_ocr_items=raw_ocr_items),
        header_text,
    )
    items, totals = _build_invoice_items_from_table_rows(table_cells)
    signatory = extract_invoice_signatory(footer_text)
    note = extract_invoice_note(footer_text)
    totals["total_in_words"] = extract_invoice_total_in_words(footer_text)

    if note:
        deadline_match = re.search(r"\u0432 \u0442\u0435\u0447\u0435\u043d\u0438\u0435\s*(\d+\s*\u0434\u043d\w*)", note, flags=re.I)
        if deadline_match:
            head["payment_deadline"] = clean_text(deadline_match.group(1))

    return {
        "invoice_number": head["invoice_number"],
        "invoice_date": head["invoice_date"],
        "payment_deadline": head["payment_deadline"],
        "supplier": head["supplier"],
        "customer": head["customer"],
        "basis": head["basis"],
        "items": items,
        "totals": totals,
        "signatory": signatory,
        "note": note,
    }


def _build_invoice_payload_from_lines(payload: dict[str, Any]) -> dict[str, Any] | None:
    repaired_payload = dict(payload)
    repair_invoice_roi_payload(repaired_payload)
    lines = _invoice_lines_from_roi_payload(repaired_payload)
    return build_invoice_raw_fallback_from_lines(lines, page_role=None)


def _wrap_invoice_payload(roi_path: Path, invoice_payload: dict[str, Any]) -> dict[str, Any]:
    file_key = roi_path.name.replace("_roi_text.json", ".pdf")
    return {"invoice": {file_key: invoice_payload}}


def detect_doc_type(roi_path: Path | str) -> str | None:
    detected = detect_doc_type_from_content(Path(roi_path))
    return str(detected) if detected else None


def parse_invoice(roi_path: Path | str) -> dict[str, Any]:
    roi_path = Path(roi_path)
    try:
        payload = read_json(roi_path)
        if isinstance(payload, dict):
            invoice_payload = _build_invoice_payload_with_legacy_helpers(roi_path, payload)
            if invoice_payload:
                return _wrap_invoice_payload(roi_path, invoice_payload)
    except Exception:
        pass

    try:
        payload = read_json(roi_path)
        if isinstance(payload, dict):
            invoice_payload = _build_invoice_payload_from_lines(payload)
            if invoice_payload:
                return _wrap_invoice_payload(roi_path, invoice_payload)
    except Exception:
        pass

    return parse_invoice_from_module(roi_path)


def parse_payment_order(roi_path: Path | str) -> dict[str, Any]:
    return parse_payment_order_from_module(Path(roi_path))


def parse_waybill(roi_path: Path | str) -> dict[str, Any]:
    return parse_waybill_from_module(Path(roi_path))


def parse_account_protocol(roi_path: Path | str) -> dict[str, Any]:
    return parse_account_protocol_from_module(Path(roi_path))
