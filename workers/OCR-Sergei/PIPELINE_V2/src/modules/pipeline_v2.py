from __future__ import annotations

import time

from src.config import config
from src.logger import get_logger
from src.models.file import FileJob, FileType
from src.modules.runtime_run_standard import run_job_pipeline_v2

logger = get_logger(__name__)


class PipelineV2Module:
    name = "pipeline_v2"
    description = "Experimental end-to-end pipeline v2"
    version = "1.0.0"
    supported_file_types = {FileType.IMAGE, FileType.PDF}

    def process(self, job: FileJob) -> bool:
        start_time = time.time()

        if job.file_type not in self.supported_file_types:
            error = f"Unsupported file type: {job.file_type.value}"
            logger.warning(error)
            job.fail_module(self.name, error)
            return False

        input_path = job.get_original_path(str(config.shared_files_dir))
        base_dir = job.get_base_path(str(config.shared_files_dir))
        if not input_path.exists():
            error = f"Input file not found: {input_path}"
            logger.error(error)
            job.fail_module(self.name, error)
            return False

        try:
            max_pages = job.config.get("max_pages")
            if max_pages is None:
                max_pages = config.max_pages
            max_pages = int(max_pages) if max_pages else None

            force_doc_type = job.config.get("force_doc_type") or config.force_doc_type
            summary = run_job_pipeline_v2(
                input_path=input_path,
                base_dir=base_dir,
                max_pages=max_pages,
                force_doc_type=force_doc_type,
            )
            duration = time.time() - start_time
            job.metadata.setdefault("pipeline_v2", {})
            job.metadata["pipeline_v2"].update(
                {
                    "base_dir": str(base_dir),
                    "input_path": str(input_path),
                    "runtime_module": "src.modules.runtime_run_standard",
                    "helper_path": str(config.helper_path),
                    "summary": summary,
                }
            )
            job.add_to_history("pipeline_v2_process", self.name, True, duration=duration)
            logger.info("Pipeline v2 completed: segments=%s pages=%s", summary.get("segment_count"), summary.get("page_count"))
            return True
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception("Pipeline v2 exception: %s", exc)
            job.fail_module(self.name, str(exc))
            job.add_to_history("pipeline_v2_process", self.name, False, error=str(exc), duration=duration)
            return False
