from __future__ import annotations

from shared.config.app_settings import WorkerSettings


class Config(WorkerSettings):
    pass


config = Config.from_env()
