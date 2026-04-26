from __future__ import annotations

import json
from pathlib import Path

from api.algofusion_api.services import ArtifactService


def _write_final_json(root: Path, doc_name: str, payload: dict) -> None:
    target = root / doc_name / "data" / "final_json"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{doc_name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_detect_run_root_prefers_largest_artifact_set(tmp_path: Path) -> None:
    small = tmp_path / "small_run"
    large = tmp_path / "large_run"
    _write_final_json(small, "Doc_1", {"document_type": "invoice", "supplier": {}, "customer": {}, "items": []})
    _write_final_json(large, "Doc_1", {"document_type": "invoice", "supplier": {}, "customer": {}, "items": []})
    _write_final_json(large, "Doc_2", {"document_type": "invoice", "supplier": {}, "customer": {}, "items": []})

    assert ArtifactService._detect_run_root(tmp_path) == large.resolve()


def test_document_fields_fix_mojibake_and_count_review_states(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    _write_final_json(
        run_root,
        "Waybill_1",
        {
            "document_type": "РўРћР’РђР РќРђРЇ РќРђРљР›РђР”РќРђРЇ",
            "sender": {"tax_id": None},
            "receiver": {"tax_id": "проверить поле"},
            "items": [],
            "totals": {},
        },
    )
    service = ArtifactService(tmp_path, run_root)

    doc = service.get_document("Waybill_1")

    assert doc is not None
    assert doc["document_type"] == "waybill"
    assert doc["null_count"] == 1
    assert doc["review_count"] == 1
    assert doc["ready_to_export"] is False
    assert doc["fields"][0]["value"] == "ТОВАРНАЯ НАКЛАДНАЯ"


def test_review_draft_updates_effective_export_readiness(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    _write_final_json(
        run_root,
        "Waybill_2",
        {
            "document_type": "ТОВАРНАЯ НАКЛАДНАЯ",
            "sender": {"tax_id": None},
            "receiver": {"tax_id": "проверить поле"},
            "items": [{"line_number": 1, "unit": "шт"}],
            "totals": {"grand_total": 10},
        },
    )
    service = ArtifactService(tmp_path, run_root)

    result = service.save_review_draft(
        "Waybill_2",
        {
            "sender.tax_id": "690667789",
            "receiver.tax_id": "193716061",
        },
    )
    doc = service.get_document("Waybill_2")

    assert result is not None
    assert result["field_count"] == 2
    assert doc is not None
    assert doc["null_count"] == 0
    assert doc["review_count"] == 0
    assert doc["ready_to_export"] is True
    sender_tax = next(field for field in doc["fields"] if field["path"] == "sender.tax_id")
    assert sender_tax["has_draft"] is True
    assert sender_tax["effective_value"] == "690667789"
    assert sender_tax["effective_state"] == "ok"


def test_artifact_path_resolution_blocks_traversal(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    _write_final_json(run_root, "Doc_1", {"document_type": "invoice", "supplier": {}, "customer": {}, "items": []})
    service = ArtifactService(tmp_path, run_root)

    assert service.resolve_artifact_path("Doc_1", "../outside.json") is None
