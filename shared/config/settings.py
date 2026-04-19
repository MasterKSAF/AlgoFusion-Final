"""Backward-compatible shared settings accessors."""

from __future__ import annotations

from typing import Optional

from shared.config.app_settings import SharedSettings
from shared.utils.logger import setup_logger

logger = setup_logger("shared.config.settings")


class Settings(SharedSettings):
    pass


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
        if not _settings.validate():
            logger.warning("Shared settings validation reported warnings")
    return _settings
