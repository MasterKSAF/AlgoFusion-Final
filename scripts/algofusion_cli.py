from __future__ import annotations

import sys
from pathlib import Path
from pprint import pformat

import typer
from rich.console import Console
from rich.table import Table

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = PROJECT_ROOT / "workers" / "OCR-Sergei" / "PIPELINE_V2"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from shared.config.settings import get_settings  # noqa: E402
from shared.resources import get_resource_registry  # noqa: E402
from shared.utils.fuzzy import best_match  # noqa: E402

app = typer.Typer(help="Algofusion operational CLI")
console = Console()


@app.command("settings-summary")
def settings_summary() -> None:
    settings = get_settings()
    table = Table(title="Algofusion Settings")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    for key in (
        "pipeline_v2_queue",
        "shared_files_path",
        "external_monitor_path",
        "monitor_interval",
        "pipeline_mode",
        "log_level",
    ):
        table.add_row(key, str(getattr(settings, key)))
    console.print(table)


@app.command("show-resource")
def show_resource(name: str, key: str = "values") -> None:
    registry = get_resource_registry()
    payload = registry.load_dictionary(name)
    console.print(pformat(payload))
    if key in payload and isinstance(payload[key], list):
        console.print(f"[bold green]{name}[/bold green] count: {len(payload[key])}")


@app.command("fuzzy-match")
def fuzzy_match(candidate: str, dictionary: str = "units", threshold: float = 92.0) -> None:
    registry = get_resource_registry()
    choices = registry.list_dictionary_values(dictionary)
    result = best_match(candidate, choices, threshold=threshold)
    table = Table(title="Fuzzy Match Result")
    table.add_column("Candidate")
    table.add_column("Best value")
    table.add_column("Score")
    table.add_column("Accepted")
    table.add_row(candidate, str(result.value), f"{result.score:.2f}", str(result.accepted))
    console.print(table)


@app.command("smoke-pipeline-v2")
def smoke_pipeline_v2(
    input_path: Path,
    output_dir: Path,
    force_doc_type: str | None = None,
    max_pages: int = 0,
) -> None:
    from src.modules.runtime_run_standard import run_job_pipeline_v2

    summary = run_job_pipeline_v2(
        input_path=input_path,
        base_dir=output_dir,
        max_pages=max_pages or None,
        force_doc_type=force_doc_type,
    )
    console.print(summary)


@app.command("smoke-precomputed-v2")
def smoke_precomputed_v2(
    input_path: Path,
    precomputed_dir: Path,
    output_dir: Path,
    force_doc_type: str | None = None,
) -> None:
    from run_pipeline_v2_precomputed_smoke import _discover_precomputed_pages
    from src.modules.runtime_run_precomputed import run_job_pipeline_v2_from_precomputed

    page_specs, header_ocr_by_page = _discover_precomputed_pages(precomputed_dir.resolve())
    summary = run_job_pipeline_v2_from_precomputed(
        input_path=input_path.resolve(),
        base_dir=output_dir.resolve(),
        page_specs=page_specs,
        header_ocr_by_page=header_ocr_by_page,
        force_doc_type=force_doc_type,
    )
    console.print(summary)


if __name__ == "__main__":
    app()
