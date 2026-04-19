"""Conservative fuzzy matching helpers for OCR cleanup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from rapidfuzz import fuzz, process


@dataclass(frozen=True)
class FuzzyMatchResult:
    value: str | None
    score: float
    accepted: bool


def best_match(
    candidate: str,
    choices: Iterable[str],
    *,
    threshold: float = 92.0,
) -> FuzzyMatchResult:
    normalized_candidate = candidate.strip()
    normalized_choices = [choice.strip() for choice in choices if str(choice).strip()]
    if not normalized_candidate or not normalized_choices:
        return FuzzyMatchResult(value=None, score=0.0, accepted=False)
    match = process.extractOne(
        normalized_candidate,
        normalized_choices,
        scorer=fuzz.WRatio,
    )
    if not match:
        return FuzzyMatchResult(value=None, score=0.0, accepted=False)
    value, score, _ = match
    return FuzzyMatchResult(value=value, score=float(score), accepted=float(score) >= threshold)


def normalize_candidate(
    candidate: str,
    choices: Iterable[str],
    *,
    threshold: float = 92.0,
) -> str | None:
    result = best_match(candidate, choices, threshold=threshold)
    return result.value if result.accepted else None
