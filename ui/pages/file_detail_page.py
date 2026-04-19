"""Detailed view for a single file."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import streamlit as st

from shared.models.file import FileJob
from shared.utils.logger import setup_logger
from ui.cache import get_file_structure_cached
from ui.components.file_preview import render_file_preview
from ui.utils.constants import LOGICAL_STAGE_DIRS, REDIS_QUEUES
from ui.utils.formatters import (
    calculate_module_progress,
    format_datetime_full,
    format_file_size_human,
    render_status_badge,
)
from ui.utils.redis_helpers import push_job_to_queue, safe_get_all_files, safe_update_file_status

logger = setup_logger("ui.pages.file_detail_page")


def render_file_detail_page(session_state: Any) -> None:
    """Render the detail page for the selected file."""
    file_data = _get_selected_file(session_state)
    if not file_data:
        st.error("Selected file was not found.")
        if st.button("Back"):
            _go_back(session_state)
        return

    file_id = str(file_data.get("file_id", "unknown"))
    filename = str(file_data.get("original_filename", "unknown"))
    file_structure = get_file_structure_cached(
        session_state.file_service,
        file_id,
        file_data.get("original_filename"),
        file_data.get("storage_dir"),
        _cache_key=session_state.cache_buster,
    )

    top_left, top_right = st.columns([4, 1])
    top_left.title(filename)
    if top_right.button("Back", key="back_to_main", use_container_width=True):
        _go_back(session_state)

    st.caption(f"File ID: {file_id}")
    _render_summary(file_data)
    st.divider()

    progress, stages = calculate_module_progress(
        file_data.get("completed_modules", []),
        file_data.get("current_module"),
    )
    st.subheader("Pipeline progress")
    st.progress(progress / 100 if progress else 0.0)
    st.caption(" | ".join(stages))
    st.divider()

    st.subheader("Logical folders")
    _render_stage_tabs(session_state, file_data, file_structure)
    st.divider()

    st.subheader("Actions")
    _render_actions(session_state, file_data)


def _render_summary(file_data: Dict[str, Any]) -> None:
    status = str(file_data.get("status", "uploaded"))
    cols = st.columns(4)
    cols[0].markdown(f"Status: {render_status_badge(status)}", unsafe_allow_html=True)
    cols[1].metric("Current module", str(file_data.get("current_module") or "-"))
    cols[2].metric("File size", format_file_size_human(file_data.get("file_size")))
    cols[3].metric("Type", str(file_data.get("file_type") or "-"))

    meta_cols = st.columns(3)
    meta_cols[0].caption(f"Created: {format_datetime_full(file_data.get('created_at'))}")
    meta_cols[1].caption(f"Updated: {format_datetime_full(file_data.get('updated_at'))}")
    meta_cols[2].caption(f"Completed modules: {', '.join(file_data.get('completed_modules', [])) or '-'}")


def _render_stage_tabs(session_state: Any, file_data: Dict[str, Any], file_structure: Optional[Dict[str, Any]]) -> None:
    directories = (file_structure or {}).get("directories", {})
    stage_names = [stage for stage in ["original", *LOGICAL_STAGE_DIRS.keys()] if stage in directories]
    if not stage_names:
        st.info("No stage files are available yet.")
        return

    unique_stages = []
    for stage in stage_names:
        if stage not in unique_stages:
            unique_stages.append(stage)

    tabs = st.tabs([stage.title() for stage in unique_stages])
    for tab, stage in zip(tabs, unique_stages):
        with tab:
            stage_info = directories.get(stage, {})
            preview_col, files_col = st.columns([3, 2])

            with preview_col:
                render_file_preview(
                    session_state.file_service,
                    file_data["file_id"],
                    stage,
                    file_data.get("original_filename"),
                    file_data.get("storage_dir"),
                )

            with files_col:
                st.caption("Physical folders")
                for path in stage_info.get("paths", []):
                    st.code(path, language="text")

                st.caption("Files")
                files = stage_info.get("files", [])
                if not files:
                    st.info("No files in this stage.")
                else:
                    for item in files[:50]:
                        st.markdown(f"- `{item['relative_path']}`")

                _render_stage_download_button(session_state, file_data, stage)


def _render_stage_download_button(session_state: Any, file_data: Dict[str, Any], stage: str) -> None:
    path = session_state.file_service.get_download_path(
        file_data["file_id"],
        stage,
        file_data.get("original_filename"),
        file_data.get("storage_dir"),
    )
    if path is None or not path.exists():
        return

    with open(path, "rb") as handle:
        st.download_button(
            label=f"Download {stage}",
            data=handle.read(),
            file_name=path.name,
            mime=_guess_mime(path.name),
            key=f"download_stage_{file_data['file_id']}_{stage}",
            use_container_width=True,
        )


def _render_actions(session_state: Any, file_data: Dict[str, Any]) -> None:
    file_id = str(file_data["file_id"])
    cols = st.columns(3)

    if cols[0].button("Retry pipeline", key=f"retry_{file_id}", use_container_width=True):
        if _retry_file(session_state, file_data):
            st.success("File was re-queued from the first stage.")
            st.rerun()
        else:
            st.error("Retry failed.")

    _render_download_action(cols[1], session_state, file_data, "original", "Download original")
    _render_download_action(cols[2], session_state, file_data, "export", "Download final JSON")

    delete_col = st.columns(1)[0]
    if delete_col.button("Delete file outputs", key=f"delete_{file_id}", use_container_width=True):
        deleted = session_state.file_service.delete_file(
            file_id,
            file_data.get("original_filename"),
            file_data.get("storage_dir"),
        )
        if session_state.redis_client:
            session_state.redis_client.delete_file_status(file_id)
        if deleted:
            st.success("File outputs deleted.")
            _go_back(session_state)
            st.rerun()
        else:
            st.error("Delete failed.")


def _render_download_action(
    container: Any,
    session_state: Any,
    file_data: Dict[str, Any],
    stage: str,
    label: str,
) -> None:
    path = session_state.file_service.get_download_path(
        file_data["file_id"],
        stage,
        file_data.get("original_filename"),
        file_data.get("storage_dir"),
    )
    if path is None or not path.exists():
        container.button(label, disabled=True, key=f"disabled_{file_data['file_id']}_{stage}", use_container_width=True)
        return

    with open(path, "rb") as handle:
        container.download_button(
            label=label,
            data=handle.read(),
            file_name=path.name,
            mime=_guess_mime(path.name),
            key=f"action_download_{file_data['file_id']}_{stage}",
            use_container_width=True,
        )


def _retry_file(session_state: Any, file_data: Dict[str, Any]) -> bool:
    try:
        payload = dict(file_data)
        payload.update(
            {
                "status": "processing",
                "current_module": "pipeline_v2",
                "completed_modules": [],
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "retry_count": int(file_data.get("retry_count", 0)) + 1,
            }
        )
        job = FileJob.from_payload(json.dumps(payload, ensure_ascii=False))
        if session_state.redis_client:
            safe_update_file_status(session_state.redis_client, job.file_id, payload)
            return push_job_to_queue(
                session_state.redis_client,
                REDIS_QUEUES["preprocessed"],
                job.to_payload(),
                priority=10,
            )
        return False
    except Exception as exc:
        logger.error("Retry failed for %s: %s", file_data.get("file_id"), exc, exc_info=True)
        return False


def _get_selected_file(session_state: Any) -> Optional[Dict[str, Any]]:
    files = safe_get_all_files(session_state.redis_client) if session_state.redis_client else []
    selected_file_id = getattr(session_state, "selected_file_id", None)

    if selected_file_id:
        for file_data in files:
            if str(file_data.get("file_id")) == str(selected_file_id):
                return file_data

    index = getattr(session_state, "editing_file_index", None)
    if index is not None and 0 <= index < len(files):
        return files[index]

    return None


def _go_back(session_state: Any) -> None:
    session_state.current_page = "main"
    session_state.editing_file_index = None
    session_state.selected_file_id = None


def _guess_mime(filename: str) -> str:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    return {
        "pdf": "application/pdf",
        "json": "application/json",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "txt": "text/plain",
    }.get(suffix, "application/octet-stream")
