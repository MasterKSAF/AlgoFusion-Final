from __future__ import annotations


def infer_doc_type_from_name(file_name: str) -> str:
    normalized = str(file_name or "").lower().replace("\\", "/")
    if "waybill" in normalized or "наклад" in normalized:
        return "waybill"
    if "invoice" in normalized or "инвойс" in normalized:
        return "invoice"
    if "account_prot" in normalized or "account-prot" in normalized or "account prot" in normalized:
        return "account_prot"
    if "payment_order" in normalized or "payment-order" in normalized or "payment order" in normalized:
        return "payment_order"
    return "unknown"


def choose_resolved_doc_type(
    *,
    declared: str | None,
    hard_type: str | None,
    detected_type: str | None,
) -> str:
    declared_type = declared or "unknown"
    if hard_type and detected_type and hard_type == detected_type:
        return hard_type
    if hard_type and declared_type in {"unknown", detected_type, None}:
        return hard_type
    if hard_type and hard_type in {"waybill", "payment_order", "account_prot"}:
        return hard_type
    if hard_type and declared_type == "unknown":
        return hard_type
    if declared_type != "unknown":
        return declared_type
    if detected_type:
        return detected_type
    if hard_type:
        return hard_type
    return "unknown"
