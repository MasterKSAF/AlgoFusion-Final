"""Lazy exports for core services."""

from __future__ import annotations

__all__ = ["get_redis_client", "RedisClient", "FileService"]


def __getattr__(name: str):
    if name in {"get_redis_client", "RedisClient"}:
        from core.services.redis_client import RedisClient, get_redis_client

        return {"get_redis_client": get_redis_client, "RedisClient": RedisClient}[name]

    if name == "FileService":
        from core.services.file_service import FileService

        return FileService

    raise AttributeError(f"module 'core.services' has no attribute {name!r}")
