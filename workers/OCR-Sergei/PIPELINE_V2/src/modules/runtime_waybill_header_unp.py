from __future__ import annotations

import re

from src.modules.runtime_document_parser_common import clean_text


def _waybill_extract_tax_id(text):
    if not text:
        return None
    m = re.search(r'(?<!\d)(\d{9})(?!\d)', text)
    return m.group(1) if m else None

def _cluster_axis(values, tol):
    if not values:
        return []

    values = sorted(values)
    groups = [[values[0]]]

    for v in values[1:]:
        if abs(v - groups[-1][-1]) <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])

    return [sum(g) / len(g) for g in groups]

def extract_waybill_unp_fields(regions):
    out = {
        "sender": {"tax_id": None},
        "receiver": {"tax_id": None},
        "payer": {"name": None, "address": None, "tax_id": None},
    }

    unp_regions = [r for r in regions if r.get("kind") == "unp_cell"]
    if not unp_regions:
        return out

    items = []
    widths = []

    for r in unp_regions:
        bbox = r.get("bbox") or [0, 0, 0, 0]
        x1, y1, x2, y2 = bbox
        text = clean_text(r.get("text"))
        widths.append(max(1, x2 - x1))

        items.append({
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "cx": (x1 + x2) / 2,
            "cy": (y1 + y2) / 2,
            "text": text,
            "tax_id": _waybill_extract_tax_id(text),
        })

    if not items:
        return out

    widths = sorted(widths)
    median_w = widths[len(widths) // 2] if widths else 100
    x_tol = max(40, int(median_w * 0.35))

    x_clusters = _cluster_axis([it["cx"] for it in items], tol=x_tol)
    if not x_clusters:
        return out

    cols = {i: [] for i in range(len(x_clusters))}
    for it in items:
        col_idx = min(range(len(x_clusters)), key=lambda i: abs(it["cx"] - x_clusters[i]))
        cols[col_idx].append(it)

    col_values = []
    for col_idx in sorted(cols):
        col_items = sorted(cols[col_idx], key=lambda z: (z["cy"], z["x1"]))

        val = next((z["tax_id"] for z in col_items if z["tax_id"]), None)
        if not val:
            merged = " ".join(z["text"] for z in col_items if z["text"])
            val = _waybill_extract_tax_id(merged)

        col_values.append(val)

    # 2 колонки: sender, receiver
    # 3 колонки: sender, payer, receiver
    if len(col_values) >= 1:
        out["sender"]["tax_id"] = col_values[0]
    if len(col_values) >= 2:
        if len(col_values) == 2:
            out["receiver"]["tax_id"] = col_values[1]
        else:
            out["payer"]["tax_id"] = col_values[1]
    if len(col_values) >= 3:
        out["receiver"]["tax_id"] = col_values[2]

    return out
