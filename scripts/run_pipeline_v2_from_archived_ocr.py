from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = PROJECT_ROOT / "workers" / "OCR-Sergei" / "PIPELINE_V2"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from src.modules.runtime_common import page_no_from_page_id  # noqa: E402
from src.modules.runtime_run_precomputed import run_job_pipeline_v2_from_precomputed  # noqa: E402


DEFAULT_RAW_OCR = PROJECT_ROOT / "shared" / "files" / "_no_ocr_inputs_136" / "all_pages_ocr_raw.json"
DEFAULT_HEADER_OCR = (
    PROJECT_ROOT / "shared" / "files" / "_no_ocr_inputs_136" / "all_pages_waybill_header_ocr.json"
)
DEFAULT_INPUT_ROOT = Path(r"C:\Users\Misha\Documents\Docs\Новая папка")
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "shared" / "files" / "_no_ocr_runs_136"

_PLACEHOLDER_CLEAN_PNG = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="
)


def _doc_stem_from_page_id(page_id: str) -> str:
    return page_id.rsplit("__p", 1)[0] if "__p" in page_id else page_id


def _normalize_name(value: str) -> str:
    value = value.replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9_]+", "", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_").lower()


def _load_json_payload(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_payloads_from_zip(zip_path: Path, aggregate_suffix: str, page_suffix: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path) as zf:
        names = [name for name in zf.namelist() if name and not name.endswith("/")]
        aggregate_names = [name for name in names if Path(name).name == aggregate_suffix]
        if aggregate_names:
            for name in aggregate_names:
                with zf.open(name) as handle:
                    data = json.loads(handle.read().decode("utf-8"))
                if isinstance(data, list):
                    payloads.extend(item for item in data if isinstance(item, dict))
            return payloads

        for name in names:
            if not Path(name).name.endswith(page_suffix):
                continue
            with zf.open(name) as handle:
                data = json.loads(handle.read().decode("utf-8"))
            if isinstance(data, dict):
                payloads.append(data)
    return payloads


def _load_raw_payloads(path_arg: str) -> list[dict[str, Any]]:
    raw_path = Path(path_arg)
    if raw_path.suffix.lower() == ".zip":
        return _load_payloads_from_zip(raw_path, "all_pages_ocr_raw.json", "__ocr_raw.json")
    data = _load_json_payload(raw_path)
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _load_header_payloads(path_arg: str) -> list[dict[str, Any]]:
    if not path_arg:
        return []
    header_path = Path(path_arg)
    if not header_path.exists():
        return []
    if header_path.suffix.lower() == ".zip":
        return _load_payloads_from_zip(
            header_path,
            "all_pages_waybill_header_ocr.json",
            "__waybill_header_ocr.json",
        )
    data = _load_json_payload(header_path)
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _build_original_index(input_root: Path) -> dict[str, Path]:
    return {_normalize_name(path.stem): path for path in input_root.glob("*.pdf")}


def _resolve_input_path(doc_stem: str, input_index: dict[str, Path]) -> Path:
    key = _normalize_name(doc_stem)
    if key in input_index:
        return input_index[key]
    raise FileNotFoundError(f"Original PDF not found for {doc_stem}")


def _ensure_placeholder_clean_png(output_root: Path) -> Path:
    staging_root = output_root / "_staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    placeholder = staging_root / "__placeholder_clean.png"
    if not placeholder.exists():
        placeholder.write_bytes(base64.b64decode(_PLACEHOLDER_CLEAN_PNG))
    return placeholder


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AlgoFusion2 pipeline without OCR service using archived raw OCR/header OCR payloads."
    )
    parser.add_argument("--raw-ocr", default=str(DEFAULT_RAW_OCR), help="Path to raw OCR json or zip.")
    parser.add_argument(
        "--header-ocr",
        default=str(DEFAULT_HEADER_OCR),
        help="Path to waybill header OCR json or zip.",
    )
    parser.add_argument(
        "--input-root",
        default=str(DEFAULT_INPUT_ROOT),
        help="Directory with original PDFs.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Directory where per-document pipeline outputs will be written.",
    )
    parser.add_argument("--doc", action="append", dest="docs", help="Specific document stem to run.")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on number of documents.")
    parser.add_argument("--force-doc-type", default="", help="Optional forced document type.")
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately on the first document error.",
    )
    args = parser.parse_args()

    input_root = Path(args.input_root).resolve()
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    raw_payloads = _load_raw_payloads(args.raw_ocr)
    header_payloads = _load_header_payloads(args.header_ocr)
    raw_by_page = {item["page_id"]: item for item in raw_payloads if item.get("page_id")}
    header_by_page = {item["page_id"]: item for item in header_payloads if item.get("page_id")}

    doc_names = sorted({_doc_stem_from_page_id(page_id) for page_id in raw_by_page})
    if args.docs:
        requested = {_normalize_name(name) for name in args.docs}
        doc_names = [name for name in doc_names if _normalize_name(name) in requested]
    if args.limit > 0:
        doc_names = doc_names[: args.limit]

    input_index = _build_original_index(input_root)
    placeholder_clean = _ensure_placeholder_clean_png(output_root)

    results: list[dict[str, Any]] = []
    for doc_stem in doc_names:
        try:
            page_ids = sorted(
                [
                    page_id
                    for page_id in raw_by_page
                    if _normalize_name(_doc_stem_from_page_id(page_id)) == _normalize_name(doc_stem)
                ],
                key=page_no_from_page_id,
            )
            page_specs = [
                {
                    "page_id": page_id,
                    "page_no": page_no_from_page_id(page_id),
                    "clean_png": str(placeholder_clean),
                    "raw_payload": raw_by_page[page_id],
                }
                for page_id in page_ids
            ]
            input_path = _resolve_input_path(doc_stem, input_index)
            base_dir = output_root / doc_stem
            summary = run_job_pipeline_v2_from_precomputed(
                input_path=input_path,
                base_dir=base_dir,
                page_specs=page_specs,
                header_ocr_by_page=header_by_page,
                force_doc_type=args.force_doc_type or None,
            )
            results.append(
                {
                    "doc_stem": doc_stem,
                    "status": "ok",
                    "input_path": str(input_path),
                    "base_dir": str(base_dir),
                    "pages": len(page_specs),
                    "summary": summary,
                }
            )
            print(f"[OK] {doc_stem} -> {base_dir}")
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "doc_stem": doc_stem,
                    "status": "error",
                    "error": str(exc),
                }
            )
            print(f"[ERROR] {doc_stem}: {exc}")
            if args.fail_fast:
                break

    summary_path = output_root / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "raw_ocr": str(Path(args.raw_ocr).resolve()),
                "header_ocr": str(Path(args.header_ocr).resolve()) if args.header_ocr else "",
                "input_root": str(input_root),
                "output_root": str(output_root),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
