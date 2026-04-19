"""Cached UI accessors for Redis-backed file data."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, TYPE_CHECKING

import streamlit as st

from shared.utils.logger import setup_logger
from ui.utils.constants import get_completed_logical_stages, map_module_to_logical_stage

if TYPE_CHECKING:
    from core.services.redis_client import RedisClient

logger = setup_logger("ui.cache")


@st.cache_resource(ttl=3600)
def get_redis_client_cached():
    """Return a cached Redis client."""
    from core.services.redis_client import get_redis_client

    logger.info("Creating cached Redis client")
    return get_redis_client()


@st.cache_data(ttl=30, show_spinner="Loading files...")
def get_files_from_redis_cached(
    _redis_client: "RedisClient",
    _cache_key: str = "default",
) -> List[Dict[str, Any]]:
    """Return all files from Redis, optionally invalidated by a cache key."""
    del _cache_key
    try:
        if hasattr(_redis_client, "get_all_files"):
            files = _redis_client.get_all_files()
            files.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
            return files
        return []
    except Exception as exc:
        logger.error("Failed to fetch files from Redis: %s", exc)
        return []


@st.cache_data(ttl=30, show_spinner="Loading stats...")
def get_file_stats_cached(
    _redis_client: "RedisClient",
    _cache_key: str = "default",
) -> Dict[str, Any]:
    """Return logical stage statistics for the dashboard."""
    files = get_files_from_redis_cached(_redis_client, _cache_key)
    return _calculate_stats(files)


@st.cache_data(ttl=60)
def get_file_structure_cached(
    _file_service: Any,
    file_id: str,
    original_filename: str | None = None,
    storage_dir: str | None = None,
    _cache_key: str = "default",
) -> Dict[str, Any] | None:
    """Return cached logical folder information for a file."""
    del _cache_key
    try:
        return _file_service.get_file_info(file_id, original_filename, storage_dir)
    except Exception as exc:
        logger.error("Failed to get file structure for %s: %s", file_id, exc)
        return None


class CacheManager:
    """Helper for clearing Streamlit caches."""

    @staticmethod
    def clear_all() -> None:
        st.cache_data.clear()
        st.cache_resource.clear()

    @staticmethod
    def clear_data_cache() -> None:
        st.cache_data.clear()

    @staticmethod
    def invalidate_function(func: Callable) -> None:
        try:
            func.clear()
        except Exception as exc:
            logger.warning("Failed to clear cache for %s: %s", getattr(func, "__name__", func), exc)


def _calculate_stats(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    stats = {
        "total": len(files),
        "uploaded": 0,
        "processing": 0,
        "failed": 0,
        "completed": 0,
        "exported": 0,
        "preprocessing": 0,
        "ocr": 0,
        "llm": 0,
        "pending_export": 0,
        "success_rate": "0%",
    }

    for file_data in files:
        status = str(file_data.get("status", "uploaded"))
        completed_stages = get_completed_logical_stages(file_data.get("completed_modules", []))
        current_stage = map_module_to_logical_stage(file_data.get("current_module"))

        export_complete = "export" in completed_stages or status in {"completed", "exported"}

        if status == "failed":
            stats["failed"] += 1
        elif export_complete:
            stats["completed"] += 1
            stats["exported"] += 1
        elif status == "processing":
            stats["processing"] += 1
            if current_stage == "preprocessed":
                stats["preprocessing"] += 1
            elif current_stage == "ocr":
                stats["ocr"] += 1
            elif current_stage == "llm":
                stats["llm"] += 1
            elif current_stage == "export":
                stats["pending_export"] += 1
        else:
            stats["uploaded"] += 1

        if status == "processing" and not export_complete and "llm" in completed_stages and current_stage not in {"export"}:
            stats["pending_export"] += 1

    finished = stats["completed"] + stats["failed"]
    if finished > 0:
        stats["success_rate"] = f"{(stats['completed'] / finished * 100):.1f}%"
    elif stats["total"] > 0:
        stats["success_rate"] = "100.0%"

    return stats
