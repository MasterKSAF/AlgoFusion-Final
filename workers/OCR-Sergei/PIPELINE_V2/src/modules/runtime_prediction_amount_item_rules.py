from __future__ import annotations

from src.modules.runtime_prediction_amount_helpers import (
    as_num,
    as_rate,
    maybe_round_money,
    non_negative,
    safe_div,
)


def recover_invoice_item_amounts(ctx, item, idx):
    q = as_num(item.get("quantity"))
    unit_price_incl_vat = as_num(item.get("unit_price_incl_vat"))
    amount_no_disc_incl_vat = as_num(item.get("amount_no_disc_incl_vat"))
    disc_amount = as_num(item.get("disc_amount"))
    amount_with_disc_excl_vat = as_num(item.get("amount_with_disc_excl_vat"))
    vat_rate = as_rate(item.get("vat_rate"))
    vat_amount = as_num(item.get("vat_amount"))
    total_with_disc_incl_vat = as_num(item.get("total_with_disc_incl_vat"))

    ctx.try_correct_numeric(
        item,
        "total_with_disc_incl_vat",
        [
            ("amount_with_disc_excl_vat + vat_amount",
             (amount_with_disc_excl_vat + vat_amount)
             if non_negative(amount_with_disc_excl_vat) and non_negative(vat_amount) else None),
            ("amount_no_disc_incl_vat - disc_amount",
             (amount_no_disc_incl_vat - disc_amount)
             if amount_no_disc_incl_vat is not None and disc_amount is not None and amount_no_disc_incl_vat >= disc_amount >= 0
             else None),
            ("quantity * unit_price_incl_vat (discount blank/0)",
             (q * unit_price_incl_vat)
             if non_negative(q) and non_negative(unit_price_incl_vat) and (disc_amount is None or ctx.close_enough(disc_amount, 0))
             else None),
            ("amount_with_disc_excl_vat * (1 + vat_rate)",
             maybe_round_money(amount_with_disc_excl_vat * (1 + vat_rate))
             if non_negative(amount_with_disc_excl_vat) and vat_rate is not None and vat_rate >= 0
             else None),
        ],
        "item",
        idx,
    )

    q = as_num(item.get("quantity"))
    unit_price_incl_vat = as_num(item.get("unit_price_incl_vat"))
    amount_no_disc_incl_vat = as_num(item.get("amount_no_disc_incl_vat"))
    disc_amount = as_num(item.get("disc_amount"))
    amount_with_disc_excl_vat = as_num(item.get("amount_with_disc_excl_vat"))
    vat_rate = as_rate(item.get("vat_rate"))
    vat_amount = as_num(item.get("vat_amount"))
    total_with_disc_incl_vat = as_num(item.get("total_with_disc_incl_vat"))

    ctx.try_correct_numeric(
        item,
        "amount_no_disc_incl_vat",
        [
            ("quantity * unit_price_incl_vat",
             (q * unit_price_incl_vat)
             if non_negative(q) and non_negative(unit_price_incl_vat)
             else None),
            ("total_with_disc_incl_vat + disc_amount",
             (total_with_disc_incl_vat + disc_amount)
             if non_negative(total_with_disc_incl_vat) and non_negative(disc_amount)
             else None),
        ],
        "item",
        idx,
    )

    ctx.try_correct_numeric(
        item,
        "amount_with_disc_excl_vat",
        [
            ("total_with_disc_incl_vat - vat_amount",
             (total_with_disc_incl_vat - vat_amount)
             if total_with_disc_incl_vat is not None and vat_amount is not None and total_with_disc_incl_vat >= vat_amount >= 0
             else None),
            ("total_with_disc_incl_vat / (1 + vat_rate)",
             maybe_round_money(safe_div(total_with_disc_incl_vat, (1 + vat_rate)))
             if non_negative(total_with_disc_incl_vat) and vat_rate is not None and vat_rate >= 0
             else None),
        ],
        "item",
        idx,
    )

    ctx.try_correct_numeric(
        item,
        "vat_amount",
        [
            ("total_with_disc_incl_vat - amount_with_disc_excl_vat",
             (total_with_disc_incl_vat - amount_with_disc_excl_vat)
             if total_with_disc_incl_vat is not None and amount_with_disc_excl_vat is not None and total_with_disc_incl_vat >= amount_with_disc_excl_vat >= 0
             else None),
            ("amount_with_disc_excl_vat * vat_rate",
             maybe_round_money(amount_with_disc_excl_vat * vat_rate)
             if non_negative(amount_with_disc_excl_vat) and vat_rate is not None and vat_rate >= 0
             else None),
        ],
        "item",
        idx,
    )

    ctx.try_correct_numeric(
        item,
        "disc_amount",
        [
            ("amount_no_disc_incl_vat - total_with_disc_incl_vat",
             (amount_no_disc_incl_vat - total_with_disc_incl_vat)
             if amount_no_disc_incl_vat is not None and total_with_disc_incl_vat is not None and amount_no_disc_incl_vat >= total_with_disc_incl_vat >= 0
             else None),
            ("quantity * unit_price_incl_vat - total_with_disc_incl_vat",
             ((q * unit_price_incl_vat) - total_with_disc_incl_vat)
             if non_negative(q) and non_negative(unit_price_incl_vat) and total_with_disc_incl_vat is not None and (q * unit_price_incl_vat) >= total_with_disc_incl_vat >= 0
             else None),
        ],
        "item",
        idx,
    )

    q = as_num(item.get("quantity"))
    unit_price_incl_vat = as_num(item.get("unit_price_incl_vat"))
    amount_no_disc_incl_vat = as_num(item.get("amount_no_disc_incl_vat"))
    disc_amount = as_num(item.get("disc_amount"))
    amount_with_disc_excl_vat = as_num(item.get("amount_with_disc_excl_vat"))
    vat_rate = as_rate(item.get("vat_rate"))
    vat_amount = as_num(item.get("vat_amount"))
    total_with_disc_incl_vat = as_num(item.get("total_with_disc_incl_vat"))

    if amount_no_disc_incl_vat is None and non_negative(q) and non_negative(unit_price_incl_vat):
        amount_no_disc_incl_vat = q * unit_price_incl_vat
        ctx.set_missing_numeric(
            item,
            "amount_no_disc_incl_vat",
            amount_no_disc_incl_vat,
            "quantity * unit_price_incl_vat",
            "item",
            idx,
        )

    if amount_no_disc_incl_vat is None and non_negative(total_with_disc_incl_vat) and non_negative(disc_amount):
        amount_no_disc_incl_vat = total_with_disc_incl_vat + disc_amount
        ctx.set_missing_numeric(
            item,
            "amount_no_disc_incl_vat",
            amount_no_disc_incl_vat,
            "total_with_disc_incl_vat + disc_amount",
            "item",
            idx,
        )

    if total_with_disc_incl_vat is None and non_negative(amount_no_disc_incl_vat) and non_negative(disc_amount):
        candidate_total = amount_no_disc_incl_vat - disc_amount
        if candidate_total >= 0:
            total_with_disc_incl_vat = candidate_total
            ctx.set_missing_numeric(
                item,
                "total_with_disc_incl_vat",
                total_with_disc_incl_vat,
                "amount_no_disc_incl_vat - disc_amount",
                "item",
                idx,
            )

    if disc_amount is None and amount_no_disc_incl_vat is not None and total_with_disc_incl_vat is not None:
        candidate_disc = amount_no_disc_incl_vat - total_with_disc_incl_vat
        if candidate_disc > 0:
            disc_amount = candidate_disc
            ctx.set_missing_numeric(
                item,
                "disc_amount",
                disc_amount,
                "amount_no_disc_incl_vat - total_with_disc_incl_vat",
                "item",
                idx,
            )

    if (
        vat_amount is None
        and total_with_disc_incl_vat is not None
        and amount_with_disc_excl_vat is not None
        and total_with_disc_incl_vat >= amount_with_disc_excl_vat >= 0
    ):
        candidate_vat_amount = total_with_disc_incl_vat - amount_with_disc_excl_vat
        if candidate_vat_amount > 0:
            vat_amount = candidate_vat_amount
            ctx.set_missing_numeric(
                item,
                "vat_amount",
                vat_amount,
                "total_with_disc_incl_vat - amount_with_disc_excl_vat",
                "item",
                idx,
            )

    if amount_with_disc_excl_vat is None and non_negative(total_with_disc_incl_vat) and non_negative(vat_amount):
        candidate_excl = total_with_disc_incl_vat - vat_amount
        if candidate_excl >= 0:
            amount_with_disc_excl_vat = candidate_excl
            ctx.set_missing_numeric(
                item,
                "amount_with_disc_excl_vat",
                amount_with_disc_excl_vat,
                "total_with_disc_incl_vat - vat_amount",
                "item",
                idx,
            )

    if amount_with_disc_excl_vat is None and non_negative(total_with_disc_incl_vat) and vat_rate is not None and vat_rate >= 0:
        candidate_excl = safe_div(total_with_disc_incl_vat, 1 + vat_rate)
        candidate_excl = maybe_round_money(candidate_excl)
        if non_negative(candidate_excl):
            amount_with_disc_excl_vat = candidate_excl
            ctx.set_missing_numeric(
                item,
                "amount_with_disc_excl_vat",
                amount_with_disc_excl_vat,
                "total_with_disc_incl_vat / (1 + vat_rate)",
                "item",
                idx,
            )

    if vat_amount is None and non_negative(amount_with_disc_excl_vat) and vat_rate is not None and vat_rate >= 0:
        candidate_vat_amount = maybe_round_money(amount_with_disc_excl_vat * vat_rate)
        if candidate_vat_amount > 0:
            vat_amount = candidate_vat_amount
            ctx.set_missing_numeric(
                item,
                "vat_amount",
                vat_amount,
                "amount_with_disc_excl_vat * vat_rate",
                "item",
                idx,
            )

    if total_with_disc_incl_vat is None and non_negative(amount_with_disc_excl_vat) and non_negative(vat_amount):
        total_with_disc_incl_vat = amount_with_disc_excl_vat + vat_amount
        ctx.set_missing_numeric(
            item,
            "total_with_disc_incl_vat",
            total_with_disc_incl_vat,
            "amount_with_disc_excl_vat + vat_amount",
            "item",
            idx,
        )


