"""Log viewer component for the Streamlit UI."""

from __future__ import annotations

from textwrap import dedent
from typing import Callable, Dict, List, Optional

import streamlit as st

from shared.utils.logger import setup_logger
from ui.utils.constants import UI_CONFIG
from ui.utils.formatters import render_log_badge

logger = setup_logger("ui.components.log_viewer")


def render_log_viewer(
    logs: List[Dict[str, str]],
    title: str = "📋 Журнал событий",
    show_pending_warning: bool = False,
    on_clear: Optional[Callable] = None,
    limit: int | None = None,
    compact_mode: bool = False,
) -> None:
    """Render a log list with optional compact mode and clear action."""
    try:
        with st.container(border=True):
            header_col, action_col = st.columns([4, 1])
            with header_col:
                st.markdown(f"### {title}")
                if show_pending_warning:
                    st.warning("Есть новые события!", icon="🔔")

            with action_col:
                if on_clear and logs:
                    if st.button("🧹", key="clear_logs_btn", help="Очистить журнал"):
                        on_clear()
                        st.rerun()

            if not logs:
                from ui.utils.components import render_empty_state

                render_empty_state("Журнал событий пока пуст")
                return

            if compact_mode:
                st.markdown(
                    dedent(
                        """
                        <style>
                            .compact-logs {
                                max-height: 280px;
                                overflow-y: auto;
                                padding-right: 4px;
                                margin: -0.5rem -1rem -1rem -1rem;
                                padding: 0.5rem 1rem 1rem 1rem;
                            }
                            .compact-logs::-webkit-scrollbar {
                                width: 6px;
                            }
                            .compact-logs::-webkit-scrollbar-thumb {
                                background: #ccc;
                                border-radius: 3px;
                            }
                        </style>
                        <div class="compact-logs">
                        """
                    ).strip(),
                    unsafe_allow_html=True,
                )

            display_limit = limit or (10 if compact_mode else UI_CONFIG["max_logs_display"])
            for log in logs[-display_limit:]:
                _render_log_line(log)

            if compact_mode:
                st.markdown("</div>", unsafe_allow_html=True)

            if len(logs) > display_limit:
                st.caption(f"Показано последних {display_limit} из {len(logs)}")

    except Exception as exc:
        logger.error("Ошибка рендеринга логов: %s", exc, exc_info=True)
        st.warning("Не удалось отобразить журнал событий", icon="⚠️")


def _render_log_line(log: Dict[str, str]) -> None:
    """Render a single log line."""
    timestamp = log.get("time", "--:--:--")
    status = log.get("status", "INFO")
    message = log.get("msg", "")

    badge_html = render_log_badge(status)
    html = dedent(
        f"""
        <div style="
            font-family: monospace;
            margin-bottom: 6px;
            font-size: 12px;
            border-bottom: 1px solid #f0f0f0;
            padding-bottom: 4px;
        ">
            <span style="color: #888888;">{timestamp}</span>
            {badge_html}
            <span style="color: #333333;">{message}</span>
        </div>
        """
    ).strip()
    st.markdown(html, unsafe_allow_html=True)
