"""File list component using the older card layout with pipeline_v2 semantics."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Literal, Optional

import streamlit as st

from shared.utils.logger import setup_logger
from ui.utils.components import error_handler, render_action_button, render_columns_config, render_empty_state
from ui.utils.constants import FILE_STATUS_CONFIG, MODULES_ORDER, UI_CONFIG, get_completed_logical_stages
from ui.utils.formatters import (
    format_datetime_short,
    format_file_size,
    get_current_logical_stage,
    render_module_badge_safe,
    render_status_badge_safe,
    truncate_filename,
)

logger = setup_logger("ui.components.file_list")


def render_file_list(
    files: List[Dict[str, Any]],
    session_state: Any,
    mode: Literal["table", "cards"] = "table",
    on_detail: Optional[Callable[[str], None]] = None,
    on_retry: Optional[Callable[[str], None]] = None,
    on_delete: Optional[Callable[[str], None]] = None,
    on_download_preprocessed: Optional[Callable[[str], None]] = None,
    on_edit: Optional[Callable[[str], None]] = None,
    on_export: Optional[Callable[[str], None]] = None,
) -> None:
    """Render a file list in table or card mode."""
    del on_retry, on_delete, on_download_preprocessed, on_export
    with error_handler("file_list", "Ошибка отображения списка файлов"):
        file_service = getattr(session_state, "file_service", None)

        if not files:
            render_empty_state("Файлы пока не загружены. Ожидание новых файлов...")
            return

        if mode == "table":
            _render_table_mode(files, session_state, on_detail)
        else:
            _render_cards_mode(files, session_state, file_service, on_detail, on_edit)


def _render_table_mode(
    files: List[Dict[str, Any]],
    session_state: Any,
    on_detail: Optional[Callable[[str], None]],
) -> None:
    cols = render_columns_config([2, 3, 2, 2, 2, 1])
    headers = ["ID", "Файл", "Статус", "Этап", "Время", "Действия"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    st.divider()

    display_files = files[-UI_CONFIG["max_files_display"] :]
    for file_data in reversed(display_files):
        _render_table_row(file_data, session_state, on_detail)
        st.divider()


def _render_table_row(
    file_data: Dict[str, Any],
    session_state: Any,
    on_detail: Optional[Callable[[str], None]],
) -> None:
    file_id = file_data.get("file_id", "unknown")
    filename = file_data.get("original_filename", "Unknown")
    status = file_data.get("status", "unknown")
    current_stage = get_current_logical_stage(file_data) or "-"
    created_at = format_datetime_short(file_data.get("created_at"))

    cols = render_columns_config([2, 3, 2, 2, 2, 1])
    cols[0].code(str(file_id)[:12], language="text")
    cols[1].markdown(f"📄 {truncate_filename(str(filename))}")
    render_status_badge_safe(str(status), cols[2])
    cols[3].markdown(f"`{current_stage}`" if current_stage else "-")
    cols[4].markdown(created_at)

    if render_action_button("📋", key=f"detail_{file_id}", help="Детали файла"):
        if on_detail:
            on_detail(str(file_id))
        else:
            _default_navigate_to_detail(str(file_id), session_state)


def _render_cards_mode(
    files: List[Dict[str, Any]],
    session_state: Any,
    file_service: Optional[Any],
    on_detail: Optional[Callable[[str], None]],
    on_edit: Optional[Callable[[str], None]] = None,
) -> None:
    """Card layout copied from the older UI, adapted to logical stages."""
    st.caption(f"📄 Найдено файлов: {len(files)}")

    for idx, file_data in enumerate(files):
        _render_file_card(file_data, idx, session_state, file_service, on_detail, on_edit)


def _render_file_card(
    file_data: Dict[str, Any],
    idx: int,
    session_state: Any,
    file_service: Optional[Any],
    on_detail: Optional[Callable[[str], None]] = None,
    on_edit: Optional[Callable[[str], None]] = None,
) -> None:
    file_id = str(file_data.get("file_id", f"file_{idx}"))
    filename = str(file_data.get("original_filename", "unknown"))
    file_size = file_data.get("file_size", 0)
    status = str(file_data.get("status", "unknown"))
    created_at = format_datetime_short(file_data.get("created_at"))
    size_formatted = format_file_size(file_size)

    status_icon = {
        "uploaded": "📃",
        "processing": "⏳",
        "completed": "✅",
        "exported": "📤",
        "failed": "❌",
    }.get(status, "❓")

    status_config = FILE_STATUS_CONFIG.get(status, FILE_STATUS_CONFIG["uploaded"])
    status_label = status_config["label"]
    status_color = status_config["color"]
    status_bg = status_config["bg"]

    header_left, header_right = st.columns([4, 1], gap="small")
    with header_left:
        st.markdown(f"**{status_icon} {truncate_filename(filename, 40)}**")
    with header_right:
        badge_html = f"""
        <span style="
            background-color: {status_bg};
            color: {status_color};
            padding: 3px 8px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 10px;
            white-space: nowrap;
        ">
            {status_label}
        </span>
        """
        st.markdown(badge_html, unsafe_allow_html=True)

    with st.expander("📊 Детали", expanded=False):
        info_col1, info_col2, info_col3 = st.columns(3, gap="small")
        with info_col1:
            st.caption("🆔 ID")
            st.code(file_id[:12], language="text")
        with info_col2:
            st.caption("📅 Загружен")
            st.write(f"`{created_at}`")
        with info_col3:
            st.caption("📦 Размер")
            st.write(f"`{size_formatted}`")

        st.markdown("##### 🔄 Прогресс обработки")
        completed_stages = get_completed_logical_stages(file_data.get("completed_modules", []))
        current_stage = get_current_logical_stage(file_data) or ""

        def get_module_status(module_name: str) -> str:
            if status == "failed":
                return "failed"
            if module_name in completed_stages:
                return "completed"
            if module_name == current_stage:
                return "processing"
            return "pending"

        module_cols = st.columns(len(MODULES_ORDER), gap="small")
        for i, module_name in enumerate(MODULES_ORDER):
            render_module_badge_safe(
                module=module_name,
                status=get_module_status(module_name),
                container=module_cols[i],
                size="small",
                show_tooltip=True,
            )

        if status == "processing" and current_stage:
            st.caption(f"⏳ Сейчас: {current_stage}")
        elif status in {"completed", "exported"}:
            st.caption("✅ Все этапы завершены")
        elif status == "failed":
            st.caption("❌ Ошибка обработки")

        st.divider()

        st.markdown("##### 📋 Классификация")
        try:
            from ui.components.classification_badge import render_classification_info

            render_classification_info(file_data, container=st)
        except Exception as exc:
            logger.debug("Classification badge skipped for %s: %s", file_id, exc)
            st.caption("Классификация недоступна")

        st.divider()
        st.markdown("##### ⚙️ Действия")

        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4, gap="small")
        with btn_col1:
            _render_download_button(
                file_service,
                file_id,
                "original",
                file_data,
                "📥 Оригинал",
                f"dl_orig_{idx}",
                filename,
            )
        with btn_col2:
            _render_download_button(
                file_service,
                file_id,
                "preprocessed",
                file_data,
                "📥 Результат",
                f"dl_prep_{idx}",
                f"{filename}_processed.png",
            )
        with btn_col3:
            if on_edit and st.button("✏️ Править", key=f"edit_{idx}", use_container_width=True, help="Редактировать файл"):
                on_edit(file_id)
            elif not on_edit:
                st.button("✏️ Править", key=f"edit_{idx}", disabled=True, use_container_width=True)
        with btn_col4:
            _render_download_button(
                file_service,
                file_id,
                "export",
                file_data,
                "📥 JSON",
                f"export_{idx}",
                f"{file_id}.json",
                mime="application/json",
            )

        detail_col = st.columns(1)[0]
        if detail_col.button("📋 Открыть детали", key=f"details_{file_id}", use_container_width=True):
            if on_detail:
                on_detail(file_id)
            else:
                _default_navigate_to_detail(file_id, session_state)


def _render_download_button(
    file_service: Optional[Any],
    file_id: str,
    stage: str,
    file_data: Dict[str, Any],
    label: str,
    key: str,
    default_name: str,
    mime: Optional[str] = None,
) -> None:
    if not file_service:
        st.button(label, key=key, disabled=True, use_container_width=True)
        return

    path = file_service.get_download_path(
        file_id,
        stage,
        file_data.get("original_filename"),
        file_data.get("storage_dir"),
    )
    if path is None or not path.exists():
        st.button(label, key=key, disabled=True, use_container_width=True)
        return

    with open(path, "rb") as f:
        st.download_button(
            label=label,
            data=f.read(),
            file_name=path.name if path.name else default_name,
            mime=mime or _guess_mime(path),
            key=key,
            use_container_width=True,
        )


def _default_navigate_to_detail(file_id: str, session_state: Any) -> None:
    """Default file-detail navigation when no external callback is provided."""
    session_state.selected_file_id = file_id
    session_state.current_page = "detail"
    st.rerun()


def _guess_mime(path) -> str:
    suffix = path.suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".json": "application/json",
        ".txt": "text/plain",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(suffix, "application/octet-stream")
