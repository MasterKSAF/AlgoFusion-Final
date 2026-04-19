from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class ResourceRegistry:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parent

    def resolve(self, relative_path: str | Path) -> Path:
        path = self.root / Path(relative_path)
        if not path.exists():
            raise FileNotFoundError(f"Resource not found: {path}")
        return path

    @lru_cache(maxsize=128)
    def load_yaml(self, relative_path: str) -> Any:
        path = self.resolve(relative_path)
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def load_dictionary(self, name: str) -> dict[str, Any]:
        return self.load_yaml(f"dictionaries/{name}.yaml")

    def list_dictionary_values(self, name: str, key: str = "values") -> list[str]:
        payload = self.load_dictionary(name)
        values = payload.get(key, [])
        if not isinstance(values, list):
            raise ValueError(f"Dictionary {name} key {key} must be a list")
        return [str(item) for item in values]


_registry: ResourceRegistry | None = None


def get_resource_registry() -> ResourceRegistry:
    global _registry
    if _registry is None:
        _registry = ResourceRegistry()
    return _registry
