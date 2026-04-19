from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.utils.json_utils import json_dumps, json_loads


class FileType(str, Enum):
    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"
    TEXT = "text"
    UNKNOWN = "unknown"


class FileStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    EXPORTED = "exported"
    FAILED = "failed"


class ExportStatus(str, Enum):
    PENDING = "pending"
    EXPORTING = "exporting"
    SUCCESS = "success"
    FAILED = "failed"


class ExportConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    enabled: bool = False
    mode: str = "manual"
    format: str = "1c_xml"
    endpoint: str = ""
    batch_size: int = 10
    retry_count: int = 3


class FileJob(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=False)

    file_id: str
    original_filename: str
    storage_dir: str | None = None
    file_type: FileType = FileType.UNKNOWN
    file_size: int = 0
    status: FileStatus = FileStatus.UPLOADED

    current_module: str | None = None
    completed_modules: set[str] = Field(default_factory=set)

    ocr_engine: str = "tesseract"
    ocr_lang: str = "rus+eng"

    export_to_1c: bool = False
    export_config: ExportConfig = Field(default_factory=ExportConfig)
    export_status: ExportStatus = ExportStatus.PENDING
    export_attempts: int = 0
    export_error: str | None = None
    exported_at: datetime | None = None
    document_1c_id: str | None = None

    config: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    callback_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    history: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @field_validator("created_at", "updated_at", "exported_at", mode="before")
    @classmethod
    def _normalize_datetime(cls, value: Any) -> Any:
        if value is None or isinstance(value, datetime):
            return cls._ensure_utc(value)
        if isinstance(value, str):
            return cls._parse_datetime(value)
        return value

    @classmethod
    def from_payload(cls, payload: str | bytes | dict[str, Any]) -> "FileJob":
        if isinstance(payload, dict):
            data = payload
        else:
            data = json_loads(payload)

        completed = data.get("completed_modules", [])
        if isinstance(completed, list):
            data["completed_modules"] = set(completed)

        return cls.model_validate(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "original_filename": self.original_filename,
            "storage_dir": self.storage_dir,
            "file_type": self.file_type.value,
            "file_size": self.file_size,
            "status": self.status.value,
            "current_module": self.current_module,
            "completed_modules": list(self.completed_modules),
            "ocr_engine": self.ocr_engine,
            "ocr_lang": self.ocr_lang,
            "export_to_1c": self.export_to_1c,
            "export_config": {
                "enabled": self.export_config.enabled,
                "mode": self.export_config.mode,
                "format": self.export_config.format,
                "endpoint": self.export_config.endpoint,
                "batch_size": self.export_config.batch_size,
            },
            "export_status": self.export_status.value,
            "export_attempts": self.export_attempts,
            "export_error": self.export_error,
            "exported_at": self.exported_at.isoformat() if self.exported_at else None,
            "document_1c_id": self.document_1c_id,
            "config": self.config,
            "priority": self.priority,
            "callback_url": self.callback_url,
            "metadata": self.metadata,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "history": self.history,
            "errors": self.errors,
        }

    def to_payload(self) -> str:
        return json_dumps(self.to_dict())

    def get_storage_dir_name(self) -> str:
        return self.storage_dir or Path(self.original_filename).stem

    def get_base_path(self, base_dir: str = "/shared/files") -> Path:
        base_dir_path = Path(base_dir)
        preferred = base_dir_path / self.get_storage_dir_name()
        legacy = base_dir_path / self.file_id
        if legacy.exists() and not preferred.exists():
            return legacy
        return preferred

    def get_original_path(self, base_dir: str = "/shared/files") -> Path:
        return self.get_base_path(base_dir) / "original" / self.original_filename

    def get_module_input_path(self, module: str, base_dir: str = "/shared/files") -> Path:
        base = self.get_base_path(base_dir)
        if module in {"pipeline_v2", "cleaner"}:
            return self.get_original_path(base_dir)
        if module == "ocr":
            preprocessed = base / "preprocessed" / self.original_filename
            return preprocessed if preprocessed.exists() else self.get_original_path(base_dir)
        if module == "llm":
            return base / "ocr" / f"{Path(self.original_filename).stem}.txt"
        if module == "export":
            return base / "llm" / "analysis.json"
        return self.get_original_path(base_dir)

    def get_module_output_path(self, module: str, base_dir: str = "/shared/files") -> Path:
        base = self.get_base_path(base_dir) / module
        base.mkdir(parents=True, exist_ok=True)
        if module == "pipeline_v2":
            return base / f"{Path(self.original_filename).stem}.json"
        if module == "ocr":
            return base / f"{Path(self.original_filename).stem}.txt"
        if module == "llm":
            return base / "analysis.json"
        if module == "export":
            return base / f"{Path(self.original_filename).stem}_1c.xml"
        return base / self.original_filename

    def get_export_path(self, base_dir: str = "/shared/files") -> Path:
        export_dir = self.get_base_path(base_dir) / "export"
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir / f"{Path(self.original_filename).stem}_1c.xml"

    def get_archive_path(self, base_dir: str = "/shared/files") -> Path:
        archive_dir = self.get_base_path(base_dir) / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        return archive_dir / f"{self.file_id}_processed.zip"

    @classmethod
    def detect_file_type(cls, filename: str) -> FileType:
        ext = Path(filename).suffix.lower()
        extensions = {
            FileType.IMAGE: {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".webp"},
            FileType.PDF: {".pdf"},
            FileType.DOCUMENT: {".doc", ".docx", ".odt", ".rtf"},
            FileType.TEXT: {".txt", ".md", ".csv", ".json", ".xml"},
        }
        for file_type, allowed_extensions in extensions.items():
            if ext in allowed_extensions:
                return file_type
        return FileType.UNKNOWN

    def get_allowed_modules(self) -> list[str]:
        routing = {
            FileType.IMAGE: ["pipeline_v2"],
            FileType.PDF: ["pipeline_v2"],
            FileType.DOCUMENT: [],
            FileType.TEXT: [],
            FileType.UNKNOWN: [],
        }
        return routing.get(self.file_type, [])

    def complete_module(self, module: str) -> None:
        self.completed_modules.add(module)
        self.current_module = None
        self.updated_at = datetime.now(timezone.utc)

    def fail_module(self, module: str, error: str) -> None:
        self.status = FileStatus.FAILED
        self.current_module = module
        self.errors.append(error)
        self.updated_at = datetime.now(timezone.utc)

    def add_to_history(
        self,
        action: str,
        module: str,
        success: bool,
        error: str | None = None,
        duration: float | None = None,
    ) -> None:
        self.history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "module": module,
                "action": action,
                "success": success,
                "error": error,
                "duration_seconds": duration,
            }
        )
        self.updated_at = datetime.now(timezone.utc)

    def is_complete(self) -> bool:
        if self.status == FileStatus.FAILED:
            return True
        return all(module in self.completed_modules for module in self.get_allowed_modules())

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        self.retry_count += 1
        self.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _ensure_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        dt = datetime.fromisoformat(value)
        return FileJob._ensure_utc(dt) or datetime.now(timezone.utc)
