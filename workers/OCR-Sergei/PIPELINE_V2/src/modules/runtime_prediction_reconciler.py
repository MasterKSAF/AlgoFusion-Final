from __future__ import annotations

import copy

from src.modules.runtime_prediction_amount_recovery import reconcile_document_amounts


def build_pred_reconciled(pred_normalized):
    pred_reconciled = copy.deepcopy(pred_normalized)

    for doc_type, docs in pred_reconciled.items():
        if not isinstance(docs, dict):
            continue

        for file_key, payload in docs.items():
            if not isinstance(payload, dict):
                continue

            if doc_type in {"invoice", "waybill", "Account-protocol"}:
                reconcile_type = {
                    "invoice": "invoice",
                    "waybill": "waybill",
                    "Account-protocol": "account_prot",
                }[doc_type]

                reconcile_document_amounts(reconcile_type, payload)

    return pred_reconciled

