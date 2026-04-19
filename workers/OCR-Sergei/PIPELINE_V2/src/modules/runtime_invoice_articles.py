from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_text_quality import _clean_inline_text


def normalize_invoice_article_value(text: Any) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None
    cleaned = re.sub(r"\s*/\s*", "/", cleaned.strip(" ,;|"))
    cleaned = re.sub(r"\s+", "", cleaned)
    if not cleaned:
        return None
    if re.fullmatch(r"0/\d{1,3}", cleaned):
        return None
    return cleaned.upper()


def _extract_invoice_article_token_strict(cleaned: str) -> str | None:
    match = re.search(
        r"\b([A-Z\u0410-\u042f0-9]{1,8}(?:\s+[A-Z\u0410-\u042f0-9]{1,8}){0,2}\s*/\s*[A-Z\u0410-\u042f0-9./-]{1,16})\b",
        cleaned,
        flags=re.I,
    )
    if not match:
        return None
    return normalize_invoice_article_value(match.group(1))


def _extract_invoice_leading_article_token(cleaned: str) -> str | None:
    source = _clean_inline_text(cleaned) or ""
    if not source:
        return None

    patterns = (
        r"^\s*([A-ZА-Я]\.\d{2,8})(?=\s|[,;:]|$)",
        r"^\s*([A-ZА-Я]{1,8}\s+\d{2,5}(?:[./-][A-ZА-Я0-9]{1,10})?)(?=\s|[,;:]|$)",
        r"^\s*([A-ZА-Я]{1,10}\d[A-ZА-Я0-9]*(?:[./-][A-ZА-Я0-9]{1,12})?)(?=\s|[,;:]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, source, flags=re.I)
        if not match:
            continue
        candidate = normalize_invoice_article_value(match.group(1))
        if not candidate:
            continue
        if len(candidate) < 3 or len(candidate) > 24:
            continue
        if not re.search(r"[A-ZА-Я]", candidate, flags=re.I) or not re.search(r"\d", candidate):
            continue
        return candidate
    return None


def _strip_invoice_embedded_line_number(article: str | None, line_number: int | None) -> str | None:
    cleaned = normalize_invoice_article_value(article)
    if not cleaned or line_number is None:
        return cleaned

    line_text = str(int(line_number))
    if cleaned.startswith(line_text) and len(cleaned) > len(line_text):
        next_char = cleaned[len(line_text) : len(line_text) + 1]
        if re.fullmatch(r"[A-Z\u0410-\u042f]", next_char, flags=re.I):
            stripped = normalize_invoice_article_value(cleaned[len(line_text) :])
            if stripped:
                cleaned = stripped
    if cleaned.endswith(line_text) and len(cleaned) > len(line_text):
        prev_char = cleaned[-len(line_text) - 1 : -len(line_text)]
        if re.fullmatch(r"[A-Z\u0410-\u042f0-9./-]", prev_char, flags=re.I):
            stripped = normalize_invoice_article_value(cleaned[: -len(line_text)])
            if stripped and "/" in stripped:
                cleaned = stripped
    return cleaned


def extract_invoice_article_candidate(text: Any, line_number: int | None = None) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None

    strict = _extract_invoice_article_token_strict(cleaned)
    if strict:
        return _strip_invoice_embedded_line_number(strict, line_number)

    leading = _extract_invoice_leading_article_token(cleaned)
    if leading:
        return _strip_invoice_embedded_line_number(leading, line_number)

    compact = cleaned.strip(" ,;|\"'`[](){}")
    compact = compact.replace("’", "'").replace("`", "'")
    compact = re.sub(r"\s+", "", compact)
    compact = compact.replace("~", "").replace("'", "").replace("|", "")
    compact = re.sub(r"(?<=/):(?=\d)", "1", compact)
    compact = re.sub(r"(?<=\d):(?=\d)", ".", compact)
    compact = re.sub(r"^[^A-Z\u0410-\u042f0-9]+", "", compact, flags=re.I)
    compact = re.sub(r"[^A-Z\u0410-\u042f0-9./:-]+$", "", compact, flags=re.I)
    if not compact or len(compact) > 24:
        return None
    if "/" not in compact:
        return None
    if not re.search(r"[A-Z\u0410-\u042f]", compact, flags=re.I) or not re.search(r"\d", compact):
        return None
    return _strip_invoice_embedded_line_number(compact, line_number)


def extract_invoice_lead_parts(text: Any, fallback_line_number: int) -> tuple[int | None, str | None]:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return fallback_line_number, None

    line_number = fallback_line_number
    body = cleaned
    line_match = re.match(r"^\s*(\d{1,3})\b", body)
    if line_match:
        try:
            line_number = int(line_match.group(1))
        except Exception:
            line_number = fallback_line_number
        body = body[line_match.end() :].strip()
    else:
        tail_match = re.search(r"\b(\d{1,3})\s*$", body)
        if tail_match:
            try:
                line_number = int(tail_match.group(1))
            except Exception:
                line_number = fallback_line_number
            body = body[: tail_match.start()].strip()

    article = extract_invoice_article_candidate(body or cleaned, line_number)
    return line_number, article


def extract_invoice_article_token(text: Any) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None
    return _extract_invoice_article_token_strict(cleaned)


def looks_like_invoice_article_cell(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned or len(cleaned) > 48:
        return False
    tokens = [token for token in re.split(r"\s+", cleaned) if token]
    if not tokens:
        return False
    article_like = [token for token in tokens if extract_invoice_article_candidate(token)]
    return len(article_like) >= 1 and len(article_like) == len(tokens)


def clean_invoice_description_value(text: Any, article: str | None = None) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None
    if article:
        cleaned = re.sub(rf"^\s*{re.escape(article)}\s+", "", cleaned, flags=re.I)
        if re.fullmatch(r"[A-ZА-Я]{1,10}\d[A-ZА-Я0-9]{1,10}", article, flags=re.I):
            spaced_article = re.sub(r"(?<=[A-ZА-Я])(?=\d)", r"\\s*", re.escape(article), flags=re.I)
            spaced_article = re.sub(r"(?<=\d)(?=[A-ZА-Я])", r"\\s*", spaced_article, flags=re.I)
            cleaned = re.sub(rf"^\s*{spaced_article}\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;|")
    return cleaned or None


def extract_invoice_lead_fields(
    lead_cells: list[str],
    fallback_line_number: int,
) -> tuple[int | None, str | None, str | None]:
    nonempty = [_clean_inline_text(cell) for cell in lead_cells if _clean_inline_text(cell)]
    if not nonempty:
        return fallback_line_number, None, None

    first = nonempty[0]
    line_number, first_article = extract_invoice_lead_parts(first, fallback_line_number)
    article = None
    if first_article and (re.match(r"^\s*\d", first) or re.search(r"\d{1,3}\s*$", first) or looks_like_invoice_article_cell(first)):
        article = first_article

    remaining = nonempty[1:]
    if remaining and looks_like_invoice_article_cell(remaining[0]):
        second_article = extract_invoice_article_candidate(remaining[0], line_number)
        if second_article:
            article = article or second_article
        remaining = remaining[1:]

    description_source = " ".join(remaining) if remaining else None
    if (
        not description_source
        and not looks_like_invoice_article_cell(first)
        and not re.fullmatch(r"\d{1,3}(?:\s+\d{1,3})*", first or "")
    ):
        description_source = first
    description = clean_invoice_description_value(description_source, article=article)

    if article is None and first_article and description:
        article = first_article
        description = clean_invoice_description_value(description, article=article)

    if article is None and description:
        leading_article = extract_invoice_article_token(description)
        if leading_article:
            stripped = clean_invoice_description_value(description, article=leading_article)
            article = leading_article
            if stripped:
                description = stripped

    return line_number, article, description


def extract_invoice_barcode_cell_description(text: Any, article: str | None = None) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None
    match = re.search(r"\d{8,14}", cleaned)
    if not match:
        return None
    prefix = cleaned[: match.start()]
    prefix = clean_invoice_description_value(prefix, article=article)
    if not prefix or len(prefix) < 6:
        return None
    if re.fullmatch(r'[".\-_\s]+', prefix):
        return None
    return prefix
