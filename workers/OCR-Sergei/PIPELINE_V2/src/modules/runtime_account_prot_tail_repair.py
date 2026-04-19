from __future__ import annotations

import copy
import re
from typing import Any

from src.modules.runtime_numbers import to_float_soft
from src.modules.runtime_text_quality import _clean_inline_text


def repair_shifted_account_prot_item(item: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(item)
    unit = _clean_inline_text(out.get("unit")) or ""
    vat_rate = _clean_inline_text(out.get("vat_rate")) or ""
    extra_charge = to_float_soft(out.get("extra_charge"))
    vat_amount = to_float_soft(out.get("vat_amount"))
    total_incl = to_float_soft(out.get("total_incl_vat"))
    total_excl = to_float_soft(out.get("total_excl_vat"))

    looks_shifted = (
        bool(unit and len(unit) > 8)
        and extra_charge is not None
        and total_excl is not None
        and abs(extra_charge - total_excl) < 0.01
        and bool(re.fullmatch(r"\d+(?:[.,]\d+)?%", vat_rate))
        and vat_amount is not None
        and total_incl is not None
        and vat_amount >= 10
        and total_incl < total_excl
    )
    if not looks_shifted:
        return out

    out["unit"] = "шт"
    out["free_unit_price_excl_vat"] = extra_charge
    out["extra_charge"] = None
    out["unit_price_excl_vat"] = extra_charge
    out["total_excl_vat"] = extra_charge
    out["vat_rate"] = f"{int(round(vat_amount))}%"
    out["vat_amount"] = total_incl
    out["total_incl_vat"] = round(extra_charge + total_incl, 2)
    return out
