"""Pydantic models used by the Algofusion UI API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FieldUpdateRequest(BaseModel):
    """Review draft changes keyed by dotted field paths."""

    fields: dict[str, Any] = Field(default_factory=dict)

