# monitor/file_monitor.py
"""Monitor an incoming directory and enqueue ready files for pipeline v2."""

from __future__ import annotations

import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set

from core.services.redis_client import get_redis_client
from shared.config.settings import get_settings
from shared.models.file import FileJob, FileStatus
from shared.utils.helpers import safe_mkdir
from shared.utils.logger import setup_logger

logger = setup_logger("monitor.file_monitor")


class FileMonitor:
    """Watch incoming files, copy originals, and create queue jobs."""

    MIN_FILE_SIZE = 1024
    FILE_STABLE_TIME = 2

    def __init__(
        self,
        external_path: Optional[str] = None,
        shared_path: Optional[str] = None,
        check_interval: Optional[int] = None,
    ):
        settings = get_settings()

        self.external_path = Path(external_path or settings.external_monitor_path)
        self.shared_path = Path(shared_path or settings.shared_files_path)
        self.check_interval = check_interval or settings.monitor_interval
        self.pipeline_mode = self._normalize_pipeline_mode(settings.pipeline_mode)
        self.pipeline_v2_queue = settings.pipeline_v2_queue or "files:pipeline_v2"
        self.processed_files: Set[str] = set()
        self.redis = get_redis_client()

        self._file_cache: dict[str, tuple[float, float, int]] = {}

        logger.info(
            "FileMonitor initialized: external=%s shared=%s interval=%ss pipeline_mode=%s",
            self.external_path,
            self.shared_path,
            self.check_interval,
            self.pipeline_mode,
        )

    @staticmethod
    def _normalize_pipeline_mode(value: Optional[str]) -> str:
        mode = (value or "v2").strip().lower()
        if mode in {"v2", "pipeline_v2", "main"}:
            return "v2"
        logger.warning("Unsupported PIPELINE_MODE=%s, defaulting to v2", value)
        return "v2"

    def _resolve_entry_queue(self) -> str:
        return self.pipeline_v2_queue

    def _resolve_first_module(self) -> str:
        return "pipeline_v2"

    def start(self) -> None:
        """Start the monitor loop."""
        logger.info("Starting FileMonitor for incoming path: %s", self.external_path)

        if not self._check_permissions():
            logger.error("Permission check failed; monitor will not start")
            return

        safe_mkdir(self.external_path, mode=0o755)
        safe_mkdir(self.shared_path, mode=0o755)

        iteration = 0
        while True:
            iteration += 1
            logger.info("Monitor scan iteration #%s", iteration)

            try:
                self.check_for_new_files()
                logger.debug("Sleeping for %ss before the next scan", self.check_interval)
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("FileMonitor stopped by user")
                break
            except Exception as exc:
                logger.error("Error in monitor loop: %s", exc, exc_info=True)
                time.sleep(self.check_interval)

    def _check_permissions(self) -> bool:
        """Check access by performing real directory and file operations."""
        try:
            safe_mkdir(self.external_path, mode=0o755)
            safe_mkdir(self.shared_path, mode=0o755)

            probe_dir = self.shared_path / ".monitor_probe"
            safe_mkdir(probe_dir, mode=0o755)
            probe_file = probe_dir / ".write_test"
            probe_file.write_text("ok", encoding="utf-8")
            probe_file.unlink(missing_ok=True)

            logger.debug("Permission check passed")
            return True
        except Exception as exc:
            logger.error("Permission check failed: %s", exc)
            return False

    def _is_file_ready(self, file_path: Path) -> bool:
        """Return True when a file is large enough and has stopped changing."""
        try:
            stat = file_path.stat()

            if stat.st_size < self.MIN_FILE_SIZE:
                logger.debug(
                    "File %s is too small: %s < %s",
                    file_path.name,
                    stat.st_size,
                    self.MIN_FILE_SIZE,
                )
                return False

            current_time = time.time()
            file_mtime = stat.st_mtime
            file_size = stat.st_size
            cache_key = str(file_path)

            if cache_key in self._file_cache:
                first_seen_time, cached_mtime, cached_size = self._file_cache[cache_key]

                if file_mtime != cached_mtime or file_size != cached_size:
                    logger.debug("File %s is still changing; resetting stability timer", file_path.name)
                    self._file_cache[cache_key] = (current_time, file_mtime, file_size)
                    return False

                time_since_first_seen = current_time - first_seen_time
                logger.debug(
                    "File %s has been stable for %.1fs; required %.1fs",
                    file_path.name,
                    time_since_first_seen,
                    self.FILE_STABLE_TIME,
                )

                if time_since_first_seen >= self.FILE_STABLE_TIME:
                    logger.debug("File %s is ready for processing", file_path.name)
                    del self._file_cache[cache_key]
                    return True
                return False

            logger.debug("File %s first seen; waiting for stability", file_path.name)
            self._file_cache[cache_key] = (current_time, file_mtime, file_size)
            return False

        except (PermissionError, FileNotFoundError) as exc:
            logger.debug("File %s is not accessible yet: %s", file_path.name, exc)
            return False
        except Exception as exc:
            logger.warning("Failed to check readiness for %s: %s", file_path, exc)
            return False

    def check_for_new_files(self) -> None:
        """Scan the incoming directory and enqueue files that are ready."""
        logger.debug("check_for_new_files: started")

        if not self.external_path.exists():
            logger.warning("Incoming path does not exist: %s", self.external_path)
            return

        logger.debug("Scanning incoming path: %s", self.external_path)

        files_count = 0
        for item in self.external_path.iterdir():
            files_count += 1
            logger.debug("[%s] %s (file=%s)", files_count, item.name, item.is_file())

            if not item.is_file() or item.name.startswith("."):
                continue

            logger.debug("Checking readiness: %s", item.name)

            if not self._is_file_ready(item):
                logger.debug("File %s is not ready yet; skipping this scan", item.name)
                continue

            file_stat = item.stat()
            cache_key = f"{item.name}:{file_stat.st_mtime}:{file_stat.st_size}"

            if cache_key in self.processed_files:
                logger.debug("File %s is already processed in this monitor session", item.name)
                continue

            logger.info("New ready file detected: %s (%s bytes)", item.name, file_stat.st_size)
            file_id = str(uuid.uuid4())[:8]
            success = self.process_new_file(item, file_id)

            if success:
                self.processed_files.add(cache_key)
                if len(self.processed_files) > 1000:
                    self.processed_files = set(list(self.processed_files)[-1000:])
            else:
                logger.warning("Failed to register file: %s", item.name)

        logger.debug("check_for_new_files: completed; scanned entries=%s", files_count)

    def process_new_file(self, file_path: Path, file_id: str) -> bool:
        """Copy the original file, create a FileJob, and enqueue it."""
        try:
            stem = Path(file_path.name).stem
            storage_dir = stem
            base_dir = self.shared_path / storage_dir
            if base_dir.exists():
                shutil.rmtree(base_dir)
            original_dir = base_dir / "original"
            safe_mkdir(original_dir, mode=0o755)

            dest_path = original_dir / file_path.name

            if not file_path.exists():
                logger.warning("Source file disappeared before copy: %s", file_path)
                return False

            shutil.copy2(file_path, dest_path)

            try:
                os.chmod(dest_path, 0o644)
            except PermissionError:
                logger.warning("Could not set permissions for copied file: %s", dest_path)

            logger.info("Copied file: %s -> %s", file_path, dest_path)

            file_type = FileJob.detect_file_type(file_path.name)
            file_size = file_path.stat().st_size

            job = FileJob(
                file_id=file_id,
                original_filename=file_path.name,
                storage_dir=storage_dir,
                file_type=file_type,
                file_size=file_size,
                status=FileStatus.UPLOADED,
                current_module=self._resolve_first_module(),
                export_to_1c=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            self.redis.set_file_status(file_id, job.to_dict())
            self.redis.push_to_queue(self._resolve_entry_queue(), job.to_payload(), priority=job.priority)
            self.redis.publish_event(
                "files:events",
                {
                    "type": "file_uploaded",
                    "file_id": file_id,
                    "filename": file_path.name,
                    "status": job.status.value,
                    "file_type": file_type.value,
                    "file_size": file_size,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            logger.info("File %s was enqueued for processing", file_id)
            return True

        except PermissionError as exc:
            logger.error("Permission error while processing %s: %s", file_path, exc)
            logger.error("Check permissions for directory: %s", file_path.parent)
            self._publish_error_event(file_path.name, f"PermissionError: {exc}")
            return False

        except shutil.Error as exc:
            logger.error("Copy error for %s: %s", file_path, exc)
            self._publish_error_event(file_path.name, f"CopyError: {exc}")
            return False

        except Exception as exc:
            logger.error("Failed to process file %s: %s", file_path, exc, exc_info=True)
            self._publish_error_event(file_path.name, str(exc))
            return False

    def _publish_error_event(self, filename: str, error: str) -> None:
        """Publish a file-level error event for the UI."""
        try:
            self.redis.publish_event(
                "files:events",
                {
                    "type": "file_error",
                    "filename": filename,
                    "error": error,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            logger.error("Failed to publish file error event: %s", exc)

    def cleanup_cache(self) -> None:
        """Keep the in-memory processed-file cache bounded."""
        if len(self.processed_files) > 500:
            old_count = len(self.processed_files)
            self.processed_files = set(list(self.processed_files)[-500:])
            logger.debug("Processed-files cache trimmed: %s -> %s", old_count, len(self.processed_files))


def main() -> None:
    """Container entry point for the file monitor."""
    logger.info("Starting FileMonitor...")

    try:
        monitor = FileMonitor()
        monitor.start()
    except Exception as exc:
        logger.error("Critical FileMonitor error: %s", exc, exc_info=True)
        raise


if __name__ == "__main__":
    main()
