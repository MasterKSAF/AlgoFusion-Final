from __future__ import annotations

from src.modules.runtime_prediction_amount_helpers import (
    as_num,
    is_missing,
    non_negative,
    parse_money_words_amount,
    rubles_part,
    sum_item_field,
)


def build_total_maps(doc_type):
    if doc_type == "invoice":
        total_map = {
            "total_quantity": "quantity",
            "subtotal_no_disc_incl_vat": "amount_no_disc_incl_vat",
            "total_disc_amount": "disc_amount",
            "subtotal_with_disc_excl_vat": "amount_with_disc_excl_vat",
            "vat_amount": "vat_amount",
            "total_with_disc_incl_vat": "total_with_disc_incl_vat",
        }
        words_total_map = {
            "total_in_words": "total_with_disc_incl_vat",
        }
    elif doc_type == "waybill":
        total_map = {
            "quantity_total": "quantity",
            "cost_total": "cost",
            "vat_total": "vat_amount",
            "cost_with_vat_total": "cost_with_vat",
        }
        words_total_map = {
            "vat_total_words": "vat_total",
            "cost_with_vat_total_words": "cost_with_vat_total",
        }
    elif doc_type == "account_prot":
        total_map = {
            "subtotal_excl_vat": "total_excl_vat",
            "vat_amount": "vat_amount",
            "total_incl_vat": "total_incl_vat",
        }
        words_total_map = {
            "total_in_words": "total_incl_vat",
        }
    else:
        total_map = {}
        words_total_map = {}
    return total_map, words_total_map


def reconcile_document_totals(ctx, items, totals):
    total_map, words_total_map = build_total_maps(ctx.doc_type)
    ctx.totals = totals
    ctx.total_map = total_map
    ctx.words_total_map = words_total_map

    derived_totals = {}
    ctx.derived_totals = derived_totals
    for total_field, item_field in total_map.items():
        derived_totals[total_field] = sum_item_field(items, item_field)

    for total_field, item_field in total_map.items():
        derived = derived_totals.get(total_field)
        extracted = totals.get(total_field)

        if is_missing(extracted):
            if derived is not None and derived >= 0:
                ctx.set_missing_numeric(totals, total_field, derived, f"sum(items.{item_field})", "totals")
        elif derived is not None and not ctx.close_enough(extracted, derived):
            ctx.add_warning(total_field, extracted, derived, "totals", source=f"sum(items.{item_field})")

    parsed_words_totals = {}
    ctx.parsed_words_totals = parsed_words_totals

    for words_field, numeric_field in words_total_map.items():
        words_text = totals.get(words_field)
        parsed_amount = parse_money_words_amount(words_text)
        if parsed_amount is None:
            continue
        parsed_words_totals[numeric_field] = parsed_amount

        extracted = totals.get(numeric_field)

        if is_missing(extracted):
            if parsed_amount >= 0:
                ctx.set_missing_numeric(totals, numeric_field, parsed_amount, f"parsed({words_field})", "totals")
            continue

        if not ctx.close_enough(extracted, parsed_amount):
            extracted_rub = rubles_part(extracted)
            parsed_rub = rubles_part(parsed_amount)

            if extracted_rub is not None and parsed_rub is not None and extracted_rub == parsed_rub:
                continue

            ctx.add_warning(numeric_field, extracted, parsed_amount, "totals", source=f"parsed({words_field})")

    for total_field in total_map.keys():
        extracted = as_num(totals.get(total_field))
        if extracted is None:
            continue

        supports = ctx.total_supports_for_field(total_field)
        target, labels = ctx.consensus_from_supports(supports, min_count=2)
        if target is None or ctx.close_enough(extracted, target):
            continue

        if ctx.looks_like_decimal_shift(extracted, target):
            ctx.set_corrected_numeric(
                totals,
                total_field,
                extracted,
                target,
                " & ".join(labels),
                "totals",
                support_count=len(labels),
            )
        else:
            ctx.add_warning(total_field, extracted, target, "totals", source=" & ".join(labels))
