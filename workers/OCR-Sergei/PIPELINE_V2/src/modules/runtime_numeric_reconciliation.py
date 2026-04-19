from __future__ import annotations

from src.modules.runtime_invoice_numeric import (
    finalize_invoice_numeric_row,
    infer_invoice_rate_from_amounts,
    invoice_discount_total_triplet,
    invoice_no_discount_triplet,
)
from src.modules.runtime_numeric_common import (
    canonical_invoice_rate_text,
    has_numeric_review_marker,
    mark_linked_numeric_fields,
    parse_percent_number,
    rate_canonical_from_text,
    rate_value_from_canonical,
    rescale_small_money_to_reference,
    set_clean_number,
    snap_percent_to_canonical,
)
from src.modules.runtime_waybill_numeric import finalize_waybill_numeric_row, reconcile_waybill_item_vat_rate
