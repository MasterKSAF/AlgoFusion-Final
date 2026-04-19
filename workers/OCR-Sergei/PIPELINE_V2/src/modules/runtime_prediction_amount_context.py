from __future__ import annotations

from src.modules.runtime_prediction_amount_helpers import (
    as_num,
    as_rate,
    is_missing,
    maybe_round_money,
    non_negative,
    norm_num,
    parse_money_words_amount,
    rubles_part,
    safe_div,
    sum_item_field,
)

from src.modules.runtime_prediction_amount_item_rules import (
    recover_account_protocol_item_amounts,
    recover_invoice_item_amounts,
    recover_waybill_item_amounts,
)
from src.modules.runtime_prediction_amount_total_rules import reconcile_document_totals

class PredictionAmountRecoveryContext:
    def __init__(self, doc_type, payload, tol=0.02):
        self.doc_type = doc_type
        self.payload = payload
        self.tol = tol
        self.changes = []
        self.warnings = []
        self.totals = {}
        self.total_map = {}
        self.words_total_map = {}
        self.derived_totals = {}
        self.parsed_words_totals = {}

    def close_enough(self, a, b):
        a = as_num(a)
        b = as_num(b)
        if a is None or b is None:
            return False
        return abs(a - b) <= self.tol

    def set_missing_numeric(self, obj, field, value, source, scope, row_idx=None):
        if value is None:
            return
        if not is_missing(obj.get(field)):
            return
        obj[field] = norm_num(value)
        record = {
            "scope": scope,
            "field": field,
            "value": obj[field],
            "source": source,
            "kind": "derived",
        }
        if row_idx is not None:
            record["row_index"] = row_idx
        self.changes.append(record)

    def set_corrected_numeric(self, obj, field, old_value, new_value, source, scope, row_idx=None, support_count=None):
        if new_value is None:
            return
        obj[field] = norm_num(new_value)
        record = {
            "scope": scope,
            "field": field,
            "value": obj[field],
            "previous_value": norm_num(old_value),
            "source": source,
            "kind": "corrected",
        }
        if support_count is not None:
            record["support_count"] = support_count
        if row_idx is not None:
            record["row_index"] = row_idx
        self.changes.append(record)

    def add_warning(self, field, extracted, derived, scope, row_idx=None, source=None):
        record = {
            "scope": scope,
            "field": field,
            "extracted": extracted,
            "derived": norm_num(derived),
        }
        if source:
            record["source"] = source
        if row_idx is not None:
            record["row_index"] = row_idx
        self.warnings.append(record)

    def consensus_from_supports(self, supports, min_count=2):
        good = []
        for label, value in supports:
            num = as_num(value)
            if num is None:
                continue
            good.append((label, num))

        if len(good) < min_count:
            return None, []

        best_value = None
        best_labels = []

        for i, (label_i, value_i) in enumerate(good):
            labels = [label_i]
            values = [value_i]

            for j, (label_j, value_j) in enumerate(good):
                if i == j:
                    continue
                if self.close_enough(value_i, value_j):
                    labels.append(label_j)
                    values.append(value_j)

            uniq_labels = []
            for lbl in labels:
                if lbl not in uniq_labels:
                    uniq_labels.append(lbl)

            if len(uniq_labels) >= min_count and len(uniq_labels) > len(best_labels):
                best_labels = uniq_labels
                best_value = sum(values) / len(values)

        if len(best_labels) < min_count:
            return None, []

        return norm_num(best_value), best_labels

    def looks_like_decimal_shift(self, raw_value, target_value):
        raw = as_num(raw_value)
        target = as_num(target_value)
        if raw is None or target is None:
            return False
        if self.close_enough(raw, target):
            return False

        for factor in (10, 100, 1000):
            if self.close_enough(raw / factor, target):
                return True
            if self.close_enough(raw * factor, target):
                return True

        return False

    def try_correct_numeric(self, obj, field, supports, scope, row_idx=None):
        current = as_num(obj.get(field))
        if current is None:
            return False

        target, labels = self.consensus_from_supports(supports, min_count=2)
        if target is None:
            return False

        if self.close_enough(current, target):
            return False

        if not self.looks_like_decimal_shift(current, target):
            return False

        self.set_corrected_numeric(
            obj,
            field,
            current,
            target,
            " & ".join(labels),
            scope,
            row_idx=row_idx,
            support_count=len(labels),
        )
        return True

    def total_supports_for_field(self, total_field):
        supports = []

        derived_value = self.derived_totals.get(total_field)
        if derived_value is not None:
            supports.append((f"sum(items.{self.total_map.get(total_field)})", derived_value))

        if total_field in self.parsed_words_totals:
            supports.append((f"parsed({next(k for k, v in self.words_total_map.items() if v == total_field)})", self.parsed_words_totals[total_field]))

        subtotal_no_disc = as_num(self.totals.get("subtotal_no_disc_incl_vat"))
        total_disc = as_num(self.totals.get("total_disc_amount"))
        subtotal_with_disc = as_num(self.totals.get("subtotal_with_disc_excl_vat"))
        vat_total = as_num(self.totals.get("vat_amount"))
        total_with_disc = as_num(self.totals.get("total_with_disc_incl_vat"))
        subtotal_excl = as_num(self.totals.get("subtotal_excl_vat"))
        total_incl = as_num(self.totals.get("total_incl_vat"))
        cost_total = as_num(self.totals.get("cost_total"))
        cost_with_vat_total = as_num(self.totals.get("cost_with_vat_total"))

        if self.doc_type == "invoice":
            if total_field == "total_with_disc_incl_vat":
                if non_negative(subtotal_with_disc) and non_negative(vat_total):
                    supports.append(("subtotal_with_disc_excl_vat + vat_amount", subtotal_with_disc + vat_total))
                if non_negative(subtotal_no_disc) and non_negative(total_disc) and subtotal_no_disc >= total_disc:
                    supports.append(("subtotal_no_disc_incl_vat - total_disc_amount", subtotal_no_disc - total_disc))
            elif total_field == "subtotal_no_disc_incl_vat":
                if non_negative(total_with_disc) and non_negative(total_disc):
                    supports.append(("total_with_disc_incl_vat + total_disc_amount", total_with_disc + total_disc))
            elif total_field == "total_disc_amount":
                if non_negative(subtotal_no_disc) and non_negative(total_with_disc) and subtotal_no_disc >= total_with_disc:
                    supports.append(("subtotal_no_disc_incl_vat - total_with_disc_incl_vat", subtotal_no_disc - total_with_disc))
            elif total_field == "subtotal_with_disc_excl_vat":
                if non_negative(total_with_disc) and non_negative(vat_total) and total_with_disc >= vat_total:
                    supports.append(("total_with_disc_incl_vat - vat_amount", total_with_disc - vat_total))
            elif total_field == "vat_amount":
                if non_negative(total_with_disc) and non_negative(subtotal_with_disc) and total_with_disc >= subtotal_with_disc:
                    supports.append(("total_with_disc_incl_vat - subtotal_with_disc_excl_vat", total_with_disc - subtotal_with_disc))
        elif self.doc_type == "waybill":
            if total_field == "cost_with_vat_total":
                if non_negative(cost_total) and non_negative(vat_total):
                    supports.append(("cost_total + vat_total", cost_total + vat_total))
            elif total_field == "vat_total":
                if non_negative(cost_with_vat_total) and non_negative(cost_total) and cost_with_vat_total >= cost_total:
                    supports.append(("cost_with_vat_total - cost_total", cost_with_vat_total - cost_total))
        elif self.doc_type == "account_prot":
            if total_field == "total_incl_vat":
                if non_negative(subtotal_excl) and non_negative(vat_total):
                    supports.append(("subtotal_excl_vat + vat_amount", subtotal_excl + vat_total))
            elif total_field == "vat_amount":
                if non_negative(total_incl) and non_negative(subtotal_excl) and total_incl >= subtotal_excl:
                    supports.append(("total_incl_vat - subtotal_excl_vat", total_incl - subtotal_excl))

        return supports

    def run(self):
        payload = self.payload
        items = payload.get("items")
        totals = payload.get("totals")
        self.changes = []
        self.warnings = []

        if not isinstance(items, list):
            items = []
        if not isinstance(totals, dict):
            totals = {}
            payload["totals"] = totals

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            if self.doc_type == "invoice":
                recover_invoice_item_amounts(self, item, idx)
            elif self.doc_type == "waybill":
                recover_waybill_item_amounts(self, item, idx)
            elif self.doc_type == "account_prot":
                recover_account_protocol_item_amounts(self, item, idx)

        reconcile_document_totals(self, items, totals)

        payload["_reconciliation"] = {
            "changes": self.changes,
            "warnings": self.warnings,
        }
        return payload
