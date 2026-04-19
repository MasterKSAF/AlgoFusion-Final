"""Main dashboard page with the older visual layout and pipeline_v2 semantics."""

from __future__ import annotations

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from ui.cache import get_file_stats_cached, get_files_from_redis_cached
from ui.components.file_list import render_file_list
from ui.components.log_viewer import render_log_viewer
from ui.components.refresh_settings import get_refresh_config, render_refresh_settings
from ui.components.stats_panel import render_stats_panel
from ui.state import SessionState

logger = setup_logger("ui.pages.main_page")


def render_main_page(session: SessionState) -> None:
    """Render the main dashboard page."""
    try:
        session.process_events()
    except AttributeError as exc:
        logger.debug("Skipping event processing during early init: %s", exc)

    from ui.utils.ui_hacks import add_compact_file_list_styles

    add_compact_file_list_styles()
    render_sidebar(session)

    redis_client = session.redis_client
    file_service = session.file_service

    if not redis_client:
        st.error("❌ Redis клиент не инициализирован")
        st.caption("Проверьте подключение к Redis и перезагрузите приложение.")
        return

    if not file_service:
        st.error("❌ FileService не инициализирован")
        return

    if not getattr(session, "_events_subscribed", False):
        try:
            session.subscribe_to_events()
            session._events_subscribed = True
        except AttributeError as exc:
            logger.debug("Skipping Redis subscribe during early init: %s", exc)

    auto_refresh_enabled, auto_refresh_interval_sec = get_refresh_config(session)
    if auto_refresh_enabled and st_autorefresh is not None:
        st_autorefresh(
            interval=auto_refresh_interval_sec * 1000,
            limit=None,
            key="main_page_auto_refresh",
            debounce=True,
        )

    log_col, stats_col = st.columns([3, 2], gap="medium")
    with log_col:
        logs = session.get_logs(limit=10)
        render_log_viewer(
            logs=logs,
            title="📋 Журнал событий",
            show_pending_warning=session.pending_events,
            on_clear=session.clear_logs,
            limit=10,
            compact_mode=True,
        )

    with stats_col:
        stats = get_file_stats_cached(redis_client, _cache_key=session.cache_buster)
        render_stats_panel(stats, show_progress=True, vertical=True)

    st.divider()
    st.subheader("📄 Реестр файлов")

    control_col1, control_col2 = st.columns([4, 1])
    with control_col1:
        status_text = "🟢 Авто" if auto_refresh_enabled else "⏸️ Пауза"
        st.caption(f"🔄 {status_text} | {auto_refresh_interval_sec:.0f}с | Кэш: 30с")
    with control_col2:
        if st.button("🔄 Обновить", key="refresh_files_btn", use_container_width=True, type="primary"):
            session.invalidate_cache()
            st.rerun()

    files = get_files_from_redis_cached(redis_client, _cache_key=session.cache_buster)
    render_file_list(files=files, session_state=session, mode="cards")
    session.update_refresh_time()


def render_sidebar(session: SessionState) -> None:
    """Render the sidebar controls."""
    with st.sidebar:
        st.header("⚙️ Настройки")
        render_refresh_settings(session, key_prefix="main")
        st.divider()

        st.subheader("🔍 Фильтры")
        status_filter = st.multiselect(
            "Статус",
            ["uploaded", "processing", "completed", "failed", "exported"],
            default=session.get_filter("status", []),
        )
        session.set_filter("status", status_filter)
        st.divider()

        st.subheader("📡 Статус")
        try:
            if hasattr(session.redis_client, "client") and session.redis_client.client:
                session.redis_client.client.ping()
                st.success("✅ Redis подключен")
            else:
                st.warning("⚠️ Redis клиент не инициализирован")
        except Exception as exc:
            st.error(f"❌ Redis: {exc}")

        st.divider()
        settings = session.settings if getattr(session, "settings", None) else get_settings()
        st.caption(f"📦 Algofusion v{settings.app_version}")
        st.caption(f"🌐 {settings.environment.upper()}")
