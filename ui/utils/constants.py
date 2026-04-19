"""Central UI constants and logical stage mapping for pipeline_v2."""

from __future__ import annotations

from typing import Iterable

LOGICAL_STAGE_ORDER = ["preprocessed", "ocr", "llm", "export"]
MODULES_ORDER = LOGICAL_STAGE_ORDER

LOGICAL_STAGE_LABELS = {
    "original": "Original",
    "preprocessed": "Preprocessed",
    "ocr": "OCR",
    "llm": "LLM",
    "export": "Export",
}

MODULE_ICONS = {
    "preprocessed": "⚙️",
    "ocr": "🔤",
    "llm": "🧠",
    "export": "📦",
    "validate": "✅",
    "parse": "📋",
}

MODULE_STATUS_EMOJI = {
    "completed": "✅",
    "processing": "🔄",
    "pending": "⏳",
    "failed": "❌",
}

MODULE_STATUS_COLORS = {
    "completed": ("#155724", "#d4edda"),
    "processing": ("#856404", "#fff3cd"),
    "pending": ("#6c757d", "#e9ecef"),
    "failed": ("#721c24", "#f8d7da"),
}

LOGICAL_STAGE_DIRS = {
    "original": ["original"],
    "preprocessed": ["cleaner", "out_table_merge"],
    "ocr": ["final_rebuilt_auto"],
    "llm": ["data/pred", "data/pred_normalized", "data/pred_reconciled"],
    "export": ["data/final_json"],
}

PIPELINE_V2_MODULES = {"pipeline_v2"}

MODULE_TO_LOGICAL_STAGE = {
    "cleaner": "preprocessed",
    "layout": "preprocessed",
    "ocr": "ocr",
    "parser": "llm",
    "normalizer": "llm",
    "reconcile": "llm",
    "final_json": "export",
    "pipeline_v2": "export",
}

LOGICAL_STAGE_REQUIREMENTS = {
    "preprocessed": {"cleaner", "layout"},
    "ocr": {"ocr"},
    "llm": {"parser", "normalizer", "reconcile"},
    "export": {"final_json"},
}

FILE_STATUS_CONFIG = {
    "uploaded": {"emoji": "🔵", "label": "Загружен", "color": "#004085", "bg": "#cce5ff"},
    "processing": {"emoji": "🟡", "label": "В обработке", "color": "#856404", "bg": "#fff3cd"},
    "completed": {"emoji": "🟢", "label": "Завершен", "color": "#155724", "bg": "#d4edda"},
    "failed": {"emoji": "🔴", "label": "Ошибка", "color": "#721c24", "bg": "#f8d7da"},
    "exported": {"emoji": "🟣", "label": "Экспортирован", "color": "#5a3d7a", "bg": "#e2d5f1"},
}

EXPORT_STATUS_CONFIG = {
    "pending": {"emoji": "⏳", "label": "Ожидает"},
    "exporting": {"emoji": "🔄", "label": "Формируется"},
    "success": {"emoji": "✅", "label": "Готово"},
    "failed": {"emoji": "❌", "label": "Ошибка"},
}

LOG_STATUS_CONFIG = {
    "OK": {"emoji": "✅", "color": "#28a745"},
    "ERROR": {"emoji": "❌", "color": "#dc3545"},
    "WARNING": {"emoji": "⚠️", "color": "#ffc107"},
    "INFO": {"emoji": "ℹ️", "color": "#6c757d"},
}

UI_CONFIG = {
    "max_files_display": 50,
    "max_logs_display": 20,
    "max_processing_display": 10,
    "datetime_format_short": "%Y-%m-%d %H:%M",
    "datetime_format_full": "%Y-%m-%d %H:%M:%S",
    "text_preview_lines": 60,
    "max_preview_bytes": 10 * 1024 * 1024,
    "badge_sizes": {
        "small": {"padding": "3px 6px", "font_size": "10px", "radius": "6px"},
        "normal": {"padding": "4px 10px", "font_size": "11px", "radius": "12px"},
        "large": {"padding": "6px 14px", "font_size": "13px", "radius": "16px"},
    },
}

REDIS_CHANNELS = {
    "events": "files:events",
    "export": "1c:export",
}

REDIS_QUEUES = {
    "preprocessed": "files:pipeline_v2",
    "ocr": "files:pipeline_v2",
    "llm": "files:pipeline_v2",
    "export": "files:pipeline_v2",
}


def map_module_to_logical_stage(module: str | None) -> str | None:
    """Map a physical pipeline module to the logical UI stage."""
    if not module:
        return None
    return MODULE_TO_LOGICAL_STAGE.get(module, module)


def normalize_completed_modules(completed_modules: Iterable[str] | None) -> set[str]:
    """Normalize completed modules to a set of non-empty strings."""
    if completed_modules is None:
        return set()
    return {str(module) for module in completed_modules if module}


def get_completed_logical_stages(completed_modules: Iterable[str] | None) -> set[str]:
    """Return logical stages satisfied by completed physical modules."""
    completed = normalize_completed_modules(completed_modules)
    if completed & PIPELINE_V2_MODULES:
        return set(LOGICAL_STAGE_ORDER)

    done: set[str] = set()
    for stage, required_modules in LOGICAL_STAGE_REQUIREMENTS.items():
        if required_modules.issubset(completed):
            done.add(stage)
    return done


def get_pending_logical_stages(completed_modules: Iterable[str] | None) -> list[str]:
    """Return logical stages that are still pending."""
    completed_stages = get_completed_logical_stages(completed_modules)
    return [stage for stage in LOGICAL_STAGE_ORDER if stage not in completed_stages]


def is_stage_complete(stage: str, completed_modules: Iterable[str] | None) -> bool:
    """Check whether a logical stage is complete."""
    return stage in get_completed_logical_stages(completed_modules)
