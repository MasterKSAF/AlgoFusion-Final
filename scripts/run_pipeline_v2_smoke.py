from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = PROJECT_ROOT / "workers" / "OCR-Sergei" / "PIPELINE_V2"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from shared.utils.json_utils import json_dumps  # noqa: E402
from src.modules.runtime_run_standard import run_job_pipeline_v2  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python scripts/run_pipeline_v2_smoke.py <input_path> <output_dir> [force_doc_type]")
    input_path = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    force_doc_type = sys.argv[3] if len(sys.argv) > 3 else None
    summary = run_job_pipeline_v2(
        input_path=input_path,
        base_dir=output_dir,
        force_doc_type=force_doc_type,
    )
    print(json_dumps(summary, indent=2))


if __name__ == "__main__":
    main()
