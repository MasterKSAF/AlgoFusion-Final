"""Base helpers and path predicates for prediction normalization."""

import math
import re

from src.modules.runtime_prediction_normalizer_config import PARTY_BLOCK_KEYS, REVIEW_FIELD_MARKER


def is_nan_like(v):
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and v.strip().lower() in {"", "nan", "none", "null"}:
        return True
    return False

def clean_spaces(s: str) -> str:
    s = str(s).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def clean_text(value):
    if is_nan_like(value):
        return None
    s = clean_spaces(value)
    return s or None

def is_review_field_marker(value):
    if value is None:
        return False
    return clean_spaces(value).lower() == REVIEW_FIELD_MARKER

def path_leaf(path):
    return path[-1] if path else None

def path_has(path, *keys):
    return any(part in keys for part in path)

def is_product_text_field(path):
    leaf = path_leaf(path)
    return leaf in {"name", "description"} and path_has(path, "items")

def is_party_name_field(path):
    leaf = path_leaf(path)
    return leaf == "name" and path_has(path, *PARTY_BLOCK_KEYS) and not path_has(path, "items")
