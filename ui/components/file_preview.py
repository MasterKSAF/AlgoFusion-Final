"""Simple preview helpers for logical file stages."""

from __future__ import annotations

import json
from typing import Any, Optional

import streamlit as st

from shared.utils.logger import setup_logger

logger = setup_logger("ui.components.file_preview")


def render_file_preview(
    file_service: Any,
    file_id: str,
    stage: str,
    original_filename: Optional[str] = None,
    storage_dir: Optional[str] = None,
) -> None:
    """Render a lightweight preview for a logical stage."""
    if not file_service:
        st.info("Preview is unavailable.")
        return

    path = file_service.get_download_path(file_id, stage, original_filename, storage_dir)
    if path is None or not path.exists():
        st.info(f"No files for stage '{stage}'.")
        return

    suffix = path.suffix.lower()
    st.caption(str(path))

    try:
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            st.image(str(path), use_container_width=True)
            return

        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            st.json(data, expanded=False)
            return

        if suffix in {".txt", ".md", ".log", ".csv", ".xml"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            st.code("\n".join(text.splitlines()[:60]), language="text")
            return

        if suffix == ".pdf":
            st.info("PDF preview is not embedded here. Use download or open the file from disk.")
            return

        st.info(f"Preview is not available for {suffix or 'this file type'}.")
    except Exception as exc:
        logger.warning("Failed to render preview for %s: %s", path, exc)
        st.info("Preview could not be rendered.")
