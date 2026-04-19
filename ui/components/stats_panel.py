"""Statistics panel for the pipeline_v2 UI."""

from __future__ import annotations

from textwrap import dedent
from typing import Any, Dict, List

import streamlit as st


def render_stats_panel(
    stats: Dict[str, Any],
    show_progress: bool = True,
    vertical: bool = True,
) -> None:
    """Render pipeline statistics in vertical or horizontal layout."""
    items = _build_stats_items(stats)
    if vertical:
        _render_vertical_stats(items, stats, show_progress)
    else:
        _render_horizontal_stats(items, stats, show_progress)


def _build_stats_items(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"label": "Загружено", "value": int(stats.get("uploaded", 0)), "color": "#17a2b8", "emoji": "📥"},
        {"label": "В обработке", "value": int(stats.get("processing", 0)), "color": "#fd7e14", "emoji": "⏳"},
        {"label": "Завершено", "value": int(stats.get("completed", 0)), "color": "#28a745", "emoji": "✅"},
        {"label": "Ошибки", "value": int(stats.get("failed", 0)), "color": "#dc3545", "emoji": "❌"},
        {"label": "Всего", "value": int(stats.get("total", 0)), "color": "#6c757d", "emoji": "📊"},
    ]


def _emoji_span(emoji: str) -> str:
    return dedent(
        f"""
        <span style="
            font-family: 'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', sans-serif;
            display: inline-block;
            min-width: 1.4em;
            text-align: center;
            line-height: 1;
            vertical-align: -0.05em;
            margin-right: 6px;
        ">{emoji}</span>
        """
    ).strip()


def _html_block(html: str) -> str:
    return dedent(html).strip()


def _render_vertical_stats(items: List[Dict[str, Any]], stats: Dict[str, Any], show_progress: bool) -> None:
    with st.container(border=True):
        st.markdown("##### 📊 Статистика обработки")

        for item in items:
            color = item["color"]
            card_html = _html_block(
                f"""
                <div style="
                    margin-bottom: 10px;
                    padding: 10px 12px;
                    border-radius: 8px;
                    background-color: #f8f9fa;
                    border-left: 4px solid {color};
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 12px;
                ">
                    <div style="
                        font-size: 18px;
                        font-weight: 600;
                        color: #333333;
                        flex: 1;
                        display: flex;
                        align-items: center;
                    ">
                        {_emoji_span(item["emoji"])}
                        <span>{item["label"]}</span>
                    </div>
                    <div style="
                        font-size: 28px;
                        font-weight: 700;
                        color: {color};
                        min-width: 60px;
                        text-align: right;
                    ">
                        {item["value"]}
                    </div>
                </div>
                """
            )
            st.markdown(card_html, unsafe_allow_html=True)

        if show_progress:
            st.divider()
            success_rate = str(stats.get("success_rate", "0%"))
            info_html = _html_block(
                f"""
                <div style="
                    font-size: 15px;
                    font-weight: 600;
                    color: #28a745;
                    margin-bottom: 6px;
                ">
                    ✨ Успешность завершённых: {success_rate}
                </div>
                """
            )
            st.markdown(info_html, unsafe_allow_html=True)
            try:
                value = float(success_rate.replace("%", "").strip()) / 100.0
            except Exception:
                value = 0.0
            st.progress(max(0.0, min(1.0, value)))


def _render_horizontal_stats(items: List[Dict[str, Any]], stats: Dict[str, Any], show_progress: bool) -> None:
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        with col:
            st.metric(f'{item["emoji"]} {item["label"]}', item["value"])

    if show_progress:
        st.divider()
        success_rate = str(stats.get("success_rate", "0%"))
        try:
            value = float(success_rate.replace("%", "").strip()) / 100.0
        except Exception:
            value = 0.0
        st.progress(max(0.0, min(1.0, value)))
        st.caption(f"Успешность завершённых: {success_rate}")
