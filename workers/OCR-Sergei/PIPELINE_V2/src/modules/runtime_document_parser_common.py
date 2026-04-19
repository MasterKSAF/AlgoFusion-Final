from __future__ import annotations

import json
import re
from pathlib import Path
# =========================
# helpers
# =========================

CYR_TO_LAT = str.maketrans({
    "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K",
    "М": "M", "О": "O", "Р": "P", "Т": "T", "У": "Y", "Х": "X",
    "І": "I", "Ү": "Y",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
})

MONTHS_RU = (
    "января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря"
)

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_text(s):
    if s is None:
        return None
    s = str(s).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s or None

def only_digits(s):
    s = clean_text(s)
    if not s:
        return None
    d = re.sub(r"\D", "", s)
    return d or None

def normalize_account(s):
    s = clean_text(s)
    if not s:
        return None
    s = s.translate(CYR_TO_LAT).upper()
    s = s.replace(" ", "")
    s = s.replace("О", "0").replace("O", "0")
    s = s.replace("І", "1").replace("I", "1").replace("L", "1")
    return s


def _normalize_latin_code_token(token):
    token = clean_text(token)
    if not token:
        return None

    normalized = token.translate(CYR_TO_LAT).upper()
    normalized = re.sub(r"[^A-Z0-9]", "", normalized)
    return normalized or None


def _normalize_account_token(token):
    token = clean_text(token)
    if not token:
        return None

    normalized = normalize_account(token)
    if not normalized:
        return None
    match = re.search(r"BY\d{2}[A-Z0-9]{24}", normalized)
    return match.group(0) if match else None


def _extract_account_candidates(text):
    cleaned = clean_text(text)
    if not cleaned:
        return []

    normalized_full = normalize_account(cleaned)
    if not normalized_full:
        return []

    out = []
    seen = set()
    for match in re.finditer(r"BY\d{2}[A-Z0-9]{24}", normalized_full):
        normalized = match.group(0)
        if normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out



def to_float(s):
    s = clean_text(s)
    if not s:
        return None
    s = s.translate(CYR_TO_LAT)
    s = s.replace(" ", "").replace(",", ".")
    s = s.replace("О", "0").replace("O", "0")
    s = s.replace("І", "1").replace("I", "1").replace("L", "1")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except:
        return None

def to_int(s):
    v = to_float(s)
    if v is None:
        return None
    return int(round(v))

def normalize_percent(s):
    s = clean_text(s)
    if not s:
        return None
    s = s.replace(" ", "").replace(",", ".").replace("％", "%")
    m = re.search(r"(\d+(?:\.\d+)?)%?", s)
    if not m:
        return None
    num = float(m.group(1))
    return f"{int(num) if num.is_integer() else num}%"

def extract_email(s):
    if not s:
        return None
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', s)
    return m.group(0) if m else None

def extract_phone(s):
    if not s:
        return None
    m = re.search(r'(\+375[\s\-\(\)\d]{8,})', s)
    return clean_text(m.group(1)) if m else None

def extract_tax_id(s):
    if not s:
        return None
    m = re.search(r'\u0423\u041d\u041f\s*([0-9]{9})', s, flags=re.I)
    if m:
        return m.group(1)
    d = only_digits(s)
    if d and len(d) == 9:
        return d
    return None

def extract_kpp(s):
    if not s:
        return None
    m = re.search(r'\u041a\u041f\u041f\s*([0-9]{9})', s, flags=re.I)
    return m.group(1) if m else None

def extract_bank_account(s):
    vals = _extract_account_candidates(s)
    return vals[0] if vals else None

def _normalize_bic_token(token):
    normalized = _normalize_latin_code_token(token)
    if not normalized:
        return None
    if re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}", normalized):
        return normalized
    return None


