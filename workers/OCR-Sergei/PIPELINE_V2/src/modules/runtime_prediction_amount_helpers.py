from __future__ import annotations

import re

VISUAL_QUOTES_REPLACEMENTS = []


def clean_spaces(s: str) -> str:
    s = str(s).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_generic_text(value):
    if value is None:
        return None

    s = clean_spaces(value)
    if not s:
        return None

    for src, dst in VISUAL_QUOTES_REPLACEMENTS:
        s = s.replace(src, dst)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r"([,.;:])(\S)", r"\1 \2", s)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:")
    return s or None


def normalize_money_words_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(r"\bкопе[йе]к\b", "копейки", s, flags=re.I)
    s = re.sub(r"(?<=\d)\s*руб\b\.?", " руб.", s, flags=re.I)
    s = re.sub(r"(?<=\d)\s*коп\b\.?", " коп.", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:")
    return s or None

def is_missing(v):
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    return False

def as_num(v):
    if is_missing(v):
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    s = re.sub(r"[^\d.\-%\-]", "", s)
    if not s:
        return None
    try:
        if s.endswith("%"):
            return float(s[:-1])
        return float(s)
    except:
        return None

def as_rate(v):
    x = as_num(v)
    if x is None:
        return None
    return x / 100.0 if x > 1 else x

def norm_num(v):
    if v is None:
        return None
    x = round(float(v), 2)
    return int(x) if x.is_integer() else x

def rubles_part(v):
    x = as_num(v)
    if x is None:
        return None
    return int(x)

def non_negative(v):
    x = as_num(v)
    return x is not None and x >= 0

def sum_item_field(items, field):
    vals = [as_num(x.get(field)) for x in items if isinstance(x, dict)]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return norm_num(sum(vals))

def safe_div(numerator, denominator):
    num = as_num(numerator)
    den = as_num(denominator)
    if num is None or den is None or abs(den) <= 1e-9:
        return None
    return num / den

def maybe_round_money(value):
    num = as_num(value)
    if num is None:
        return None
    return round(num, 2)

def parse_ru_number_words(text):
    if not text:
        return None

    units = {
        "ноль": 0,
        "один": 1, "одна": 1, "одно": 1,
        "два": 2, "две": 2,
        "три": 3,
        "четыре": 4,
        "пять": 5,
        "шесть": 6,
        "семь": 7,
        "восемь": 8,
        "девять": 9,
    }
    teens = {
        "десять": 10,
        "одиннадцать": 11,
        "двенадцать": 12,
        "тринадцать": 13,
        "четырнадцать": 14,
        "пятнадцать": 15,
        "шестнадцать": 16,
        "семнадцать": 17,
        "восемнадцать": 18,
        "девятнадцать": 19,
    }
    tens = {
        "двадцать": 20,
        "тридцать": 30,
        "сорок": 40,
        "пятьдесят": 50,
        "шестьдесят": 60,
        "семьдесят": 70,
        "восемьдесят": 80,
        "девяносто": 90,
    }
    hundreds = {
        "сто": 100,
        "двести": 200,
        "триста": 300,
        "четыреста": 400,
        "пятьсот": 500,
        "шестьсот": 600,
        "семьсот": 700,
        "восемьсот": 800,
        "девятьсот": 900,
    }
    scales = {
        "тысяча": 1000, "тысячи": 1000, "тысяч": 1000,
        "миллион": 1000000, "миллиона": 1000000, "миллионов": 1000000,
        "миллиард": 1000000000, "миллиарда": 1000000000, "миллиардов": 1000000000,
    }

    s = str(text).lower().replace("ё", "е").replace("-", " ")
    tokens = re.findall(r"[а-я]+", s)

    if not tokens:
        return None

    total = 0
    group = 0
    seen = False

    for token in tokens:
        if token in hundreds:
            group += hundreds[token]
            seen = True
        elif token in teens:
            group += teens[token]
            seen = True
        elif token in tens:
            group += tens[token]
            seen = True
        elif token in units:
            group += units[token]
            seen = True
        elif token in scales:
            mul = scales[token]
            if group == 0:
                group = 1
            total += group * mul
            group = 0
            seen = True

    total += group
    return total if seen else None

def parse_money_words_amount(value):
    s = normalize_money_words_text(value) or normalize_generic_text(value)
    if not s:
        return None

    s_low = s.lower().replace("ё", "е")

    start_match = re.search(
        r"(ноль|один|одна|одно|два|две|три|четыре|пять|шесть|семь|восемь|девять|"
        r"десять|одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать|"
        r"шестнадцать|семнадцать|восемнадцать|девятнадцать|двадцать|тридцать|"
        r"сорок|пятьдесят|шестьдесят|семьдесят|восемьдесят|девяносто|сто|двести|"
        r"триста|четыреста|пятьсот|шестьсот|семьсот|восемьсот|девятьсот)",
        s_low,
        flags=re.I,
    )
    if start_match:
        s = s[start_match.start():]
        s_low = s.lower().replace("ё", "е")

    kop_match = re.search(r"(\d{1,2})\s*коп(?:\.|е[йе]к|ейки|еек)?", s_low, flags=re.I)
    kop = int(kop_match.group(1)) if kop_match else 0

    rub_match = re.search(r"(.+?)\s+(?:белорусских\s+)?рубл[яей]", s_low, flags=re.I)
    rub_text = rub_match.group(1) if rub_match else s_low

    rubles = parse_ru_number_words(rub_text)
    if rubles is None:
        return None

    if kop < 0 or kop > 99:
        kop = 0

    return norm_num(rubles + kop / 100.0)
