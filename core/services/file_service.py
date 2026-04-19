"""Helpers for browsing pipeline files and logical UI folders."""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.models.file import FileJob
from shared.utils.helpers import safe_mkdir
from shared.utils.logger import setup_logger
from ui.utils.constants import LOGICAL_STAGE_DIRS, UI_CONFIG

logger = setup_logger("core.services.file_service")


class FileService:
    """File-system access for the UI."""

    def __init__(self, base_dir: str = "/shared/files"):
        self.requested_base_dir = Path(base_dir)
        self.base_dir, self.using_fallback_base_dir = self._resolve_base_dir(self.requested_base_dir)
        logger.info(
            "FileService initialized: requested_base_dir=%s effective_base_dir=%s fallback=%s",
            self.requested_base_dir,
            self.base_dir,
            self.using_fallback_base_dir,
        )

    def _resolve_base_dir(self, requested_base_dir: Path) -> tuple[Path, bool]:
        if requested_base_dir.exists():
            return requested_base_dir, False

        try:
            safe_mkdir(requested_base_dir)
            return requested_base_dir, False
        except PermissionError:
            pass

        project_local = Path.cwd() / "shared" / "files"
        if project_local.exists():
            return project_local, True

        fallback_dir = Path(
            os.getenv("STREAMLIT_SHARED_FILES_FALLBACK", "/tmp/algofusion/shared_files")
        )
        safe_mkdir(fallback_dir)
        logger.warning(
            "Shared files path %s is not writable; falling back to %s",
            requested_base_dir,
            fallback_dir,
        )
        return fallback_dir, True

    def create_file_structure(self, file_job: FileJob) -> bool:
        """Create the current pipeline folder structure for a file."""
        try:
            base = file_job.get_base_path(str(self.base_dir))
            directories = [
                base / "original",
                base / "cleaner",
                base / "out_table_merge",
                base / "final_rebuilt_auto",
                base / "data" / "pred",
                base / "data" / "pred_normalized",
                base / "data" / "pred_reconciled",
                base / "data" / "final_json",
                base / "archive",
            ]
            for directory in directories:
                safe_mkdir(directory)
            return True
        except Exception as exc:
            logger.error("Failed to create file structure: %s", exc, exc_info=True)
            return False

    def move_to_archive(self, file_job: FileJob) -> bool:
        """Archive all stage outputs for a file."""
        try:
            base = file_job.get_base_path(str(self.base_dir))
            archive_path = file_job.get_archive_path(str(self.base_dir))

            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for stage in ["original", "cleaner", "out_table_merge", "final_rebuilt_auto", "data"]:
                    stage_path = base / stage
                    if not stage_path.exists():
                        continue
                    for file_path in stage_path.rglob("*"):
                        if file_path.is_file():
                            zipf.write(file_path, file_path.relative_to(base))

            return True
        except Exception as exc:
            logger.error("Failed to archive file %s: %s", file_job.file_id, exc, exc_info=True)
            return False

    def get_file_info(
        self,
        file_id: str,
        original_filename: Optional[str] = None,
        storage_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return logical UI folders and their underlying physical files."""
        base = self._resolve_base_path(file_id, original_filename, storage_dir)
        if base is None:
            return None

        directories: Dict[str, Dict[str, Any]] = {}
        for logical_stage, relative_dirs in LOGICAL_STAGE_DIRS.items():
            stage_files = self._collect_stage_files(base, logical_stage)
            if not stage_files:
                continue
            directories[logical_stage] = {
                "logical_name": logical_stage,
                "label": logical_stage.title(),
                "physical_dirs": relative_dirs,
                "paths": [str(base / relative_dir) for relative_dir in relative_dirs if (base / relative_dir).exists()],
                "file_count": len(stage_files),
                "files": [self._file_info_dict(path, base) for path in stage_files],
            }

        archive_path = base / "archive"
        if archive_path.exists():
            archive_files = [path for path in archive_path.rglob("*") if path.is_file()]
            if archive_files:
                directories["archive"] = {
                    "logical_name": "archive",
                    "label": "Archive",
                    "physical_dirs": ["archive"],
                    "paths": [str(archive_path)],
                    "file_count": len(archive_files),
                    "files": [self._file_info_dict(path, base) for path in archive_files],
                }

        return {
            "file_id": file_id,
            "base_path": str(base),
            "storage_dir": base.name,
            "directories": directories,
        }

    def cleanup_old_files(self, max_age_days: int = 30) -> int:
        """Delete stale working directories."""
        try:
            cleaned = 0
            now = datetime.now(timezone.utc)
            for file_dir in self.base_dir.iterdir():
                if not file_dir.is_dir() or file_dir.name == "archive":
                    continue
                age_days = (now - datetime.fromtimestamp(file_dir.stat().st_ctime, tz=timezone.utc)).days
                if age_days > max_age_days:
                    shutil.rmtree(file_dir)
                    cleaned += 1
            return cleaned
        except Exception as exc:
            logger.error("Failed to clean up old files: %s", exc, exc_info=True)
            return 0

    def list_files(self) -> List[str]:
        """List storage directories present in the shared folder."""
        try:
            return sorted(directory.name for directory in self.base_dir.iterdir() if directory.is_dir())
        except Exception as exc:
            logger.error("Failed to list files: %s", exc)
            return []

    def get_download_path(
        self,
        file_id: str,
        file_type: str = "original",
        original_filename: Optional[str] = None,
        storage_dir: Optional[str] = None,
    ) -> Optional[Path]:
        """Return the best representative file for a logical stage."""
        base = self._resolve_base_path(file_id, original_filename, storage_dir)
        if base is None:
            return None
        stage_files = self._collect_stage_files(base, file_type)
        return stage_files[0] if stage_files else None

    def get_file_content(
        self,
        file_id: str,
        file_type: str = "original",
        original_filename: Optional[str] = None,
        storage_dir: Optional[str] = None,
    ) -> Optional[bytes]:
        """Return bytes for the representative file of a logical stage."""
        path = self.get_download_path(file_id, file_type, original_filename, storage_dir)
        if path is None or not path.exists():
            return None
        if path.stat().st_size > UI_CONFIG["max_preview_bytes"]:
            logger.warning("Skipping preview for large file: %s", path)
            return None
        return path.read_bytes()

    def get_text_preview(
        self,
        file_id: str,
        file_type: str = "ocr",
        max_lines: int = 50,
        original_filename: Optional[str] = None,
        storage_dir: Optional[str] = None,
    ) -> Optional[str]:
        """Return a text preview for the representative file of a logical stage."""
        path = self.get_download_path(file_id, file_type, original_filename, storage_dir)
        if path is None or not path.exists():
            return None

        try:
            if path.suffix.lower() == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                text = json.dumps(data, ensure_ascii=False, indent=2)
            else:
                text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.warning("Failed to build text preview for %s: %s", path, exc)
            return None

        return "\n".join(text.splitlines()[:max_lines])

    def get_file_metadata(
        self,
        file_id: str,
        file_type: str = "original",
        original_filename: Optional[str] = None,
        storage_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return metadata for the representative file of a logical stage."""
        path = self.get_download_path(file_id, file_type, original_filename, storage_dir)
        if path is None or not path.exists():
            return None
        return self._file_info_dict(path, path.parents[1] if len(path.parents) > 1 else path.parent)

    def delete_file(
        self,
        file_id: str,
        original_filename: Optional[str] = None,
        storage_dir: Optional[str] = None,
        force: bool = True,
    ) -> bool:
        """Delete the working directory for a file."""
        del force  # kept for API compatibility
        base = self._resolve_base_path(file_id, original_filename, storage_dir)
        if base is None:
            return False
        try:
            shutil.rmtree(base)
            logger.info("Deleted file directory: %s", base)
            return True
        except Exception as exc:
            logger.error("Failed to delete file directory %s: %s", base, exc, exc_info=True)
            return False

    def retry_processing(
        self,
        file_id: str,
        original_filename: Optional[str] = None,
        storage_dir: Optional[str] = None,
    ) -> bool:
        """Clean transient outputs while keeping the original file."""
        base = self._resolve_base_path(file_id, original_filename, storage_dir)
        if base is None:
            return False

        try:
            for relative_dir in [
                "cleaner",
                "out_table_merge",
                "final_rebuilt_auto",
                "data/pred",
                "data/pred_normalized",
                "data/pred_reconciled",
                "data/final_json",
            ]:
                target = base / relative_dir
                if target.exists():
                    shutil.rmtree(target)
            self.create_file_structure(
                FileJob(file_id=file_id, original_filename=original_filename or file_id, storage_dir=base.name)
            )
            return True
        except Exception as exc:
            logger.error("Failed to reset file outputs for retry: %s", exc, exc_info=True)
            return False

    def get_stage_files(
        self,
        file_id: str,
        stage: str,
        original_filename: Optional[str] = None,
        storage_dir: Optional[str] = None,
    ) -> List[Path]:
        """Return all files for a logical stage."""
        base = self._resolve_base_path(file_id, original_filename, storage_dir)
        if base is None:
            return []
        return self._collect_stage_files(base, stage)

    def _resolve_base_path(
        self,
        file_id: str,
        original_filename: Optional[str],
        storage_dir: Optional[str],
    ) -> Optional[Path]:
        candidates: list[Path] = []

        if storage_dir:
            candidates.append(self.base_dir / storage_dir)
        if original_filename:
            candidates.append(self.base_dir / Path(original_filename).stem)
        candidates.append(self.base_dir / file_id)

        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            if candidate.exists():
                return candidate
        return None

    def _collect_stage_files(self, base: Path, stage: str) -> List[Path]:
        relative_dirs = LOGICAL_STAGE_DIRS.get(stage, [stage])
        collected: list[Path] = []
        for relative_dir in relative_dirs:
            target = base / relative_dir
            if not target.exists():
                continue
            collected.extend(path for path in target.rglob("*") if path.is_file())
        return sorted(collected, key=self._stage_sort_key(stage))

    def _stage_sort_key(self, stage: str):
        def sort_key(path: Path) -> tuple[int, int, str]:
            name = path.name.lower()
            suffix = path.suffix.lower()
            priority = 99

            if stage == "original":
                priority = 0 if suffix == ".pdf" else 1
            elif stage == "preprocessed":
                if "__clean" in name:
                    priority = 0
                elif "out_table_merge" in str(path):
                    priority = 1
                elif suffix in {".png", ".jpg", ".jpeg"}:
                    priority = 2
            elif stage == "ocr":
                if name.endswith("_roi_text.json"):
                    priority = 0
                elif "__waybill_header_ocr.json" in name:
                    priority = 1
                elif "__ocr_raw.json" in name:
                    priority = 2
                elif suffix == ".json":
                    priority = 3
                elif suffix in {".png", ".jpg", ".jpeg"}:
                    priority = 4
            elif stage == "llm":
                if "pred_reconciled" in str(path):
                    priority = 0
                elif "pred_normalized" in str(path):
                    priority = 1
                elif "pred" in str(path):
                    priority = 2
            elif stage == "export":
                priority = 0 if suffix == ".json" else 1

            suffix_score = 0 if suffix in {".json", ".txt", ".pdf", ".png", ".jpg", ".jpeg"} else 1
            return (priority, suffix_score, str(path))

        return sort_key

    def _file_info_dict(self, path: Path, base: Path) -> Dict[str, Any]:
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "relative_path": str(path.relative_to(base)),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "suffix": path.suffix.lower(),
        }