def recover_waybill_item_amounts(ctx, item, idx):
    q = as_num(item.get("quantity"))
    price = as_num(item.get("price"))
    cost = as_num(item.get("cost"))
    vat_amount = as_num(item.get("vat_amount"))
    cost_with_vat = as_num(item.get("cost_with_vat"))
    vat_rate = as_rate(item.get("vat_rate"))

    ctx.try_correct_numeric(
        item,
        "cost",
        [
            ("quantity * price", (q * price) if non_negative(q) and non_negative(price) else None),
            ("cost_with_vat - vat_amount",
             (cost_with_vat - vat_amount)
             if cost_with_vat is not None and vat_amount is not None and cost_with_vat >= vat_amount >= 0
             else None),
        ],
        "item",
        idx,
    )

    ctx.try_correct_numeric(
        item,
        "vat_amount",
        [
            ("cost_with_vat - cost",
             (cost_with_vat - cost)
             if cost_with_vat is not None and cost is not None and cost_with_vat >= cost >= 0
             else None),
            ("cost * vat_rate",
             (cost * vat_rate)
             if non_negative(cost) and vat_rate is not None and vat_rate >= 0
             else None),
        ],
        "item",
        idx,
    )

    q = as_num(item.get("quantity"))
    price = as_num(item.get("price"))
    cost = as_num(item.get("cost"))
    vat_amount = as_num(item.get("vat_amount"))
    cost_with_vat = as_num(item.get("cost_with_vat"))

    if cost is None and non_negative(q) and non_negative(price):
        cost = q * price
        ctx.set_missing_numeric(item, "cost", cost, "quantity * price", "item", idx)

    if (
        vat_amount is None
        and cost_with_vat is not None
        and cost is not None
        and cost_with_vat >= cost >= 0
    ):
        vat_amount = cost_with_vat - cost
        ctx.set_missing_numeric(item, "vat_amount", vat_amount, "cost_with_vat - cost", "item", idx)

    if cost_with_vat is None and non_negative(cost) and non_negative(vat_amount):
        cost_with_vat = cost + vat_amount
        ctx.set_missing_numeric(item, "cost_with_vat", cost_with_vat, "cost + vat_amount", "item", idx)


