"""Shared production resources: dictionaries, rules, and registries."""

from shared.resources.registry import ResourceRegistry, get_resource_registry
from shared.resources.text_lexicon import (
    COMPANY_FORMS,
    COMPANY_QUOTED_NAME_PATTERNS,
    WAYBILL_NAME_STOPWORDS,
)

__all__ = [
    "COMPANY_FORMS",
    "COMPANY_QUOTED_NAME_PATTERNS",
    "ResourceRegistry",
    "WAYBILL_NAME_STOPWORDS",
    "get_resource_registry",
]
