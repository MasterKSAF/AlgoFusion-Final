from __future__ import annotations

from src.modules import runtime_prediction_normalizer as normalizer


def test_normalizer_preserves_review_marker_scalars() -> None:
    marker = "проверить поле"

    assert normalizer.normalize_bool(marker) == marker
    assert normalizer.normalize_number(marker) == marker
    assert normalizer.normalize_percent(marker) == marker
    assert normalizer.normalize_date(marker) == marker
    assert normalizer.normalize_generic_text(marker) == marker


def test_normalize_pred_preserves_review_marker_nested_fields() -> None:
    marker = "проверить поле"
    normalized = normalizer.normalize_pred(
        {
            "invoice": {
                "totals": {"vat_rate": marker},
                "seller": {"name": marker},
                "items": [
                    {
                        "description": marker,
                        "quantity": marker,
                    }
                ],
            }
        }
    )

    invoice = normalized["invoice"]
    assert invoice["totals"]["vat_rate"] == marker
    assert invoice["seller"]["name"] == marker
    assert invoice["items"][0]["description"] == marker
    assert invoice["items"][0]["quantity"] == marker
