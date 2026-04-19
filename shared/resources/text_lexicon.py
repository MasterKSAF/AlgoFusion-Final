from __future__ import annotations

import re
from functools import lru_cache

from shared.resources.registry import get_resource_registry

_registry = get_resource_registry()


def _regex_union(values: tuple[str, ...]) -> str:
    return "|".join(sorted((re.escape(value) for value in values), key=len, reverse=True))


def _dictionary_values(name: str) -> tuple[str, ...]:
    return tuple(_registry.list_dictionary_values(name))


@lru_cache(maxsize=1)
def company_forms() -> tuple[str, ...]:
    return _dictionary_values("company_forms")


@lru_cache(maxsize=1)
def company_forms_pattern() -> str:
    return _regex_union(company_forms())


@lru_cache(maxsize=1)
def company_quoted_name_patterns() -> tuple[str, ...]:
    quote_tail = r'\s+[«"][^»"]+[»"]'
    return tuple(rf"({re.escape(form)}{quote_tail})" for form in company_forms())


@lru_cache(maxsize=1)
def waybill_name_stopwords() -> frozenset[str]:
    values = _dictionary_values("waybill_name_stopwords")
    return frozenset(value.casefold() for value in values)


COMPANY_FORMS = company_forms()
COMPANY_FORMS_PATTERN = company_forms_pattern()
COMPANY_QUOTED_NAME_PATTERNS = company_quoted_name_patterns()
WAYBILL_NAME_STOPWORDS = waybill_name_stopwords()

ACCOUNT_PROT_PATTERN = r"счет[-\s]*протокол"
PAYMENT_ORDER_PATTERN = r"платежн\w*\s+поручен"
WAYBILL_DOC_PATTERN = r"товарн(?:о[-\s]*транспортн\w*\s+)?накладн"
WAYBILL_SENDER_PATTERN = r"грузоотправ"
WAYBILL_RECEIVER_PATTERN = r"грузополуч"
WAYBILL_BASIS_PATTERN = r"основани[ея]\s+отпуска"
WAYBILL_RELEASE_PATTERN = r"отпуск\s+разрешил"

INVOICE_NUMBER_PATTERN = r"\bсчет\b\s*(?:№|N|No|#)\s*[\w#/\-]+"
INVOICE_DATE_PATTERN = (
    r"\bсчет\b.{0,30}\bот\b.{0,24}"
    r"(?:[0-3]?\d[./][01]?\d[./]20\d{2}|[0-3]?\d\s+\w+\s+20\d{2})"
)
INVOICE_SELLER_PATTERN = r"\bпродавец\b"
INVOICE_BUYER_PATTERN = r"\bпокупател"
INVOICE_SUPPLIER_PATTERN = r"\bпоставщик\b"
INVOICE_BASIS_PATTERN = r"\bоснован"
INVOICE_TOTAL_LINE_PATTERN = r"\b(?:итого|всего\s+к\s+оплате|счет\s+действителен)\b|mroro"

WAYBILL_ADDRESS_BASIS_PATTERN = r"\b(?:Основание\s+отпуска|Осснование\s+отпуска|Договор)\b"
WAYBILL_ADDRESS_STOP_PATTERN = (
    r"\b(?:I+[\.\s]+ТОВАРН|ТОВАРНЫЙ\s+РАЗДЕЛ|Принял\s+грузополучатель|"
    r"С\s+товаром|220\d{3},\s*г\.)\b"
)
WAYBILL_BRIDGE_CONTEXT_PATTERN = (
    r"\b(?:скидк\w*|цена\s+отпуск\w*|товар\s+для\s+собственн\w*|свидетельств\w*)\b"
)
WAYBILL_HEADER_ANCHOR_NOISE_PATTERN = (
    r"Гр\S{0,12}(?:отправ|получ)\w*|Груз\w*(?:отправ|получ)\w*|"
    r"Осн\w*\s+\S*пуск\w*|Основание\s+отпуска|Пункт\s+(?:погрузки|разгрузки)|"
    r"\(наим|\(адр|наимин|адрос|овиние"
)
WAYBILL_ADDRESS_TOKEN_PATTERN = (
    r"(^|[\s,])(ул\.|пр\.|пр-?т|г\.|район|р-н|каб\.|пом\.|Беларусь|обл\.)(?=$|[\s,])"
)
WAYBILL_ADDRESS_SCORE_TOKEN_PATTERN = r"(^|[\s,])(ул\.|пр\.|г\.|р-н|каб\.|пом\.|Беларусь|обл\.)(?=$|[\s,])"
WAYBILL_NOTE_TAIL_MARKERS = ("цена отпуск", "скидка к отпуск")

__all__ = [
    "ACCOUNT_PROT_PATTERN",
    "COMPANY_FORMS",
    "COMPANY_FORMS_PATTERN",
    "COMPANY_QUOTED_NAME_PATTERNS",
    "INVOICE_BASIS_PATTERN",
    "INVOICE_BUYER_PATTERN",
    "INVOICE_DATE_PATTERN",
    "INVOICE_NUMBER_PATTERN",
    "INVOICE_SELLER_PATTERN",
    "INVOICE_SUPPLIER_PATTERN",
    "INVOICE_TOTAL_LINE_PATTERN",
    "PAYMENT_ORDER_PATTERN",
    "WAYBILL_ADDRESS_BASIS_PATTERN",
    "WAYBILL_ADDRESS_SCORE_TOKEN_PATTERN",
    "WAYBILL_ADDRESS_STOP_PATTERN",
    "WAYBILL_ADDRESS_TOKEN_PATTERN",
    "WAYBILL_BASIS_PATTERN",
    "WAYBILL_BRIDGE_CONTEXT_PATTERN",
    "WAYBILL_DOC_PATTERN",
    "WAYBILL_HEADER_ANCHOR_NOISE_PATTERN",
    "WAYBILL_NAME_STOPWORDS",
    "WAYBILL_NOTE_TAIL_MARKERS",
    "WAYBILL_RECEIVER_PATTERN",
    "WAYBILL_RELEASE_PATTERN",
    "WAYBILL_SENDER_PATTERN",
]