def _extract_bic_candidates(text):
    cleaned = clean_text(text)
    if not cleaned:
        return []

    tokens = re.findall(r"[A-Za-zА-Яа-яІіҮү0-9]{8,12}", cleaned)
    out = []
    seen = set()
    for token in tokens:
        normalized = _normalize_bic_token(token)
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def _split_leading_code_prefix(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    match = re.match(r"^([A-Za-z\u0410-\u042f\u0430-\u044f\u0406\u0456\u04ae\u04af]{3,6})\s+(\d{4,10})(\b.*)$", cleaned)
    if not match:
        return None
    return match.groups()


def _normalize_known_code_prefix(prefix):
    if not prefix:
        return prefix

    corrections = {
        "OTHK": "OTHR",
    }
    return corrections.get(prefix, prefix)


def normalize_leading_code_prefix(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None

    parts = _split_leading_code_prefix(cleaned)
    if not parts:
        return cleaned

    prefix, numeric_code, tail = parts
    prefix_norm = _normalize_latin_code_token(prefix)
    if not prefix_norm or not re.fullmatch(r"[A-Z]{3,6}", prefix_norm):
        return cleaned
    prefix_norm = _normalize_known_code_prefix(prefix_norm)

    return f"{prefix_norm} {numeric_code}{tail}"


def choose_best_code_prefixed_text(*values):
    best = None
    for value in values:
        cleaned = clean_text(value)
        if not cleaned:
            continue

        parts = _split_leading_code_prefix(cleaned)
        if not parts:
            continue

        prefix, _numeric_code, _tail = parts
        normalized = normalize_leading_code_prefix(cleaned)
        if not normalized:
            continue

        normalized_parts = _split_leading_code_prefix(normalized)
        if not normalized_parts:
            continue

        ascii_letters = len(re.findall(r"[A-Za-z]", prefix))
        cyr_letters = len(re.findall(r"[А-Яа-яІіҮү]", prefix))
        score = (
            1 if re.fullmatch(r"[A-Z]{3,6}", normalized_parts[0]) else 0,
            ascii_letters,
            -cyr_letters,
            len(cleaned),
        )
        if best is None or score >= best[0]:
            best = (score, normalized)

    return best[1] if best else None


def extract_bic(s):
    vals = _extract_bic_candidates(s)
    return vals[0] if vals else None

def extract_all_accounts(s):
    return _extract_account_candidates(s)

def extract_all_tax_ids(s):
    if not s:
        return []
    vals = re.findall(r'(?<!\d)(\d{9})(?!\d)', s)
    return list(dict.fromkeys(vals))

def extract_all_bics(s):
    return _extract_bic_candidates(s)

def extract_all_datetimes(s):
    if not s:
        return []
    vals = re.findall(r'([0-3]?\d\.[01]?\d\.20\d{2}\s+\d{2}:\d{2})', s)
    return list(dict.fromkeys(clean_text(v) for v in vals if clean_text(v)))

def extract_company_names(s):
    if not s:
        return []
    patterns = [
        r'((?:ООО|ОАО|ЗАО|ОДО|ЧУП)\s*["«][^"»]+["»])',
        r'((?:Общество с ограниченной ответственностью|Открытое акционерное общество|Закрытое акционерное общество)\s*["«][^"»]+["»])',
    ]
    vals = []
    for pat in patterns:
        vals.extend(re.findall(pat, s, flags=re.I))
    out = []
    seen = set()
    for v in vals:
        cv = clean_text(v)
        key = cv.lower() if cv else None
        if cv and key not in seen:
            seen.add(key)
            out.append(cv)
    return out

def extract_person_name(s):
    if not s:
        return None
    m = re.search(r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)', s)
    if m:
        val = clean_text(m.group(1))
        val = re.sub(r'копейк$', 'копейки', val, flags=re.I)
        return val
    m = re.search(r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.)', s)
    return clean_text(m.group(1)) if m else None

def cleanup_bank_name(s):
    if not s:
        return None
    s = clean_text(s)
    s = re.sub(r'\b[A-Z]{6}[A-Z0-9]{2}\b', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip(' ,;:')
    return s or None

def extract_doc_number_by_no(s):
    if not s:
        return None
    m = re.search(r'№\s*([A-Za-zА-Яа-я0-9\-\/]+)', s)
    return clean_text(m.group(1)) if m else None

def extract_ru_date_text(s):
    if not s:
        return None
    m = re.search(rf'([0-3]?\d\s+(?:{MONTHS_RU})\s+20\d{{2}}\s*г?\.?)', s, flags=re.I)
    if m:
        val = clean_text(m.group(1))
        val = re.sub(r'копейк$', 'копейки', val, flags=re.I)
        return val
    m = re.search(r'([0-3]?\d\.[01]?\d\.20\d{2}(?:\s+\d{2}:\d{2})?)', s)
    if m:
        return clean_text(m.group(1))
    return None

def get_regions(data):
    return data.get("regions", []) if isinstance(data, dict) else []

def group_rows(table_cells, tol=12):
    rows = []
    for cell in sorted(table_cells, key=lambda r: (r["bbox"][1], r["bbox"][0])):
        y = cell["bbox"][1]
        placed = False
        for row in rows:
            row_y = round(sum(c["bbox"][1] for c in row) / len(row))
            if abs(y - row_y) <= tol:
                row.append(cell)
                placed = True
                break
        if not placed:
            rows.append([cell])
    for row in rows:
        row.sort(key=lambda c: c["bbox"][0])
    return rows

def row_texts(row):
    return [clean_text(c.get("text")) or "" for c in row]

def looks_like_table_header(texts):
    joined = " ".join((clean_text(x) or "") for x in texts).lower()

    patterns = [
        r"\bартикул\b",
        r"\bтовар\b",
        r"\bштрих\b",
        r"\bцена\b",
        r"\bсумма\b",
        r"\bндс\b",
        r"\bкол(?:-во|ичество)?\b",
        r"\bед\.?\b",
    ]

    hits = sum(1 for pat in patterns if re.search(pat, joined))
    return hits >= 3


def is_header_row(texts):
    return looks_like_table_header(texts)


def is_index_row(texts):
    vals = [clean_text(v) for v in texts if clean_text(v)]
    if len(vals) < 3:
        return False

    nums = []
    for v in vals:
        vv = v.replace("l", "1").replace("I", "1").replace("|", "1")
        if not vv.isdigit():
            return False
        nums.append(int(vv))

    diffs = [b - a for a, b in zip(nums, nums[1:])]
    return all(d == 1 for d in diffs)


def is_total_row(texts):
    joined = " ".join((clean_text(x) or "") for x in texts).lower()
    return "итого" in joined


def filter_table_rows(table_rows):
    clean_rows = []

    for row in table_rows:
        texts = [clean_text(cell.get("text")) or "" for cell in row]
        joined = " ".join(texts).lower()

        if looks_like_table_header(texts):
            continue
        if is_index_row(texts):
            continue
        if "итого" in joined:
            continue

        clean_rows.append(row)

    return clean_rows


def invoice_is_header_row(texts):
    return looks_like_table_header(texts)


def invoice_is_index_row(texts):
    return is_index_row(texts)




