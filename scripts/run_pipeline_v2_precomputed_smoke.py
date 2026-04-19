from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = PROJECT_ROOT / "workers" / "OCR-Sergei" / "PIPELINE_V2"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from shared.utils.json_utils import json_dumps  # noqa: E402
from src.modules.runtime_run_precomputed import run_job_pipeline_v2_from_precomputed  # noqa: E402


def _discover_precomputed_pages(precomputed_dir: Path) -> tuple[list[dict[str, str | int]], dict[str, dict]]:
    roi_root = precomputed_dir / "final_rebuilt_auto" / "_clean_page_plus_roi_json"
    debug_pages_root = precomputed_dir / "_pipeline_v2_debug" / "pages"
    page_specs: list[dict[str, str | int]] = []
    header_ocr_by_page: dict[str, dict] = {}

    for page_dir in sorted(path for path in roi_root.iterdir() if path.is_dir()):
        page_id = page_dir.name
        clean_png = page_dir / f"{page_id}__clean.png"
        roi_coords = page_dir / f"{page_id}__roi_coords.json"
        raw_ocr_candidates = [
            page_dir / f"{page_id}__ocr_raw.json",
            debug_pages_root / page_id / f"{page_id}__ocr_raw.json",
        ]
        raw_ocr = next((path for path in raw_ocr_candidates if path.exists()), None)
        if raw_ocr is None:
            raise FileNotFoundError(f"Missing precomputed raw OCR for {page_id}")

        header_ocr = page_dir / f"{page_id}__waybill_header_ocr.json"
        if header_ocr.exists():
            header_ocr_by_page[page_id] = json.loads(header_ocr.read_text(encoding="utf-8"))

        page_no = int(page_id.rsplit("__p", 1)[1])
        page_specs.append(
            {
                "page_id": page_id,
                "page_no": page_no,
                "clean_png": str(clean_png),
                "roi_coords": str(roi_coords),
                "raw_ocr": str(raw_ocr),
            }
        )

    return page_specs, header_ocr_by_page


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(
            "Usage: python scripts/run_pipeline_v2_precomputed_smoke.py <input_path> <precomputed_dir> <output_dir> [force_doc_type]"
        )
    input_path = Path(sys.argv[1]).resolve()
    precomputed_dir = Path(sys.argv[2]).resolve()
    output_dir = Path(sys.argv[3]).resolve()
    force_doc_type = sys.argv[4] if len(sys.argv) > 4 else None

    page_specs, header_ocr_by_page = _discover_precomputed_pages(precomputed_dir)
    summary = run_job_pipeline_v2_from_precomputed(
        input_path=input_path,
        base_dir=output_dir,
        page_specs=page_specs,
        header_ocr_by_page=header_ocr_by_page,
        force_doc_type=force_doc_type,
    )
    print(json_dumps(summary, indent=2))


if __name__ == "__main__":
    main()
