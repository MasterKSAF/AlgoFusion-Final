from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_raw_helpers import (
    _clean_inline_text,
    _detect_waybill_document_type_text,
    _extract_between_markers,
    _extract_company_name_address,
    _extract_first_numeric_token,
    _extract_first_ru_date,
    _extract_waybill_footer_totals_from_text,
    _extract_waybill_words_after_anchor,
    _group_ocr_lines,
    _group_region_lines,
    _load_roi_text_regions,
    _load_waybill_header_number,
    _looks_like_address_only,
    _normalize_waybill_document_number_or_review,
    _region_bbox_xyxy,
    _review_marker_or_none,
    _score_waybill_party_value,
    _split_person_value_pair,
    _strip_ocr_markup,
    _text_after_anchor,
    _text_before_anchor,
    _waybill_totals_incoherent,
)


def _extract_waybill_top_tax_ids_from_raw_ocr(
    ocr_items: list[dict[str, Any]] | None,
    *,
    top_y_max: int = 220,
) -> list[str]:
    candidates: list[tuple[int, int, str]] = []
    for item in ocr_items or []:
        if not isinstance(item, dict):
            continue
        bbox = item.get("bbox") or [0, 0, 0, 0]
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        try:
            x1, y1, x2, y2 = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
        except Exception:
            continue
        if min(y1, y2) > top_y_max:
            continue
        text = _clean_inline_text(item.get("text")) or ""
        if not text:
            continue
        for match in re.finditer(r"(?<!\d)(\d{9})(?!\d)", text):
            candidates.append((x1, y1, match.group(1)))

    ordered: list[str] = []
    for _x1, _y1, value in sorted(candidates, key=lambda row: (row[0], row[1], row[2])):
        if value not in ordered:
            ordered.append(value)
    return ordered


