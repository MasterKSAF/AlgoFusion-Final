from __future__ import annotations

from src.modules.runtime_waybill_header_fallback import (
    extract_company_name_address,
    looks_like_address_only,
    overlay_waybill_header_fallback,
    split_person_value_pair,
)


def test_extract_company_name_address_splits_company_and_address() -> None:
    name, address = extract_company_name_address('ООО "Тест Логистик", г. Минск, ул. Ленина, 1')

    assert name == 'ООО "Тест Логистик"'
    assert address == "г. Минск, ул. Ленина, 1"


def test_looks_like_address_only_detects_address_without_company() -> None:
    assert looks_like_address_only("г. Минск, ул. Ленина, 1") is True
    assert looks_like_address_only('ООО "Тест Логистик", г. Минск') is False


def test_overlay_waybill_header_fallback_prefers_distinct_raw_parties_for_same_current_party() -> None:
    base = {
        "basis": "Грузоотправитель ООО Старое",
        "sender": {"name": 'ООО "Одинаковое"', "address": None},
        "receiver": {"name": 'ООО "Одинаковое"', "address": None},
    }
    raw_fallback = {
        "basis": "Договор поставки от 01.01.2024",
        "sender": {"name": 'ООО "Отправитель"', "address": "г. Минск"},
        "receiver": {"name": 'ООО "Получатель"', "address": "г. Гродно"},
    }

    merged = overlay_waybill_header_fallback(base, raw_fallback)

    assert merged["basis"] == "Договор поставки от 01.01.2024"
    assert merged["sender"]["name"] == 'ООО "Отправитель"'
    assert merged["receiver"]["name"] == 'ООО "Получатель"'


def test_split_person_value_pair_handles_initials_without_regex_error() -> None:
    person, value = split_person_value_pair("Ivanov I.I. warehouse section")

    assert person == "Ivanov I.I."
    assert value == "warehouse section"


def test_overlay_waybill_header_fallback_replaces_review_tax_ids_with_raw_values() -> None:
    base = {
        "sender": {"name": 'ООО "Отправитель"', "address": "г. Минск", "tax_id": "проверить поле"},
        "receiver": {"name": 'ООО "Получатель"', "address": "г. Гродно", "tax_id": "проверить поле"},
        "payer": {"name": None, "address": None, "tax_id": None},
    }
    raw_fallback = {
        "sender": {"name": 'ООО "Отправитель"', "address": "г. Минск", "tax_id": "690667789"},
        "receiver": {"name": 'ООО "Получатель"', "address": "г. Гродно", "tax_id": "193716061"},
        "payer": {"name": None, "address": None, "tax_id": "123456789"},
    }

    merged = overlay_waybill_header_fallback(base, raw_fallback)

    assert merged["sender"]["tax_id"] == "690667789"
    assert merged["receiver"]["tax_id"] == "193716061"
    assert merged["payer"]["tax_id"] == "123456789"
