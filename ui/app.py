"""Streamlit entry point for the Algofusion UI."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(
    page_title="Algofusion UI",
    layout="wide",
    initial_sidebar_state="expanded",
)

from core.services.file_service import FileService
from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from ui.cache import CacheManager, get_redis_client_cached
from ui.pages.file_detail_page import render_file_detail_page
from ui.pages.main_page import render_main_page
from ui.state import get_session_state
from ui.utils.ui_hacks import hide_streamlit_navigation

logger = setup_logger("ui.app")


def main() -> None:
    """Initialize dependencies and route to the selected UI page."""
    hide_streamlit_navigation()
    session = get_session_state()
    settings = get_settings()
    session.settings = settings

    if session.redis_client is None:
        session.redis_client = get_redis_client_cached()

    if session.file_service is None:
        session.file_service = FileService(settings.shared_files_path)

    if getattr(session.file_service, "using_fallback_base_dir", False):
        st.warning(
            "Shared files storage is unavailable at the configured path. "
            "The UI is running with a temporary fallback directory, so Docker pipeline artifacts "
            "won't appear here until you provide a writable SHARED_FILES_PATH."
        )

    session.process_events()
    session.update_refresh_time()
    _render_header(session)

    try:
        if session.current_page == "detail":
            render_file_detail_page(session)
        else:
            render_main_page(session)
    except Exception as exc:
        logger.error("UI render failed: %s", exc, exc_info=True)
        st.error(f"Critical UI error: {exc}")

    _render_footer(session)


def _render_header(session) -> None:
    left, center, right = st.columns([4, 1, 1])
    left.title("Algofusion")
    center.metric("Uptime", session.get_uptime())
    right.caption(f"Updated: {session.last_refresh.strftime('%H:%M:%S') if session.last_refresh else '--:--:--'}")


def _render_footer(session) -> None:
    st.divider()
    left, center, right = st.columns(3)
    left.caption(f"Version: {session.settings.app_version}")
    center.caption(f"Environment: {session.settings.environment}")
    if right.button("Clear cache", key="footer_clear_cache", use_container_width=True):
        CacheManager.clear_all()
        session.invalidate_cache()
        st.rerun()


if __name__ == "__main__":
    main()