def _build_waybill_raw_fallback(item: PageWorkItem) -> dict[str, Any] | None:
    regions = _load_roi_text_regions(item)
    if not regions:
        return None

    ordered_regions = sorted(
        [region for region in regions if _strip_ocr_markup(region.get("text"))],
        key=lambda region: (_region_bbox_xyxy(region)[1], _region_bbox_xyxy(region)[0]),
    )
    if not ordered_regions:
        return None

    page_text = "\n".join(_strip_ocr_markup(region.get("text")) for region in ordered_regions)
    raw_full_text = _clean_inline_text(item.full_text) or page_text
    if not re.search(r"накладн", page_text, flags=re.I):
        return None

    line_rows = _group_region_lines(
        ordered_regions,
        kinds={"form_roi", "header_form_roi", "unp_cell", "footer_box"},
        y_tol=12,
    )
    line_texts = [_clean_inline_text(row.get("text")) or "" for row in line_rows if _clean_inline_text(row.get("text"))]

    table_y1_min = min(
        (_region_bbox_xyxy(region)[1] for region in ordered_regions if region.get("kind") == "table_cell"),
        default=10_000,
    )
    header_limit = table_y1_min - 16 if table_y1_min < 10_000 else 650
    raw_header_rows = [row for row in _group_ocr_lines(item.ocr_items, y_tol=10) if float(row.get("yc", 0.0)) <= header_limit]
    raw_header_lines = [_clean_inline_text(row.get("text")) or "" for row in raw_header_rows if _clean_inline_text(row.get("text"))]

    top_regions = [region for region in ordered_regions if _region_bbox_xyxy(region)[1] <= 220]
    top_tax = []
    for region in sorted(top_regions, key=lambda region: _region_bbox_xyxy(region)[0]):
        text = _strip_ocr_markup(region.get("text"))
        match = re.search(r"(?<!\d)(\d{9})(?!\d)", text)
        if match:
            top_tax.append(match.group(1))

    raw_top_tax = _extract_waybill_top_tax_ids_from_raw_ocr(item.ocr_items, top_y_max=220)
    if len(raw_top_tax) > len(top_tax) or (len(top_tax) < 2 and len(raw_top_tax) >= 2):
        top_tax = raw_top_tax

    sender_tax = top_tax[0] if len(top_tax) >= 1 else None
    receiver_tax = top_tax[1] if len(top_tax) >= 2 else None
    payer_tax = top_tax[2] if len(top_tax) >= 3 else None

    document_type = _detect_waybill_document_type_text(page_text)
    header_line = next((line for line in raw_header_lines if re.search(r"товарн\w+\s+накладн", line, flags=re.I)), "")
    if not header_line:
        header_line = next((line for line in line_texts if re.search(r"товарн\w+\s+накладн", line, flags=re.I)), "")
    series_line = next((line for line in raw_header_lines if re.search(r"\bСерия\b", line, flags=re.I)), "")
    if not series_line:
        series_line = next((line for line in line_texts if re.search(r"\bСерия\b", line, flags=re.I)), "")
    series_match = re.search(r"\bСерия\s+([A-ZА-Я0-9]{1,8})", series_line or page_text, flags=re.I)
    document_series = _clean_inline_text(series_match.group(1)) if series_match else None
    document_date = _extract_first_ru_date(header_line or page_text)
    document_number = _load_waybill_header_number(item)
    number_match = re.search(r"\b(?:№|N|No)\s*([0-9]{5,})", header_line or page_text)
    if number_match:
        candidate = _normalize_waybill_document_number_or_review(number_match.group(1))
        if candidate:
            document_number = candidate

    sender_anchor_pattern = r"(?:Груз\w*отправ\w*|Гр\S{0,12}отправ\w*)"
    receiver_anchor_pattern = r"(?:Груз\w*получ\w*|Гр\S{0,12}получ\w*)"
    basis_anchor_pattern = r"(?:Осн\w*\s+\S*пуск\w*|Основание\s+отпуска)"

    direct_sender_lines = [
        line
        for line in raw_header_lines
        if re.search(sender_anchor_pattern, line, flags=re.I) and not re.search(r"Сдал\s+груз", line, flags=re.I)
    ]
    direct_receiver_lines = [
        line
        for line in raw_header_lines
        if re.search(receiver_anchor_pattern, line, flags=re.I) and not re.search(r"Принял\s+груз", line, flags=re.I)
    ]
    direct_basis_lines = [line for line in raw_header_lines if re.search(basis_anchor_pattern, line, flags=re.I)]

    payer_candidates = [
        line
        for line in line_texts
        if re.search(r"Грузоотправитель", line, flags=re.I)
        and not re.search(r"Сдал\s+грузоотправитель", line, flags=re.I)
    ]
    sender_candidates = [
        line
        for line in line_texts
        if re.search(r"Грузополучатель", line, flags=re.I)
        and not re.search(r"Принял\s+грузополучатель", line, flags=re.I)
    ]
    receiver_candidates = [line for line in line_texts if re.search(r"Пункт\s+разгрузки", line, flags=re.I)]

    payer_line = max(
        payer_candidates,
        key=lambda line: _score_waybill_party_value(_text_before_anchor(line, r"Грузоотправитель") or ""),
        default="",
    )
    sender_line = max(
        sender_candidates,
        key=lambda line: _score_waybill_party_value(_text_before_anchor(line, r"Грузополучатель") or ""),
        default="",
    )
    receiver_line = max(
        receiver_candidates,
        key=lambda line: _score_waybill_party_value(_text_before_anchor(line, r"Пункт\s+разгрузки") or ""),
        default="",
    )

    payer_chunk = _text_before_anchor(payer_line, r"Грузоотправитель") or _extract_between_markers(
        page_text,
        [r"Заказчик\s+автомобильной\s+перевозки(?:\s*\([^)]*\))?"],
        [r"Грузоотправитель", r"Грузополучатель"],
    )
    sender_chunk = (
        max(
            (_text_after_anchor(line, sender_anchor_pattern) for line in direct_sender_lines),
            key=_score_waybill_party_value,
            default=None,
        )
        or _text_before_anchor(sender_line, r"Грузополучатель")
        or _extract_between_markers(
        page_text,
        [r"Грузоотправитель(?:\s*\([^)]*\))?"],
        [r"Грузополучатель", r"Пункт\s+разгрузки", r"Основание\s+отпуска"],
    )
    )
    receiver_chunk = (
        max(
            (_text_after_anchor(line, receiver_anchor_pattern) for line in direct_receiver_lines),
            key=_score_waybill_party_value,
            default=None,
        )
        or _text_before_anchor(receiver_line, r"Пункт\s+разгрузки")
        or _extract_between_markers(
        page_text,
        [r"Грузополучатель(?:\s*\([^)]*\))?"],
        [r"Пункт\s+разгрузки", r"Основание\s+отпуска", r"Пункт\s+погрузки"],
    )
    )
    basis_row = next((line for line in direct_basis_lines if _clean_inline_text(line)), "")
    if not basis_row:
        basis_row = next((line for line in line_texts if re.search(r"Основание\s+отпуска", line, flags=re.I)), "")
    basis = _text_after_anchor(
        basis_row,
        basis_anchor_pattern,
        [r"Пункт\s+погрузки", r"Переадресовка", r"1\.\s*ТОВАРНЫЙ\s+РАЗДЕЛ"],
    ) or _extract_between_markers(
        page_text,
        [r"Основание\s+отпуска"],
        [r"Пункт\s+погрузки", r"Переадресовка", r"1\.\s*ТОВАРНЫЙ\s+РАЗДЕЛ"],
    )
    if basis:
        contract_match = re.search(r"(.+?\bот\s+[0-3]?\d[./][01]?\d[./]20\d{2})", basis, flags=re.I)
        if contract_match:
            basis = _clean_inline_text(contract_match.group(1))

    sender_name, sender_address = _extract_company_name_address(sender_chunk or "")
    receiver_name, receiver_address = _extract_company_name_address(receiver_chunk or "")
    payer_name, payer_address = _extract_company_name_address(payer_chunk or "")
    if _looks_like_address_only(receiver_chunk or ""):
        receiver_name = None
        receiver_address = _clean_inline_text(receiver_chunk)

    quantity_total = None
    cost_total = None
    vat_total = None
    cost_with_vat_total = None
    total_row = next((line for line in line_texts if re.search(r"\bитого\b", line, flags=re.I)), "")
    if total_row:
        total_numbers = [
            _extract_first_numeric_token(token)
            for token in re.findall(r"\d+[.,]\d{1,3}|\d+", total_row)
        ]
        total_numbers = [value for value in total_numbers if value is not None]
        if len(total_numbers) >= 4:
            quantity_total = total_numbers[0]
            cost_total = total_numbers[1]
            vat_total = total_numbers[2]
            cost_with_vat_total = total_numbers[3]

    raw_totals = _extract_waybill_footer_totals_from_text(raw_full_text)
    if raw_totals and (
        quantity_total is None
        or cost_total is None
        or vat_total is None
        or cost_with_vat_total is None
        or _waybill_totals_incoherent(quantity_total, cost_total, vat_total, cost_with_vat_total)
    ):
        quantity_total = raw_totals.get("quantity_total", quantity_total)
        cost_total = raw_totals.get("cost_total", cost_total)
        vat_total = raw_totals.get("vat_total", vat_total)
        cost_with_vat_total = raw_totals.get("cost_with_vat_total", cost_with_vat_total)

    vat_row = next((line for line in line_texts if re.search(r"Всего\s+сумма\s+НДС", line, flags=re.I)), "")
    total_words_row = next((line for line in line_texts if re.search(r"Всего\s+стоимость\s+с\s+НДС", line, flags=re.I)), "")
    vat_words = _text_before_anchor(vat_row, r"Всего\s+сумма\s+НДС")
    total_words = _text_before_anchor(total_words_row, r"Всего\s+стоимость\s+с\s+НДС")
    vat_words_after = _extract_waybill_words_after_anchor(
        raw_full_text,
        r"\u0412\u0441\u0435\u0433\u043e\s+\u0441\u0443\u043c\u043c\u0430\s+\u041d\u0414\u0421",
        [
            r"\(",
            r"\u0412\u0441\u0435\u0433\u043e\s+\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c\s+\u0441\s+\u041d\u0414\u0421",
            r"\u041e\u0442\u043f\u0443\u0441\u043a\s+\u0440\u0430\u0437\u0440\u0435\u0448\u0438\u043b",
        ],
    )
    total_words_after = _extract_waybill_words_after_anchor(
        raw_full_text,
        r"\u0412\u0441\u0435\u0433\u043e\s+\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c\s+\u0441\s+\u041d\u0414\u0421",
        [
            r"\(",
            r"\u041e\u0442\u043f\u0443\u0441\u043a\s+\u0440\u0430\u0437\u0440\u0435\u0448\u0438\u043b",
            r"\u0421\u0434\u0430\u043b\s+\u0433\u0440\u0443\u0437\u043e\u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u0435\u043b",
            r"\u0422\u043e\u0432\u0430\u0440\s+\u043a\s+\u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0435\s+\u043f\u0440\u0438\u043d\u044f\u043b",
        ],
    )
    if vat_words_after:
        vat_words = vat_words_after
    if total_words_after:
        total_words = total_words_after

    approvals_row = next((line for line in line_texts if re.search(r"Отпуск\s+разрешил", line, flags=re.I)), "")
    approvals_prefix = _text_before_anchor(approvals_row, r"Отпуск\s+разрешил") or ""
    released_by, accepted_for_delivery = _split_person_value_pair(approvals_prefix)
    handed_row = next((line for line in line_texts if re.search(r"Сдал\s+грузоотправитель", line, flags=re.I)), "")
    handed_by = _text_after_anchor(
        handed_row,
        r"Сдал\s+грузоотправитель",
        [r"№\s*пломбы", r"по\s+доверенности"],
    )
    if handed_by:
        handed_by = _clean_inline_text(re.sub(r"[·•]+$", "", handed_by))
    received_row = next((line for line in line_texts if re.search(r"Принял\s+грузополучатель", line, flags=re.I)), "")
    received_by = _text_after_anchor(
        received_row,
        r"Принял\s+грузополучатель",
        [r"II\.", r"С\s+товаром\s+переданы\s+документы"],
    )
    if received_by and len(received_by.split()) <= 4 and not re.search(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\.", received_by):
        received_by = _review_marker_or_none(received_by)
    docs_row = next((line for line in line_texts if re.search(r"С\s+товаром\s+переданы\s+документы", line, flags=re.I)), "")
    documents_transferred = _text_after_anchor(
        docs_row,
        r"С\s+товаром\s+переданы\s+документы:?",
        [r"УП\s+«Бумажная", r"РУП\s+«Издательство", r"Гознака", r"$"],
    )
    if documents_transferred:
        cleaned_documents = _clean_inline_text(documents_transferred) or ""
        if not re.search(r"[A-Za-z\u0410-\u044f\u0401\u04510-9]", cleaned_documents):
            documents_transferred = None
        elif re.search(r"УП\s+«Бумажная|РУП\s+«Издательство|Гознака", cleaned_documents, flags=re.I):
            documents_transferred = None

    return {
        "document_type": document_type,
        "document_series": document_series,
        "document_number": document_number,
        "date": document_date,
        "sender": {
            "name": sender_name,
            "address": sender_address,
            "tax_id": sender_tax,
        },
        "receiver": {
            "name": receiver_name,
            "address": receiver_address,
            "tax_id": receiver_tax,
        },
        "payer": {
            "name": payer_name,
            "address": payer_address,
            "tax_id": payer_tax,
        },
        "basis": basis,
        "items": [],
        "totals": {
            "quantity_total": quantity_total,
            "cost_total": cost_total,
            "vat_total": vat_total,
            "cost_with_vat_total": cost_with_vat_total,
            "vat_total_words": vat_words,
            "cost_with_vat_total_words": total_words,
        },
        "approvals": {
            "released_by": released_by,
            "handed_by": handed_by,
            "accepted_for_delivery": accepted_for_delivery,
            "received_by": received_by,
            "documents_transferred": documents_transferred,
        },
        "footer": {
            "warning": None,
        },
    }

build_waybill_raw_fallback = _build_waybill_raw_fallback
