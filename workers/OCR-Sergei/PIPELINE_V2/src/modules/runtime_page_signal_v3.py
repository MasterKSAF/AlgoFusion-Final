from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.modules.runtime_common import has_any, keyword_score, zone_text
from src.modules.runtime_io import save_png, write_json
from src.modules.runtime_page_signal_blank import is_blank_page_v3
from src.modules.runtime_page_signal_doc_type import select_page_doc_type
from src.modules.runtime_page_signal_footer import has_footer_for_doc_type
from src.modules.runtime_page_signal_overlay import draw_page_signal_zones
from src.modules.runtime_page_signal_roles import infer_page_role_hint_v3
from src.modules.runtime_page_signal_titles import detect_waybill_document_type_text, has_invoice_header_like
from src.modules.runtime_services import CleanerLayoutService


def analyze_page_signals_v3(
    cleaner: CleanerLayoutService,
    page_id: str,
    page_no: int,
    clean_bgr: np.ndarray,
    mask: np.ndarray,
    ocr_payload: dict[str, Any],
    page_dir: Path,
    force_doc_type: str | None = None,
) -> dict[str, Any]:
    h, w = clean_bgr.shape[:2]
    ocr_items = ocr_payload.get("ocr_items", [])
    full_text = ocr_payload.get("text", "") or ""

    top_text = zone_text(ocr_items, 0, int(h * 0.28))
    mid_text = zone_text(ocr_items, int(h * 0.28), int(h * 0.72))
    bot_text = zone_text(ocr_items, int(h * 0.72), h)
    tail_text = zone_text(ocr_items, int(h * 0.55), h)
    all_text = " ".join(part for part in [top_text, mid_text, bot_text, full_text] if part)

    page_overlay = draw_page_signal_zones(clean_bgr)

    protocol_title = has_any(top_text, [r"счет[-\s]*протокол"])
    protocol_anywhere = has_any(all_text, [r"счет[-\s]*протокол"])
    invoice_title = has_invoice_header_like(top_text) and not protocol_title
    waybill_document_type_text = detect_waybill_document_type_text(top_text)
    waybill_title = bool(waybill_document_type_text)
    payment_title = has_any(top_text, [r"платежн\w+\s+поручен"])

    inv_score = 0
    inv_score += 4 if invoice_title else 0
    inv_score += keyword_score(top_text + " " + full_text, [r"\bпродавец\b", r"\bпокупател", r"\bоснован"])
    inv_score += 2 if has_any(all_text, [r"\bвнимание\b", r"специалист\s+по\s+работе", r"счет\s+действителен\s+в\s+течение"]) else 0
    inv_score -= 4 if protocol_anywhere else 0

    wb_score = 0
    wb_score += 6 if waybill_title else 0
    wb_score += keyword_score(top_text + " " + full_text, [r"грузоотправ", r"грузополуч", r"основание\s+отпуска"])
    wb_score += 2 if has_any(tail_text + " " + full_text, [r"отпуск\s+разрешил", r"сдал\s+грузоотправитель", r"принял\s+грузополучатель"]) else 0

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

    layout_type, layout_stats = cleaner.detect_layout_type(mask)
    table_block = cleaner.find_main_table_block(mask)
    table_top = int(table_block["y1"]) if table_block and "y1" in table_block else None
    table_top_ratio = round(table_top / h, 4) if table_top is not None and h > 0 else None

    footer_source = " ".join(part for part in [bot_text, tail_text] if part)

    has_title = bool(payment_title or waybill_title or protocol_title or invoice_title)
    has_footer = has_footer_for_doc_type(page_doc_type=page_doc_type, footer_source=footer_source, full_text=full_text)
    continuation_like = bool(table_top_ratio is not None and table_top_ratio <= 0.18 and not has_title)
    blank = is_blank_page_v3(full_text=full_text, has_title=has_title, has_footer=has_footer)

    role_hint = infer_page_role_hint_v3(
        page_doc_type=page_doc_type,
        page_no=page_no,
        layout_type=layout_type,
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
        "page_no": page_no,
        "layout_type": layout_type,
        "layout_stats": layout_stats,
        "page_doc_type": page_doc_type,
        "page_document_type_text": waybill_document_type_text,
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
    write_json(page_dir / "12_sig.json", signals)
    return signals
