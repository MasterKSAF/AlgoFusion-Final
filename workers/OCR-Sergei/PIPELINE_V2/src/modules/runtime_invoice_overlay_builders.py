from __future__ import annotations

import re

from src.modules.runtime_invoice_items import (
    clean_invoice_description_value as _clean_invoice_description_value,
    parse_invoice_region_row as _parse_invoice_region_row,
)
from src.modules.runtime_invoice_raw import (
    looks_like_invoice_index_row as _looks_like_invoice_index_row,
    looks_like_invoice_table_header as _looks_like_invoice_table_header,
)
from src.modules.runtime_invoice_row_detection import looks_like_invoice_raw_direct_row as _looks_like_invoice_raw_direct_row
from src.modules.runtime_regions import (
    group_ocr_lines as _group_ocr_lines,
    group_regions_by_rows as _group_regions_by_rows,
    load_roi_text_regions as _load_roi_text_regions,
    row_join_text as _row_join_text,
    row_texts as _row_texts,
    row_to_pipe_text as _row_to_pipe_text,
)
from src.modules.runtime_text_quality import _clean_inline_text
from src.modules.runtime_types import PageWorkItem


def build_invoice_items_overlay(item: PageWorkItem) -> list[dict[str, object]]:
    regions = _load_roi_text_regions(item)
    if not regions:
        return []
    rows = _group_regions_by_rows(regions, kind="table_cell", tol=12)
    header_row_idx = None
    for idx, row in enumerate(rows):
        if _looks_like_invoice_table_header(_row_join_text(row)):
            header_row_idx = idx
            break
    if header_row_idx is None:
        if item.page_role in {"middle", "last"}:
            candidate_rows = rows
        else:
            return []
    else:
        candidate_rows = rows[header_row_idx + 1 :]

    items: list[dict[str, object]] = []
    fallback_line_number = 1
    for row in candidate_rows:
        texts = _row_texts(row)
        parsed = _parse_invoice_region_row(texts, fallback_line_number=fallback_line_number)
        if parsed is None:
            joined = _row_join_text(row)
            if re.search(r"\b(?:итого|всего|счет\s+действителен)\b", joined, flags=re.I):
                break
            continue
        items.append(parsed)
        parsed_line_no = parsed.get("line_number")
        if isinstance(parsed_line_no, int):
            fallback_line_number = max(fallback_line_number + 1, parsed_line_no + 1)
        else:
            fallback_line_number += 1
    return items


def build_invoice_raw_direct_rows_overlay(item: PageWorkItem) -> list[dict[str, object]]:
    if not item.ocr_items:
        return []

    rows = _group_ocr_lines(item.ocr_items, y_tol=10)
    lines = [_row_to_pipe_text(row) for row in rows if _row_to_pipe_text(row)]
    if not lines:
        return []

    header_seen = False
    blocks: list[list[str]] = []
    current_block: list[str] = []
    stop_line_pattern = re.compile(
        r"\b(?:Итого|Всего|Счет\s+действителен|ВНИМАНИЕ|Специалист\s+по\s+работе)\b",
        flags=re.I,
    )
    for line in lines:
        if not header_seen:
            if _looks_like_invoice_table_header(line):
                header_seen = True
            continue
        if stop_line_pattern.search(line):
            if current_block:
                blocks.append(current_block)
                current_block = []
            break
        if _looks_like_invoice_index_row([part for part in re.split(r"\s*\|\s*", line) if _clean_inline_text(part)]):
            continue
        if _looks_like_invoice_raw_direct_row(line):
            if current_block:
                blocks.append(current_block)
            current_block = [line]
            continue
        if current_block:
            current_block.append(line)
    if current_block:
        blocks.append(current_block)

    items: list[dict[str, object]] = []
    fallback_line_number = 1
    for block in blocks:
        base_line = block[0]
        base_cells = [part for part in re.split(r"\s*\|\s*", base_line) if _clean_inline_text(part)]
        parsed = _parse_invoice_region_row(base_cells, fallback_line_number=fallback_line_number)
        if not parsed:
            continue
        continuation_parts = []
        for extra in block[1:]:
            cleaned = _clean_inline_text(extra.replace("|", " "))
            if not cleaned:
                continue
            if _looks_like_invoice_table_header(cleaned):
                continue
            continuation_parts.append(cleaned)
        if continuation_parts:
            merged_desc = _clean_invoice_description_value(
                " ".join(part for part in [parsed.get("description")] + continuation_parts if part),
                article=parsed.get("article"),
            )
            if merged_desc:
                parsed["description"] = merged_desc
        items.append(parsed)
        parsed_line_no = parsed.get("line_number")
        if isinstance(parsed_line_no, int):
            fallback_line_number = max(fallback_line_number + 1, parsed_line_no + 1)
        else:
            fallback_line_number += 1
    return items
