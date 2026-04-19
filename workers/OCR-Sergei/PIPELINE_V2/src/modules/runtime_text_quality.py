from __future__ import annotations

from src.modules.runtime_text_common import (
    BAD_SYMBOL_RE,
    REVIEW_FIELD_MARKER,
    _clean_inline_text,
    _collapse_repeated_punctuation,
    _is_review_field_marker,
    _review_marker_or_none,
)
from src.modules.runtime_text_noise import (
    _invoice_description_has_unreliable_ocr,
    _item_text_has_unreliable_ocr,
    _sanitize_final_text_or_review,
    _strict_text_has_unreliable_ocr,
    _trim_edge_noise_tokens,
)
