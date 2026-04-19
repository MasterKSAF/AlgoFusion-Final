"""Centralized logging helpers with a loguru-first backend."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

try:
    from loguru import logger as _loguru_logger
except ImportError:  # pragma: no cover
    _loguru_logger = None

_std_loggers: dict[str, logging.Logger] = {}
_loguru_configured = False
_MOJIBAKE_MARKERS = (
    "\u0420\u00a0",
    "\u0420\u040e",
    "\u0420\u0406\u0420\u201a",
    "\xa0",
)


def _repair_mojibake(text: str) -> str:
    repaired = text
    for _ in range(2):
        if not any(marker in repaired for marker in _MOJIBAKE_MARKERS):
            break
        try:
            candidate = repaired.encode("cp1251", errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            break
        if not candidate or candidate == repaired:
            break
        repaired = candidate
    return repaired


def _format_message(message: Any, args: tuple[Any, ...], context: dict[str, Any] | None = None) -> str:
    if args:
        try:
            rendered = str(message) % args
        except Exception:
            rendered = " ".join([str(message), *[str(arg) for arg in args]])
    else:
        rendered = str(message)
    rendered = _repair_mojibake(rendered)
    if context:
        suffix = " | ".join(f"{key}={value}" for key, value in context.items())
        if suffix:
            rendered = f"{rendered} | {suffix}"
    return rendered


def _configure_loguru(level: str, format_type: str) -> None:
    global _loguru_configured
    if _loguru_logger is None or _loguru_configured:
        return
    _loguru_logger.remove()
    if format_type == "json":
        _loguru_logger.add(sys.stdout, level=level.upper(), serialize=True, enqueue=False)
    else:
        _loguru_logger.add(
            sys.stdout,
            level=level.upper(),
            enqueue=False,
            format="{time:YYYY-MM-DD HH:mm:ss} | {extra[service]} | {level: <8} | {message}",
        )
    _loguru_configured = True


class _LoguruCompatLogger:
    def __init__(self, name: str, context: dict[str, Any] | None = None):
        self.name = name
        self.context = context or {}

    def bind_context(self, **context: Any) -> "_LoguruCompatLogger":
        merged = dict(self.context)
        merged.update(context)
        return _LoguruCompatLogger(self.name, merged)

    def _emit(self, level: str, message: Any, *args: Any, exception: Any = None, **kwargs: Any) -> None:
        rendered = _format_message(message, args, self.context)
        service = os.getenv("SERVICE_NAME", "algofusion")
        bound = _loguru_logger.bind(service=service, logger_name=self.name)
        if exception:
            bound.opt(exception=exception).log(level.upper(), rendered)
        else:
            bound.log(level.upper(), rendered)

    def debug(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._emit("DEBUG", message, *args, **kwargs)

    def info(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._emit("INFO", message, *args, **kwargs)

    def warning(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._emit("WARNING", message, *args, **kwargs)

    def error(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._emit("ERROR", message, *args, exception=kwargs.pop("exc_info", None), **kwargs)

    def critical(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._emit("CRITICAL", message, *args, exception=kwargs.pop("exc_info", None), **kwargs)

    def exception(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._emit("ERROR", message, *args, exception=True, **kwargs)


def _setup_stdlib_logger(name: str, level: str) -> logging.Logger:
    if name in _std_loggers:
        return _std_loggers[name]
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    _std_loggers[name] = logger
    return logger


def setup_logger(name: str, level: str | None = None):
    level = level or os.getenv("LOG_LEVEL", "INFO")
    format_type = os.getenv("LOG_FORMAT", "text")
    if _loguru_logger is not None:
        _configure_loguru(level, format_type)
        return _LoguruCompatLogger(name)
    return _setup_stdlib_logger(name, level)


def get_logger(name: str, level: str | None = None, format_type: str | None = None):
    if format_type is not None:
        os.environ["LOG_FORMAT"] = format_type
    return setup_logger(name, level=level)


def logger_with_context(logger, **context: Any):
    if isinstance(logger, _LoguruCompatLogger):
        return logger.bind_context(**context)
    return logging.LoggerAdapter(logger, context)


__all__ = ["get_logger", "logger_with_context", "setup_logger"]
