"""Streamlit session state helpers for the UI."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import streamlit as st

from shared.utils.logger import setup_logger

logger = setup_logger("ui.state")


@dataclass
class SessionState:
    """Global state persisted across Streamlit reruns."""

    current_page: str = "main"
    editing_file_index: Optional[int] = None
    selected_file_id: Optional[str] = None

    redis_client: Any = None
    file_service: Any = None
    settings: Any = None

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cache_buster: str = field(default_factory=lambda: f"v{int(time.time())}")
    last_refresh: Optional[datetime] = None

    _filters: Dict[str, List[str]] = field(default_factory=dict)
    _logs: List[Dict[str, str]] = field(default_factory=list)
    max_logs: int = 100

    _pubsub: Any = None
    _subscribed_channels: List[str] = field(default_factory=lambda: ["files:events", "1c:export"])
    _last_event_check: float = 0.0
    _event_check_interval: float = 0.25
    pending_events: bool = False
    _events_subscribed: bool = False
    _recent_history_loaded: bool = False

    def add_log(self, status: str, message: str, time_str: Optional[str] = None) -> None:
        """Append a UI log entry."""
        self._append_log(status, message, time_str=time_str, mark_pending=True)

    def _append_log(
        self,
        status: str,
        message: str,
        time_str: Optional[str] = None,
        *,
        mark_pending: bool,
    ) -> None:
        """Append a UI log entry with optional pending flag update."""
        if time_str is None:
            time_str = datetime.now(timezone.utc).strftime("%H:%M:%S")

        self._logs.append({"time": time_str, "status": status, "msg": message})
        if len(self._logs) > self.max_logs:
            self._logs = self._logs[-self.max_logs :]
        if mark_pending:
            self.pending_events = True

    def get_logs(self, limit: int = 20) -> List[Dict[str, str]]:
        """Return recent UI log entries."""
        return self._logs[-limit:] if self._logs else []

    def clear_logs(self) -> None:
        """Clear UI logs."""
        self._logs.clear()
        self.pending_events = False

    def subscribe_to_events(self) -> None:
        """Subscribe to Redis pub/sub channels once."""
        if not self.redis_client or self._pubsub is not None:
            return
        try:
            self._pubsub = self.redis_client.subscribe(self._subscribed_channels)
            self._events_subscribed = True
            self._load_recent_events()
            logger.info("Subscribed to Redis events: %s", self._subscribed_channels)
        except Exception as exc:
            logger.warning("Failed to subscribe to Redis events: %s", exc)

    def _load_recent_events(self) -> None:
        """Hydrate the log viewer from recent Redis events once per session."""
        if self._recent_history_loaded or not self.redis_client:
            return
        if not hasattr(self.redis_client, "get_recent_events"):
            self._recent_history_loaded = True
            return
        try:
            events = self.redis_client.get_recent_events(limit=self.max_logs)
            self._logs.clear()
            for event in events:
                self._handle_event(event, invalidate=False, mark_pending=False)
            self.pending_events = False
        except Exception as exc:
            logger.debug("Failed to load recent Redis events: %s", exc)
        finally:
            self._recent_history_loaded = True

    def process_events(self) -> None:
        """Poll Redis pub/sub without blocking the UI."""
        now = time.time()
        if now - self._last_event_check < self._event_check_interval:
            return
        self._last_event_check = now

        if not self.redis_client:
            return

        if self._pubsub is None:
            self.subscribe_to_events()
        if self._pubsub is None:
            return

        try:
            for attempt in range(4):
                message = self._pubsub.get_message(timeout=0.15 if attempt == 0 else 0.05)
                while message:
                    if message.get("type") in {"message", "pmessage"}:
                        try:
                            event = json.loads(message["data"])
                            self._handle_event(event)
                        except Exception as exc:
                            logger.debug("Skipping invalid Redis event: %s", exc)
                    message = self._pubsub.get_message(timeout=0.05)
                if self.pending_events:
                    break
                time.sleep(0.05)
        except Exception as exc:
            logger.debug("Redis event polling error: %s", exc)

    def _handle_event(
        self,
        event: Dict[str, Any],
        *,
        invalidate: bool = True,
        mark_pending: bool = True,
    ) -> None:
        """Translate a Redis event into a short UI log line."""
        if invalidate:
            self.invalidate_cache()
        event_name = event.get("type") or event.get("event") or "unknown"
        file_id = str(event.get("file_id", "unknown"))
        short_id = file_id[:8]
        filename = event.get("filename") or short_id
        module = event.get("module")
        status = event.get("status")
        next_module = event.get("next_module")
        error = event.get("error")

        timestamp = event.get("timestamp")
        time_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        if timestamp:
            try:
                time_str = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).strftime("%H:%M:%S")
            except Exception:
                pass

        if event_name == "file_uploaded":
            self._append_log("OK", f"Queued {filename}", time_str=time_str, mark_pending=mark_pending)
        elif event_name == "module_started":
            if module:
                self._append_log("INFO", f"{module} started for {short_id}", time_str=time_str, mark_pending=mark_pending)
            else:
                self._append_log("INFO", f"{filename}: processing started", time_str=time_str, mark_pending=mark_pending)
        elif event_name == "file_error":
            self._append_log("ERROR", f"{filename}: {error or 'monitor error'}", time_str=time_str, mark_pending=mark_pending)
        elif event_name == "module_completed":
            if status == "failed":
                self._append_log("ERROR", f"{module} failed for {short_id}", time_str=time_str, mark_pending=mark_pending)
            elif module:
                suffix = f" -> {next_module}" if next_module else ""
                self._append_log("OK", f"{module} done for {short_id}{suffix}", time_str=time_str, mark_pending=mark_pending)
            else:
                self._append_log("INFO", f"{filename}: {status or 'updated'}", time_str=time_str, mark_pending=mark_pending)
        else:
            message = error or f"{filename}: {event_name}"
            self._append_log("INFO", message, time_str=time_str, mark_pending=mark_pending)

    def invalidate_cache(self) -> None:
        """Bump cache key for cache-backed helpers."""
        self.cache_buster = f"v{int(time.time())}"

    def update_refresh_time(self) -> None:
        """Record the latest refresh timestamp."""
        self.last_refresh = datetime.now(timezone.utc)

    def get_filter(self, key: str, default: Optional[List[str]] = None) -> List[str]:
        """Read a persisted filter."""
        return self._filters.get(key, default or [])

    def set_filter(self, key: str, value: List[str]) -> None:
        """Persist a filter."""
        self._filters[key] = value

    def navigate(self, page: str, **kwargs: Any) -> None:
        """Navigate to another page and store extra fields."""
        self.current_page = page
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_uptime(self) -> str:
        """Return UI session uptime."""
        delta = datetime.now(timezone.utc) - self.started_at
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


_SESSION_STATE_KEY = "_algofusion_session_state"


def get_session_state() -> SessionState:
    """Return or initialize the session singleton."""
    if _SESSION_STATE_KEY not in st.session_state:
        logger.info("Initializing SessionState")
        st.session_state[_SESSION_STATE_KEY] = SessionState()
    return st.session_state[_SESSION_STATE_KEY]


def reset_session_state() -> None:
    """Reset Streamlit session state for the UI."""
    if _SESSION_STATE_KEY in st.session_state:
        del st.session_state[_SESSION_STATE_KEY]
    logger.info("SessionState reset")