def recover_account_protocol_item_amounts(ctx, item, idx):
    q = as_num(item.get("quantity"))
    free_unit_price_excl_vat = as_num(item.get("free_unit_price_excl_vat"))
    extra_charge = as_num(item.get("extra_charge"))
    unit_price_excl_vat = as_num(item.get("unit_price_excl_vat"))
    total_excl_vat = as_num(item.get("total_excl_vat"))
    vat_amount = as_num(item.get("vat_amount"))
    total_incl_vat = as_num(item.get("total_incl_vat"))
    vat_rate = as_rate(item.get("vat_rate"))

    ctx.try_correct_numeric(
        item,
        "total_excl_vat",
        [
            ("quantity * unit_price_excl_vat",
             (q * unit_price_excl_vat)
             if non_negative(q) and non_negative(unit_price_excl_vat)
             else None),
            ("total_incl_vat - vat_amount",
             (total_incl_vat - vat_amount)
             if total_incl_vat is not None and vat_amount is not None and total_incl_vat >= vat_amount >= 0
             else None),
        ],
        "item",
        idx,
    )

    ctx.try_correct_numeric(
        item,
        "unit_price_excl_vat",
        [
            ("free_unit_price_excl_vat + extra_charge",
             (free_unit_price_excl_vat + extra_charge)
             if non_negative(free_unit_price_excl_vat) and non_negative(extra_charge)
             else None),
            ("total_excl_vat / quantity",
             (total_excl_vat / q)
             if non_negative(total_excl_vat) and non_negative(q) and q > 0
             else None),
        ],
        "item",
        idx,
    )

    ctx.try_correct_numeric(
        item,
        "vat_amount",
        [
            ("total_incl_vat - total_excl_vat",
             (total_incl_vat - total_excl_vat)
             if total_incl_vat is not None and total_excl_vat is not None and total_incl_vat >= total_excl_vat >= 0
             else None),
            ("total_excl_vat * vat_rate",
             (total_excl_vat * vat_rate)
             if non_negative(total_excl_vat) and vat_rate is not None and vat_rate >= 0
             else None),
        ],
        "item",
        idx,
    )

    q = as_num(item.get("quantity"))
    free_unit_price_excl_vat = as_num(item.get("free_unit_price_excl_vat"))
    extra_charge = as_num(item.get("extra_charge"))
    unit_price_excl_vat = as_num(item.get("unit_price_excl_vat"))
    total_excl_vat = as_num(item.get("total_excl_vat"))
    vat_amount = as_num(item.get("vat_amount"))
    total_incl_vat = as_num(item.get("total_incl_vat"))

    if unit_price_excl_vat is None and non_negative(free_unit_price_excl_vat) and non_negative(extra_charge):
        unit_price_excl_vat = free_unit_price_excl_vat + extra_charge
        ctx.set_missing_numeric(
            item,
            "unit_price_excl_vat",
            unit_price_excl_vat,
            "free_unit_price_excl_vat + extra_charge",
            "item",
            idx,
        )

    if total_excl_vat is None and non_negative(q) and non_negative(unit_price_excl_vat):
        total_excl_vat = q * unit_price_excl_vat
        ctx.set_missing_numeric(
            item,
            "total_excl_vat",
            total_excl_vat,
            "quantity * unit_price_excl_vat",
            "item",
            idx,
        )

    if (
        vat_amount is None
        and total_incl_vat is not None
        and total_excl_vat is not None
        and total_incl_vat >= total_excl_vat >= 0
    ):
        vat_amount = total_incl_vat - total_excl_vat
        ctx.set_missing_numeric(
            item,
            "vat_amount",
            vat_amount,
            "total_incl_vat - total_excl_vat",
            "item",
            idx,
        )

    if total_incl_vat is None and non_negative(total_excl_vat) and non_negative(vat_amount):
        total_incl_vat = total_excl_vat + vat_amount
        ctx.set_missing_numeric(
            item,
            "total_incl_vat",
            total_incl_vat,
            "total_excl_vat + vat_amount",
            "item",
            idx,
        )
