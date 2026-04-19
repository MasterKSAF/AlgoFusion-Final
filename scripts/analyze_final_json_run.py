from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REVIEW_MARKER = "проверить поле"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _doc_type_from_payload(payload: Any) -> tuple[str, Any]:
    if isinstance(payload, dict):
        if "invoice" in payload and isinstance(payload["invoice"], dict) and payload["invoice"]:
            return "invoice", next(iter(payload["invoice"].values()))
        if "payment_order" in payload and isinstance(payload["payment_order"], dict) and payload["payment_order"]:
            return "payment_order", next(iter(payload["payment_order"].values()))
        if "account_prot" in payload and isinstance(payload["account_prot"], dict) and payload["account_prot"]:
            return "account_prot", next(iter(payload["account_prot"].values()))
        if "document_type" in payload or "items" in payload:
            return "waybill", payload
    return "unknown", payload


def _leaf_stats(value: Any, prefix: str = "") -> dict[str, Any]:
    totals = {
        "field_count": 0,
        "review_count": 0,
        "null_count": 0,
        "review_paths": Counter(),
    }

    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            child_stats = _leaf_stats(child, child_prefix)
            totals["field_count"] += child_stats["field_count"]
            totals["review_count"] += child_stats["review_count"]
            totals["null_count"] += child_stats["null_count"]
            totals["review_paths"].update(child_stats["review_paths"])
        return totals

    if isinstance(value, list):
        for idx, child in enumerate(value):
            child_prefix = f"{prefix}[*]" if prefix.endswith("]") else f"{prefix}[*]" if prefix else "[*]"
            child_stats = _leaf_stats(child, child_prefix)
            totals["field_count"] += child_stats["field_count"]
            totals["review_count"] += child_stats["review_count"]
            totals["null_count"] += child_stats["null_count"]
            totals["review_paths"].update(child_stats["review_paths"])
        return totals

    totals["field_count"] = 1
    if value is None:
        totals["null_count"] = 1
        return totals
    if isinstance(value, str) and REVIEW_MARKER in value.lower():
        totals["review_count"] = 1
        totals["review_paths"][prefix] += 1
    return totals


def _normalize_path(path: str) -> str:
    return path.replace("[*].[*]", "[*]")


def analyze_run(run_root: Path) -> dict[str, Any]:
    summary_path = run_root / "summary.json"
    summary_payload = _load_json(summary_path) if summary_path.exists() else {}
    doc_type_by_stem: dict[str, str] = {}
    for result in summary_payload.get("results", []):
        doc_stem = result.get("doc_stem")
        final_outputs = ((result.get("summary") or {}).get("final_outputs")) or []
        if doc_stem and final_outputs:
            doc_type_by_stem[doc_stem] = final_outputs[0].get("doc_type") or "unknown"

    overall = {
        "documents_total": 0,
        "documents_without_review": 0,
        "fields_total": 0,
        "fields_without_review": 0,
        "review_fields": 0,
        "null_fields": 0,
    }
    by_type: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "documents_total": 0,
            "documents_without_review": 0,
            "fields_total": 0,
            "fields_without_review": 0,
            "review_fields": 0,
            "null_fields": 0,
        }
    )
    review_hotspots: Counter[str] = Counter()
    top_docs: list[dict[str, Any]] = []

    for doc_dir in sorted(path for path in run_root.iterdir() if path.is_dir()):
        final_paths = sorted((doc_dir / "data" / "final_json").glob("*.json"))
        if not final_paths:
            continue
        raw_payload = _load_json(final_paths[0])
        doc_type, payload = _doc_type_from_payload(raw_payload)
        doc_type = doc_type_by_stem.get(doc_dir.name, doc_type)
        stats = _leaf_stats(payload)
        review_count = int(stats["review_count"])
        field_count = int(stats["field_count"])
        null_count = int(stats["null_count"])
        review_paths = Counter({_normalize_path(key): value for key, value in stats["review_paths"].items()})

        overall["documents_total"] += 1
        overall["fields_total"] += field_count
        overall["review_fields"] += review_count
        overall["fields_without_review"] += field_count - review_count
        overall["null_fields"] += null_count
        if review_count == 0:
            overall["documents_without_review"] += 1

        by_type[doc_type]["documents_total"] += 1
        by_type[doc_type]["fields_total"] += field_count
        by_type[doc_type]["review_fields"] += review_count
        by_type[doc_type]["fields_without_review"] += field_count - review_count
        by_type[doc_type]["null_fields"] += null_count
        if review_count == 0:
            by_type[doc_type]["documents_without_review"] += 1

        review_hotspots.update(review_paths)
        top_docs.append(
            {
                "doc_stem": doc_dir.name,
                "doc_type": doc_type,
                "review_fields": review_count,
                "field_count": field_count,
            }
        )

    for bucket in [overall, *by_type.values()]:
        documents_total = bucket["documents_total"] or 1
        fields_total = bucket["fields_total"] or 1
        bucket["documents_without_review_pct"] = round(bucket["documents_without_review"] * 100.0 / documents_total, 2)
        bucket["fields_without_review_pct"] = round(bucket["fields_without_review"] * 100.0 / fields_total, 2)

    top_docs.sort(key=lambda row: (-row["review_fields"], row["doc_stem"]))
    hotspot_rows = [
        {"path": path, "review_fields": count}
        for path, count in review_hotspots.most_common()
    ]

    return {
        "run_root": str(run_root),
        "overall": overall,
        "by_type": dict(sorted(by_type.items())),
        "top_review_docs": top_docs[:20],
        "review_hotspots": hotspot_rows[:200],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze final_json outputs for a run root.")
    parser.add_argument("run_root", help="Run root with per-document outputs and summary.json.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    analysis = analyze_run(run_root)
    output_text = json.dumps(analysis, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).resolve().write_text(output_text, encoding="utf-8")
    else:
        print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
