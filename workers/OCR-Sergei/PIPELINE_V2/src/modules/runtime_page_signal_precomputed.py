from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.modules.runtime_common import has_any, keyword_score, ocr_text_from_items, zone_text
from src.modules.runtime_io import save_png, write_json
from src.modules.runtime_page_signal_blank import is_precomputed_blank_page
from src.modules.runtime_page_signal_doc_type import select_page_doc_type
from src.modules.runtime_page_signal_footer import has_precomputed_footer
from src.modules.runtime_page_signal_layout import analyze_precomputed_roi_layout
from src.modules.runtime_page_signal_overlay import draw_page_signal_zones
from src.modules.runtime_page_signal_roles import infer_precomputed_role_hint
from src.modules.runtime_text_quality import _clean_inline_text


def analyze_page_signals_from_precomputed(
    page_id: str,
    page_no: int,
    clean_bgr: np.ndarray,
    roi_payload: dict[str, Any],
    ocr_payload: dict[str, Any],
    page_dir: Path,
    force_doc_type: str | None = None,
) -> dict[str, Any]:
    h, w = clean_bgr.shape[:2]
    ocr_items = ocr_payload.get("ocr_items", []) if isinstance(ocr_payload, dict) else []
    full_text = ""
    if isinstance(ocr_payload, dict):
        full_text = str(ocr_payload.get("text") or "").strip()
    if not full_text:
        full_text = ocr_text_from_items(ocr_items)

    top_text = zone_text(ocr_items, 0, int(h * 0.28))
    mid_text = zone_text(ocr_items, int(h * 0.28), int(h * 0.72))
    bot_text = zone_text(ocr_items, int(h * 0.72), h)
    all_text = " ".join(part for part in [top_text, mid_text, bot_text, full_text] if part)

    page_overlay = draw_page_signal_zones(clean_bgr)

    layout = analyze_precomputed_roi_layout(roi_payload, h)
    layout_type = layout.layout_type
    layout_stats = layout.layout_stats
    table_top_ratio = layout.table_top_ratio

    protocol_title = has_any(top_text, [r"счет[-\s]*протокол"])
    protocol_anywhere = has_any(all_text, [r"счет[-\s]*протокол"])
    invoice_title = has_any(top_text, [r"\bсчет\b(?![-\s]*протокол)"])
    waybill_title = has_any(top_text, [r"товарн\w+\s+накладн"])
    payment_title = has_any(top_text, [r"платежн\w+\s+поручен"])

    inv_score = 0
    inv_score += 3 if invoice_title else 0
    inv_score += keyword_score(top_text + " " + full_text, [r"\bпоставщик\b", r"\bпокупател", r"\bоснован"])
    inv_score += 2 if has_any(all_text, [r"\bвнимание\b", r"специалист\s+по\s+работе", r"счет\s+действителен\s+в\s+течение"]) else 0
    inv_score -= 4 if protocol_anywhere else 0

    wb_score = 0
    wb_score += 6 if waybill_title else 0
    wb_score += keyword_score(top_text + " " + full_text, [r"грузоотправ", r"грузополуч", r"основание\s+отпуска"])
    wb_score += 2 if has_any(bot_text + " " + full_text, [r"отпуск\s+разрешил", r"сдал\s+грузоотправитель", r"принял\s+грузополучатель"]) else 0
    wb_score += int(layout.has_header_box)
    wb_score += int(layout.unp_cell_count >= 2)

    po_score = 0
    po_score += 8 if payment_title else 0
    po_score += keyword_score(top_text + " " + full_text, [r"банк-отправ", r"бенефициар", r"назначение\s+платеж", r"сумма\s+и\s+валюта"])

    ap_score = 0
    ap_score += 8 if protocol_title else 0
    ap_score += 5 if protocol_anywhere and not protocol_title else 0
    ap_score += keyword_score(top_text + " " + full_text, [r"\bпоставщик\b", r"\bпокупател"])
    ap_score += 2 if has_any(all_text, [r"согласования\s+свободных", r"при\s+получении\s+товара\s+необходимо", r"счет\s+действителен\s+до"]) else 0

    scores = {
        "invoice": inv_score,
        "waybill": wb_score,
        "payment_order": po_score,
        "account_prot": ap_score,
    }
    page_doc_type = select_page_doc_type(
        force_doc_type=force_doc_type,
        payment_title=payment_title,
        waybill_title=waybill_title,
        protocol_title=protocol_title,
        scores=scores,
    )

    blank = is_precomputed_blank_page(full_text)
    has_title = bool(
        re.search(r"платежн\w+\s+поручен|товарн\w+\s+накладн|счет[-\s]*протокол|\bсчет\b", top_text, flags=re.I)
    )
    has_footer = has_precomputed_footer(has_footer_box=layout.has_footer_box, bot_text=bot_text)
    continuation_like = bool(table_top_ratio is not None and table_top_ratio <= 0.18 and not has_title)

    role_hint = infer_precomputed_role_hint(
        blank=blank,
        has_title=has_title,
        has_footer=has_footer,
        continuation_like=continuation_like,
    )

    cv2.putText(
        page_overlay,
        f"{page_doc_type} | {role_hint}",
        (30, h - 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 180),
        2,
        cv2.LINE_AA,
    )
    save_png(page_dir / "12_sig.png", page_overlay)

    signals = {
        "page_id": page_id,
        "page_no": int(page_no),
        "layout_type": layout_type,
        "layout_stats": layout_stats,
        "page_doc_type": page_doc_type,
        "role_hint": role_hint,
        "blank": blank,
        "has_title": has_title,
        "has_footer": has_footer,
        "continuation_like": continuation_like,
        "table_top_ratio": table_top_ratio,
        "top_text": top_text,
        "mid_text": mid_text,
        "bot_text": bot_text,
        "full_text": full_text,
        "scores": {**scores},
    }
    title_match = re.search(r"(ТОВАРНО[-\s]*ТРАНСПОРТН\w*\s+НАКЛАДН\w*|ТОВАРН\w*\s+НАКЛАДН\w*)", top_text, flags=re.I)
    if title_match:
        signals["page_document_type_text"] = _clean_inline_text(title_match.group(1))
    write_json(page_dir / "12_sig.json", signals)
    return signals
