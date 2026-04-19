"""Pydantic settings models shared across containers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default="text", validation_alias="LOG_FORMAT")
    service_name: str = Field(default="algofusion", validation_alias="SERVICE_NAME")
    container_id: str = Field(default="unknown", validation_alias="CONTAINER_ID")


class SharedSettings(CommonSettings):
    redis_host: str = Field(default="redis", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")

    shared_files_path: str = Field(default="/shared/files", validation_alias="SHARED_FILES_PATH")
    external_monitor_path: str = Field(default="/external/incoming", validation_alias="EXTERNAL_MONITOR_PATH")

    monitor_interval: int = Field(default=30, validation_alias="MONITOR_INTERVAL")
    worker_type: str = Field(default="pipeline_v2", validation_alias="WORKER_TYPE")
    worker_timeout: int = Field(default=300, validation_alias="WORKER_TIMEOUT")
    pipeline_mode: str = Field(default="v2", validation_alias="PIPELINE_MODE")
    pipeline_v2_queue: str = Field(default="files:pipeline_v2", validation_alias="PIPELINE_V2_QUEUE")

    export_1c_enabled: bool = Field(default=False, validation_alias="EXPORT_1C_ENABLED")
    export_1c_endpoint: str = Field(default="", validation_alias="EXPORT_1C_ENDPOINT")

    ui_auto_refresh_enabled: bool = Field(default=True, validation_alias="UI_AUTO_REFRESH_ENABLED")
    ui_auto_refresh_interval_sec: int = Field(default=10, validation_alias="UI_AUTO_REFRESH_INTERVAL_SEC")
    ui_auto_refresh_min_sec: int = Field(default=5, validation_alias="UI_AUTO_REFRESH_MIN_SEC")
    ui_auto_refresh_max_sec: int = Field(default=60, validation_alias="UI_AUTO_REFRESH_MAX_SEC")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    environment: str = Field(default="local", validation_alias="ENVIRONMENT")

    @classmethod
    def from_env(cls) -> "SharedSettings":
        return cls()

    def validate(self) -> bool:
        errors: list[str] = []
        if not self.redis_host:
            errors.append("REDIS_HOST is required")
        if self.monitor_interval < 5:
            errors.append("MONITOR_INTERVAL must be >= 5")
        if self.pipeline_mode not in {"main", "v2", "pipeline_v2"}:
            errors.append("PIPELINE_MODE must be one of 'main', 'v2', or 'pipeline_v2'")
        if self.ui_auto_refresh_min_sec < 1:
            errors.append("UI_AUTO_REFRESH_MIN_SEC must be >= 1")
        if self.ui_auto_refresh_max_sec < self.ui_auto_refresh_min_sec:
            errors.append("UI_AUTO_REFRESH_MAX_SEC must be >= UI_AUTO_REFRESH_MIN_SEC")
        if not (
            self.ui_auto_refresh_min_sec
            <= self.ui_auto_refresh_interval_sec
            <= self.ui_auto_refresh_max_sec
        ):
            errors.append("UI_AUTO_REFRESH_INTERVAL_SEC must stay within configured min/max range")
        return not errors


class WorkerSettings(CommonSettings):
    redis_url: str = Field(default="redis://redis:6379/0", validation_alias="REDIS_URL")
    redis_queue: str = Field(default="files:pipeline_v2", validation_alias="PIPELINE_V2_QUEUE")
    redis_timeout: int = Field(default=5, validation_alias="BLPOP_TIMEOUT")

    shared_files_dir: Path = Field(default=Path("/shared/files"), validation_alias="SHARED_FILES_DIR")
    helper_path: Path = Field(
        default_factory=lambda: _default_worker_helper_path(),
        validation_alias="PIPELINE_V2_HELPER_PATH",
    )
    max_pages: int = Field(default=0, validation_alias="PIPELINE_V2_MAX_PAGES")
    force_doc_type: Optional[str] = Field(default=None, validation_alias="PIPELINE_V2_FORCE_DOC_TYPE")
    max_retries: int = Field(default=3, validation_alias="MAX_RETRIES")

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        settings = cls()
        if settings.force_doc_type == "":
            settings.force_doc_type = None
        return settings

    def validate(self) -> bool:
        if not self.redis_url:
            raise ValueError("REDIS_URL is required")
        return True


def _default_worker_helper_path() -> Path:
    env_path = os.getenv("PIPELINE_V2_HELPER_PATH")
    if env_path:
        return Path(env_path)
    candidates = [
        Path("/app/src/modules/runtime_bridge.py"),
        Path(__file__).resolve().parents[2]
        / "workers"
        / "OCR-Sergei"
        / "PIPELINE_V2"
        / "src"
        / "modules"
        / "runtime_bridge.py",
        Path.cwd() / "workers" / "OCR-Sergei" / "PIPELINE_V2" / "src" / "modules" / "runtime_bridge.py",
        Path.cwd() / "src" / "modules" / "runtime_bridge.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
