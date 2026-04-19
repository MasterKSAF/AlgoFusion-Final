from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_numbers import to_float_soft
from src.modules.runtime_text_quality import _clean_inline_text


def _trim_money_words_ocr_noise(text: str | None) -> str | None:
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r"(\bкоп\.?)\s+\d{1,3}\s*[:;.]?$", r"\1", cleaned, flags=re.I)
    tail_match = re.search(r"^(.*?\bкоп\.?)(.*)$", cleaned, flags=re.I)
    if tail_match:
        head, tail = tail_match.groups()
        if tail and not re.search(r"[A-Za-zА-Яа-яЁё]", tail):
            cleaned = head
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;")
    return cleaned or None


def _looks_like_latin_garbage_word(token: str) -> bool:
    cleaned = re.sub(r"[^A-Za-z]", "", str(token or ""))
    if len(cleaned) < 3:
        return False
    return cleaned.upper() not in {"BYN", "RUB", "RUR", "KOP", "KOF", "KOPEK", "KOPEKS"}


def _looks_like_suspicious_money_words(text: str | None) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return False
    tokens = [token for token in re.split(r"[\s,;:()\"/\\]+", cleaned) if token]
    latin_words = [token for token in tokens if _looks_like_latin_garbage_word(token)]
    if latin_words:
        return True
    if re.search(r"[?\ufffd]", cleaned):
        return True
    if re.search(r"[A-Za-z]{3,}", cleaned) and not re.search(r"[А-Яа-яЁё]", cleaned):
        return True
    return False


_RU_UNITS = {
    "0_19_m": {
        0: "ноль",
        1: "один",
        2: "два",
        3: "три",
        4: "четыре",
        5: "пять",
        6: "шесть",
        7: "семь",
        8: "восемь",
        9: "девять",
        10: "десять",
        11: "одиннадцать",
        12: "двенадцать",
        13: "тринадцать",
        14: "четырнадцать",
        15: "пятнадцать",
        16: "шестнадцать",
        17: "семнадцать",
        18: "восемнадцать",
        19: "девятнадцать",
    },
    "0_19_f": {
        0: "ноль",
        1: "одна",
        2: "две",
        3: "три",
        4: "четыре",
        5: "пять",
        6: "шесть",
        7: "семь",
        8: "восемь",
        9: "девять",
        10: "десять",
        11: "одиннадцать",
        12: "двенадцать",
        13: "тринадцать",
        14: "четырнадцать",
        15: "пятнадцать",
        16: "шестнадцать",
        17: "семнадцать",
        18: "восемнадцать",
        19: "девятнадцать",
    },
    "tens": {
        20: "двадцать",
        30: "тридцать",
        40: "сорок",
        50: "пятьдесят",
        60: "шестьдесят",
        70: "семьдесят",
        80: "восемьдесят",
        90: "девяносто",
    },
    "hundreds": {
        100: "сто",
        200: "двести",
        300: "триста",
        400: "четыреста",
        500: "пятьсот",
        600: "шестьсот",
        700: "семьсот",
        800: "восемьсот",
        900: "девятьсот",
    },
}


def _choose_ru_plural(value: int, one: str, few: str, many: str) -> str:
    mod100 = value % 100
    mod10 = value % 10
    if 11 <= mod100 <= 14:
        return many
    if mod10 == 1:
        return one
    if 2 <= mod10 <= 4:
        return few
    return many


def _number_to_ru_words_under_1000(value: int, *, feminine: bool = False) -> str:
    if value == 0:
        return _RU_UNITS["0_19_f" if feminine else "0_19_m"][0]
    words: list[str] = []
    hundreds = (value // 100) * 100
    rest = value % 100
    if hundreds:
        words.append(_RU_UNITS["hundreds"][hundreds])
    if 0 < rest < 20:
        words.append(_RU_UNITS["0_19_f" if feminine else "0_19_m"][rest])
    else:
        tens = (rest // 10) * 10
        ones = rest % 10
        if tens:
            words.append(_RU_UNITS["tens"][tens])
        if ones:
            words.append(_RU_UNITS["0_19_f" if feminine else "0_19_m"][ones])
    return " ".join(words)


def _number_to_ru_words(value: int) -> str:
    if value == 0:
        return "ноль"
    if value < 0:
        return f"минус {_number_to_ru_words(abs(value))}"

    parts: list[str] = []
    millions = value // 1_000_000
    thousands = (value // 1_000) % 1_000
    rest = value % 1_000

    if millions:
        parts.append(_number_to_ru_words_under_1000(millions))
        parts.append(_choose_ru_plural(millions, "миллион", "миллиона", "миллионов"))
    if thousands:
        parts.append(_number_to_ru_words_under_1000(thousands, feminine=True))
        parts.append(_choose_ru_plural(thousands, "тысяча", "тысячи", "тысяч"))
    if rest:
        parts.append(_number_to_ru_words_under_1000(rest))
    return " ".join(part for part in parts if part).strip()


def _format_money_words_ru(amount: Any) -> str | None:
    value = to_float_soft(amount)
    if value is None or value < 0:
        return None
    rub = int(value)
    kop = int(round((value - rub) * 100))
    if kop == 100:
        rub += 1
        kop = 0
    words = _number_to_ru_words(rub)
    if not words:
        return None
    return f"{words.capitalize()} руб. {kop:02d} коп"


def _normalize_money_words_for_compare(text: Any) -> str:
    cleaned = (_clean_inline_text(text) or "").lower().replace("ё", "е")
    cleaned = re.sub(r"[.]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _money_words_need_rebuild(text: Any, amount: Any) -> bool:
    expected = _format_money_words_ru(amount)
    if not expected:
        return False
    cleaned = _trim_money_words_ocr_noise(text)
    if not cleaned:
        return True
    if _looks_like_suspicious_money_words(cleaned):
        return True
    return _normalize_money_words_for_compare(cleaned) != _normalize_money_words_for_compare(expected)
