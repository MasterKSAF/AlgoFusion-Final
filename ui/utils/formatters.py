"""Formatting helpers for the UI."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, TYPE_CHECKING, Union

from ui.utils.constants import (
    EXPORT_STATUS_CONFIG,
    FILE_STATUS_CONFIG,
    LOGICAL_STAGE_LABELS,
    LOGICAL_STAGE_ORDER,
    LOG_STATUS_CONFIG,
    MODULE_ICONS,
    MODULE_STATUS_COLORS,
    PIPELINE_V2_MODULES,
    UI_CONFIG,
    get_completed_logical_stages,
    map_module_to_logical_stage,
    normalize_completed_modules,
)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def format_datetime_short(value: Optional[Union[datetime, str]]) -> str:
    """Format a date value for compact UI display."""
    dt = _parse_datetime(value)
    return dt.strftime(UI_CONFIG["datetime_format_short"]) if dt else "-"


def format_datetime_full(value: Optional[Union[datetime, str]]) -> str:
    """Format a date value for detailed UI display."""
    dt = _parse_datetime(value)
    return dt.strftime(UI_CONFIG["datetime_format_full"]) if dt else "-"


def format_file_size_human(size_bytes: Optional[int]) -> str:
    """Format byte counts in a human-readable way."""
    if size_bytes is None:
        return "-"
    size = float(max(size_bytes, 0))
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def format_file_size(size_bytes: Optional[int]) -> str:
    """Alias for human-readable byte formatting."""
    return format_file_size_human(size_bytes)


def render_status_badge(status: str, with_tooltip: bool = True, size: str = "normal") -> str:
    """Return HTML for a styled file-status badge."""
    config = FILE_STATUS_CONFIG.get(status, FILE_STATUS_CONFIG["uploaded"])
    style = _badge_style(size)
    tooltip = f' title="{config["label"]}"' if with_tooltip else ""
    return (
        f'<span style="background-color:{config["bg"]};color:{config["color"]};'
        f'padding:{style["padding"]};border-radius:{style["radius"]};font-weight:600;'
        f'font-size:{style["font_size"]};display:inline-block;white-space:nowrap;"{tooltip}>'
        f'{config["emoji"]} {config["label"]}</span>'
    )


def render_status_badge_safe(
    status: str,
    container: "DeltaGenerator",
    with_tooltip: bool = True,
    size: str = "normal",
) -> None:
    """Render a status badge directly into a Streamlit container."""
    container.markdown(render_status_badge(status, with_tooltip=with_tooltip, size=size), unsafe_allow_html=True)


def render_export_status_badge(status: str, with_tooltip: bool = True) -> str:
    """Return HTML for a result-status badge."""
    config = EXPORT_STATUS_CONFIG.get(status, EXPORT_STATUS_CONFIG["pending"])
    colors = {
        "pending": ("#475569", "#E2E8F0"),
        "exporting": ("#8A5A00", "#FEF3C7"),
        "success": ("#166534", "#DCFCE7"),
        "failed": ("#991B1B", "#FEE2E2"),
    }
    color, bg = colors.get(status, colors["pending"])
    tooltip = f' title="{config["label"]}"' if with_tooltip else ""
    return (
        f'<span style="background-color:{bg};color:{color};padding:3px 8px;'
        f'border-radius:10px;font-weight:500;font-size:11px;display:inline-block;"{tooltip}>'
        f'{config["emoji"]} {config["label"]}</span>'
    )


def render_export_status_badge_safe(status: str, container: "DeltaGenerator", with_tooltip: bool = True) -> None:
    """Render a result badge directly into a Streamlit container."""
    container.markdown(render_export_status_badge(status, with_tooltip=with_tooltip), unsafe_allow_html=True)


def render_module_badge(module: str, status: str, size: str = "small", show_tooltip: bool = True) -> str:
    """Render a logical-stage badge with the old UI look."""
    icon = MODULE_ICONS.get(module, "⚙️")
    color, bg = MODULE_STATUS_COLORS.get(status, MODULE_STATUS_COLORS["pending"])
    style = _badge_style(size)
    label = LOGICAL_STAGE_LABELS.get(module, module)
    tooltip = f' title="{label}: {status}"' if show_tooltip else ""
    return (
        f'<span style="background-color:{bg};color:{color};padding:{style["padding"]};'
        f'border-radius:{style["radius"]};font-weight:500;font-size:{style["font_size"]};'
        f'display:inline-block;white-space:nowrap;margin-right:4px;"{tooltip}>{icon}</span>'
    )


def render_module_badge_safe(
    module: str,
    status: str,
    container: "DeltaGenerator",
    size: str = "small",
    show_tooltip: bool = True,
) -> None:
    """Render a module badge into a Streamlit container."""
    container.markdown(
        render_module_badge(module, status, size=size, show_tooltip=show_tooltip),
        unsafe_allow_html=True,
    )


def render_module_progress_badge(module: str, is_completed: bool, is_current: bool, size: str = "small") -> str:
    """Convenience wrapper for rendering a module badge from booleans."""
    if is_completed:
        status = "completed"
    elif is_current:
        status = "processing"
    else:
        status = "pending"
    return render_module_badge(module, status, size=size)


def render_module_progress_badge_safe(
    module: str,
    is_completed: bool,
    is_current: bool,
    container: "DeltaGenerator",
    size: str = "small",
) -> None:
    """Streamlit-safe wrapper for module progress badge rendering."""
    container.markdown(
        render_module_progress_badge(module, is_completed, is_current, size=size),
        unsafe_allow_html=True,
    )


def render_log_badge(status: str) -> str:
    """Return a plain colored badge for log severity."""
    config = LOG_STATUS_CONFIG.get(status, LOG_STATUS_CONFIG["INFO"])
    return f'<span style="color:{config["color"]};font-weight:bold;">{config["emoji"]} {status}</span>'


def truncate_filename(filename: str, max_length: int = 40, suffix: str = "...") -> str:
    """Truncate long filenames while keeping both ends visible."""
    if len(filename) <= max_length:
        return filename
    prefix_length = max(8, (max_length - len(suffix)) // 2)
    suffix_length = max_length - len(suffix) - prefix_length
    return f"{filename[:prefix_length]}{suffix}{filename[-suffix_length:]}"


def calculate_module_progress(completed_modules: Iterable[str], current_module: Optional[str]) -> tuple[int, list[str]]:
    """Return logical pipeline progress and human-readable stage states."""
    completed_physical = normalize_completed_modules(completed_modules)
    completed_stages = get_completed_logical_stages(completed_physical)
    current_stage = map_module_to_logical_stage(current_module)

    if current_module in PIPELINE_V2_MODULES and current_module not in completed_physical:
        statuses = [f"🔄 {LOGICAL_STAGE_LABELS.get(stage, stage)}" for stage in LOGICAL_STAGE_ORDER]
        return 50, statuses

    completed_count = 0
    statuses: list[str] = []
    for stage in LOGICAL_STAGE_ORDER:
        label = LOGICAL_STAGE_LABELS.get(stage, stage)
        if stage in completed_stages:
            statuses.append(f"✅ {label}")
            completed_count += 1
        elif current_stage == stage:
            statuses.append(f"🔄 {label}")
        else:
            statuses.append(f"⏳ {label}")

    total = len(LOGICAL_STAGE_ORDER)
    if total == 0:
        return 0, statuses

    progress = completed_count / total * 100
    if current_stage and current_stage not in completed_stages:
        progress = min(progress + 0.5 * (100 / total), 99.0)

    return int(progress), statuses


def get_current_logical_stage(file_data: dict) -> Optional[str]:
    """Return the current logical stage for a file payload."""
    return map_module_to_logical_stage(file_data.get("current_module"))


def get_completed_logical_stage_labels(file_data: dict) -> list[str]:
    """Return completed logical stages in display order."""
    completed_stages = get_completed_logical_stages(file_data.get("completed_modules", []))
    return [stage for stage in LOGICAL_STAGE_ORDER if stage in completed_stages]


def _parse_datetime(value: Optional[Union[datetime, str]]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _badge_style(size: str) -> dict[str, str]:
    sizes = UI_CONFIG.get("badge_sizes", {})
    return sizes.get(size, sizes.get("normal", {"padding": "4px 10px", "font_size": "11px", "radius": "12px"}))
