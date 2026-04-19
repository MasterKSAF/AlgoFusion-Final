from __future__ import annotations

import re


PRECOMPUTED_FOOTER_PATTERN = (
    r"\bитого\b|\bвсего\b|отпуск\s+разрешил|сдал\s+грузоотправитель|"
    r"принял\s+грузополучатель|внимание|действителен|подпись"
)

FOOTER_PATTERNS = {
    "invoice": (
        r"\bитого\b|\bвсего\b|всего\s+к\s+оплате|счет\s+действителен|"
        r"внимание|специалист\s+по\s+работе|директор"
    ),
    "waybill": (
        r"\bитого\b|\bвсего\b|отпуск\s+разрешил|сдал\s+грузоотправитель|"
        r"принял\s+грузополучатель|с\s+товаром\s+переданы\s+документы"
    ),
    "payment_order": (
        r"дата\s+исполнения|дата\s+поступления|штамп\s+банка|"
        r"подпись\s+исполнителя"
    ),
    "account_prot": (
        r"\bитого\b|\bвсего\b|счет\s+действителен\s+до|"
        r"при\s+получении\s+товара\s+необходимо|сумма\s+прописью"
    ),
    "unknown": r"\bитого\b|\bвсего\b|подпись|директор",
}


def has_precomputed_footer(*, has_footer_box: bool, bot_text: str) -> bool:
    return has_footer_box or bool(re.search(PRECOMPUTED_FOOTER_PATTERN, bot_text, flags=re.I))


def has_footer_for_doc_type(*, page_doc_type: str, footer_source: str, full_text: str) -> bool:
    strong_footer = False
    if page_doc_type == "invoice":
        strong_footer = bool(re.search(r"всего\s+к\s+оплате|директор", full_text, flags=re.I))
    elif page_doc_type == "account_prot":
        strong_footer = bool(re.search(r"счет\s+действителен\s+до|сумма\s+прописью", full_text, flags=re.I))

    return bool(re.search(FOOTER_PATTERNS.get(page_doc_type, FOOTER_PATTERNS["unknown"]), footer_source, flags=re.I)) or strong_footer
