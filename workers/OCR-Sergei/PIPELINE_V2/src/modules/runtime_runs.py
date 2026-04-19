from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from src.modules.runtime_run_debug import run_multipage_debug_pipeline
from src.modules.runtime_run_precomputed import run_job_pipeline_v2_from_precomputed
from src.modules.runtime_run_standard import run_job_pipeline_v2, run_standard_output_pipeline


def import_helper_module(path: str | Path | None = None):
    helper_path = Path(path) if path else Path(__file__)
    spec = importlib.util.spec_from_file_location(helper_path.stem, helper_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
