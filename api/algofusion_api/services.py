"""Artifact-backed data access for the production UI."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEW_MARKER = "\u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u043f\u043e\u043b\u0435"
INVALID_MARKERS = (
    "invalid",
    "\u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d",
    "\u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d",
    "\u043e\u0448\u0438\u0431\u043a",
)


@dataclass(frozen=True)
class RunRootCandidate:
    path: Path
    document_count: int
    modified_at: float


class ArtifactService:
    """Read Algofusion run artifacts and expose UI-ready summaries."""

    def __init__(self, shared_files_path: Path, run_root: Path):
        self.shared_files_path = shared_files_path.resolve()
        self.run_root = run_root.resolve()

    @classmethod
    def from_env(cls) -> "ArtifactService":
        shared_files = Path(os.getenv("SHARED_FILES_PATH", "shared/files"))
        configured_run_root = os.getenv("ALGOFUSION_RUN_ROOT")
        run_root = Path(configured_run_root) if configured_run_root else cls._detect_run_root(shared_files)
        return cls(shared_files, run_root)

    def health(self) -> dict[str, object]:
        docs = self._document_dirs()
        return {
            "ok": self.run_root.exists(),
            "shared_files_path": str(self.shared_files_path),
            "run_root": str(self.run_root),
            "document_count": len(docs),
            "has_summary": (self.run_root / "summary.json").exists(),
        }

    def stats(self) -> dict[str, object]:
        documents = self.list_documents(limit=1000)
        total = len(documents)
        completed = sum(1 for item in documents if item["status"] == "completed")
        processing = sum(1 for item in documents if item["status"] == "processing")
        failed = sum(1 for item in documents if item["status"] == "failed")
        ready = sum(1 for item in documents if item["ready_to_export"])
        by_type: dict[str, int] = {}
        for item in documents:
            doc_type = str(item["document_type"] or "unknown")
            by_type[doc_type] = by_type.get(doc_type, 0) + 1

        return {
            "total": total,
            "completed": completed,
            "processing": processing,
            "failed": failed,
            "ready_to_export": ready,
            "requires_attention": total - ready,
            "null_fields": sum(int(item["null_count"]) for item in documents),
            "review_fields": sum(int(item["review_count"]) for item in documents),
            "invalid_fields": sum(int(item["invalid_count"]) for item in documents),
            "success_rate": round((completed / total * 100), 1) if total else 0,
            "by_type": by_type,
            "run_root": str(self.run_root),
        }

    def list_documents(
        self,
        *,
        status: str | None = None,
        doc_type: str | None = None,
        limit: int = 250,
    ) -> list[dict[str, object]]:
        summary_by_stem = self._summary_by_stem()
        documents = [self._document_card(path, summary_by_stem.get(path.name)) for path in self._document_dirs()]
        if status:
            documents = [item for item in documents if item["status"] == status]
        if doc_type:
            documents = [item for item in documents if item["document_type"] == doc_type]
        documents.sort(key=lambda item: str(item["updated_at"]), reverse=True)
        return documents[:limit]

    def get_document(self, document_id: str) -> dict[str, object] | None:
        base = self._document_path(document_id)
        if base is None:
            return None
        summary = self._summary_by_stem().get(base.name)
        card = self._document_card(base, summary)
        raw_final = self._read_final_json(base)
        payload, wrapper_type = self._extract_document_payload(raw_final)
        review_draft = self._read_review_draft(base)
        draft_fields = self._draft_fields(review_draft)
        fields = self._flatten_fields(payload, draft_fields=draft_fields)
        return {
            **card,
            "fields": fields,
            "final_json": self._display_value(payload),
            "raw_final_json": raw_final,
            "wrapper_document_type": wrapper_type,
            "review_draft": review_draft,
        }

    def artifacts(self, document_id: str) -> dict[str, object] | None:
        base = self._document_path(document_id)
        if base is None:
            return None
        files: list[dict[str, object]] = []
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            try:
                relative_path = path.relative_to(base)
            except ValueError:
                continue
            stat = path.stat()
            files.append(
                {
                    "name": path.name,
                    "relative_path": str(relative_path).replace("\\", "/"),
                    "stage": relative_path.parts[0] if relative_path.parts else "",
                    "size_bytes": stat.st_size,
                    "modified_at": self._iso_from_timestamp(stat.st_mtime),
                    "preview_type": self._preview_type(path),
                }
            )
            if len(files) >= 800:
                break
        return {"document_id": document_id, "base_path": str(base), "files": files}

    def resolve_artifact_path(self, document_id: str, relative_path: str) -> Path | None:
        base = self._document_path(document_id)
        if base is None:
            return None
        candidate = (base / relative_path).resolve()
        try:
            candidate.relative_to(base.resolve())
        except ValueError:
            return None
        return candidate

    def artifact_text(self, document_id: str, relative_path: str) -> dict[str, object] | None:
        path = self.resolve_artifact_path(document_id, relative_path)
        if path is None or not path.exists() or not path.is_file():
            return None
        if path.stat().st_size > 2_000_000:
            return {"path": relative_path, "text": "", "truncated": True, "error": "File is too large"}
        suffix = path.suffix.lower()
        if suffix not in {".json", ".txt", ".log", ".html", ".csv", ".md"}:
            return None
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            if suffix == ".json":
                text = json.dumps(self._display_value(json.loads(text)), ensure_ascii=False, indent=2)
            else:
                text = self._fix_text(text)
            return {"path": relative_path, "text": text[:100_000], "truncated": len(text) > 100_000}
        except Exception as exc:
            return {"path": relative_path, "text": "", "truncated": False, "error": str(exc)}

    def save_review_draft(self, document_id: str, fields: dict[str, Any]) -> dict[str, object] | None:
        base = self._document_path(document_id)
        if base is None:
            return None
        draft_dir = base / "data" / "review_overrides"
        draft_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "document_id": document_id,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "fields": fields,
        }
        draft_path = draft_dir / "ui_review.json"
        draft_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"saved": True, "path": str(draft_path), "field_count": len(fields)}

    def export_queue(self) -> dict[str, object]:
        documents = self.list_documents(limit=1000)
        attention = [item for item in documents if not item["ready_to_export"]]
        ready = [item for item in documents if item["ready_to_export"]]
        return {
            "requires_attention": attention,
            "ready": ready,
            "summary": {
                "attention_count": len(attention),
                "ready_count": len(ready),
                "null_fields": sum(int(item["null_count"]) for item in attention),
                "invalid_fields": sum(int(item["invalid_count"]) for item in attention),
            },
        }

    def events(self, *, limit: int = 50) -> list[dict[str, object]]:
        redis_events = self._redis_events(limit)
        if redis_events:
            return redis_events
        docs = self.list_documents(limit=limit)
        events: list[dict[str, object]] = []
        for item in docs:
            level = "ERROR" if item["status"] == "failed" else "OK"
            message = "Final JSON ready" if item["status"] == "completed" else "Document updated"
            events.append(
                {
                    "level": level,
                    "message": message,
                    "document": item["filename"],
                    "timestamp": item["updated_at"],
                    "type": "artifact_snapshot",
                }
            )
        return events

    @classmethod
    def _detect_run_root(cls, shared_files: Path) -> Path:
        base = shared_files.resolve()
        candidates: list[RunRootCandidate] = []
        if base.exists():
            direct_count = cls._count_document_dirs(base)
            if direct_count:
                candidates.append(RunRootCandidate(base, direct_count, base.stat().st_mtime))
            for child in base.iterdir():
                if not child.is_dir():
                    continue
                count = cls._count_document_dirs(child)
                if count:
                    candidates.append(RunRootCandidate(child, count, child.stat().st_mtime))
        if not candidates:
            return base
        candidates.sort(key=lambda item: (item.document_count, item.modified_at), reverse=True)
        return candidates[0].path

    @staticmethod
    def _count_document_dirs(root: Path) -> int:
        try:
            return sum(1 for child in root.iterdir() if child.is_dir() and ArtifactService._looks_like_doc_dir(child))
        except OSError:
            return 0

    @staticmethod
    def _looks_like_doc_dir(path: Path) -> bool:
        return any(
            [
                (path / "data" / "final_json").exists(),
                (path / "data" / "pred_reconciled").exists(),
                (path / "final_rebuilt_auto").exists(),
                (path / "_pipeline_v2_debug").exists(),
                (path / "original").exists(),
            ]
        )

    def _document_dirs(self) -> list[Path]:
        if not self.run_root.exists():
            return []
        return [child for child in self.run_root.iterdir() if child.is_dir() and self._looks_like_doc_dir(child)]

    def _document_path(self, document_id: str) -> Path | None:
        candidate = (self.run_root / document_id).resolve()
        try:
            candidate.relative_to(self.run_root)
        except ValueError:
            return None
        if candidate.exists() and candidate.is_dir():
            return candidate
        for child in self._document_dirs():
            if child.name == document_id:
                return child
        return None

    def _summary_by_stem(self) -> dict[str, dict[str, Any]]:
        summary_path = self.run_root / "summary.json"
        if not summary_path.exists():
            return {}
        try:
            summary = self._read_json(summary_path)
        except Exception:
            return {}
        results = summary.get("results", []) if isinstance(summary, dict) else []
        by_stem: dict[str, dict[str, Any]] = {}
        for item in results:
            if isinstance(item, dict) and item.get("doc_stem"):
                by_stem[str(item["doc_stem"])] = item
        return by_stem

    def _document_card(self, base: Path, summary: dict[str, Any] | None) -> dict[str, object]:
        final_path = self._find_final_json(base)
        raw_final = self._read_final_json(base)
        payload, wrapper_type = self._extract_document_payload(raw_final)
        draft_fields = self._draft_fields(self._read_review_draft(base))
        fields = self._flatten_fields(payload, draft_fields=draft_fields)
        null_count = sum(1 for field in fields if field["effective_state"] == "null")
        review_count = sum(1 for field in fields if field["effective_state"] == "review")
        invalid_count = sum(1 for field in fields if field["effective_state"] == "invalid")
        status = self._status_for(base, summary, bool(final_path))
        updated_at = self._iso_from_timestamp(final_path.stat().st_mtime if final_path else base.stat().st_mtime)
        ready = status == "completed" and null_count == 0 and review_count == 0 and invalid_count == 0
        return {
            "id": base.name,
            "storage_dir": base.name,
            "filename": self._filename_for(base, summary),
            "document_type": self._infer_doc_type(raw_final, payload, summary, wrapper_type),
            "status": status,
            "progress": 100 if status in {"completed", "failed"} else self._progress_for(base),
            "updated_at": updated_at,
            "pages": self._pages_for(summary),
            "field_count": len(fields),
            "null_count": null_count,
            "review_count": review_count,
            "invalid_count": invalid_count,
            "ready_to_export": ready,
            "draft_field_count": len(draft_fields),
            "final_json_path": str(final_path) if final_path else None,
            "base_path": str(base),
        }

    def _find_final_json(self, base: Path) -> Path | None:
        final_dir = base / "data" / "final_json"
        if not final_dir.exists():
            return None
        files = sorted(final_dir.glob("*.json"))
        if not files:
            return None
        preferred = final_dir / f"{base.name}.json"
        return preferred if preferred.exists() else files[0]

    def _read_final_json(self, base: Path) -> Any:
        path = self._find_final_json(base)
        if path is None:
            return {}
        try:
            return self._read_json(path)
        except Exception:
            return {}

    @staticmethod
    def _read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))

    def _extract_document_payload(self, value: Any) -> tuple[Any, str | None]:
        if not isinstance(value, dict) or len(value) != 1:
            return value, None
        wrapper_type, wrapper_value = next(iter(value.items()))
        if not isinstance(wrapper_value, dict) or not wrapper_value:
            return value, str(wrapper_type)
        first_value = next(iter(wrapper_value.values()))
        if isinstance(first_value, dict):
            return first_value, str(wrapper_type)
        return value, str(wrapper_type)

    def _flatten_fields(
        self,
        value: Any,
        prefix: str = "",
        *,
        draft_fields: dict[str, Any] | None = None,
    ) -> list[dict[str, object]]:
        fields: list[dict[str, object]] = []
        if isinstance(value, dict):
            for key, item in value.items():
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                fields.extend(self._flatten_fields(item, child_prefix, draft_fields=draft_fields))
            return fields
        if isinstance(value, list):
            for index, item in enumerate(value):
                fields.extend(self._flatten_fields(item, f"{prefix}[{index}]", draft_fields=draft_fields))
            if not value and prefix:
                fields.append(self._field(prefix, value, draft_fields=draft_fields))
            return fields
        if prefix:
            fields.append(self._field(prefix, value, draft_fields=draft_fields))
        return fields

    def _field(
        self,
        path: str,
        value: Any,
        *,
        draft_fields: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        display = self._display_value(value)
        has_draft = draft_fields is not None and path in draft_fields
        draft_value = self._display_value(draft_fields[path]) if has_draft and draft_fields is not None else None
        effective_value = draft_value if has_draft else display
        return {
            "path": path,
            "label": path.replace("_", " ").replace(".", " / "),
            "value": display,
            "raw_value": value,
            "draft_value": draft_value,
            "has_draft": has_draft,
            "effective_value": effective_value,
            "state": self._field_state(display),
            "effective_state": self._field_state(effective_value),
            "catalog": self._catalog_for_path(path),
        }

    def _field_state(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, str):
            lowered = value.lower()
            if REVIEW_MARKER in lowered:
                return "review"
            if any(marker in lowered for marker in INVALID_MARKERS):
                return "invalid"
            if not value.strip():
                return "empty"
        if isinstance(value, list) and not value:
            return "empty"
        return "ok"

    @staticmethod
    def _catalog_for_path(path: str) -> str | None:
        lowered = path.lower()
        if "unit" in lowered:
            return "units"
        if any(token in lowered for token in ("supplier", "sender", "receiver", "customer", "payer")):
            return "counterparties"
        return None

    def _display_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._fix_text(value)
        if isinstance(value, dict):
            return {self._fix_text(str(key)): self._display_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._display_value(item) for item in value]
        return value

    @staticmethod
    def _fix_text(value: str) -> str:
        if not value:
            return value
        markers = ("Р", "С", "вЂ", "в„", "Ð", "Ñ")
        if not any(marker in value for marker in markers):
            return value
        candidates = [value]
        for _ in range(2):
            source = candidates[-1]
            try:
                candidates.append(source.encode("cp1251").decode("utf-8"))
            except UnicodeError:
                break
        return min(candidates, key=ArtifactService._mojibake_score)

    @staticmethod
    def _mojibake_score(value: str) -> int:
        score = value.count("\ufffd") * 5
        for marker in ("Р", "С", "вЂ", "в„", "Ð", "Ñ"):
            score += value.count(marker)
        return score

    def _read_review_draft(self, base: Path) -> dict[str, Any] | None:
        path = base / "data" / "review_overrides" / "ui_review.json"
        if not path.exists():
            return None
        try:
            return self._read_json(path)
        except Exception:
            return None

    @staticmethod
    def _draft_fields(review_draft: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(review_draft, dict):
            return {}
        fields = review_draft.get("fields")
        return fields if isinstance(fields, dict) else {}

    def _infer_doc_type(
        self,
        raw_final: Any,
        payload: Any,
        summary: dict[str, Any] | None,
        wrapper_type: str | None,
    ) -> str:
        summary_type = self._summary_doc_type(summary)
        if summary_type:
            return summary_type
        if wrapper_type:
            return self._normalize_doc_type(wrapper_type)
        if isinstance(payload, dict):
            doc_type = payload.get("document_type")
            if isinstance(doc_type, str):
                fixed = self._fix_text(doc_type).lower()
                if "наклад" in fixed:
                    return "waybill"
                if "счет" in fixed:
                    return "invoice"
            keys = {str(key).lower() for key in payload.keys()}
            if {"sender", "receiver", "items", "totals"} <= keys:
                return "waybill"
            if {"supplier", "customer", "items"} <= keys:
                return "invoice"
            if "payer" in keys and "recipient" in keys:
                return "payment_order"
        if isinstance(raw_final, dict) and raw_final:
            return self._normalize_doc_type(next(iter(raw_final.keys())))
        return "unknown"

    @staticmethod
    def _normalize_doc_type(value: str) -> str:
        lowered = value.lower()
        if "waybill" in lowered:
            return "waybill"
        if "invoice" in lowered:
            return "invoice"
        if "payment" in lowered:
            return "payment_order"
        if "account" in lowered:
            return "account_prot"
        return lowered

    @staticmethod
    def _summary_doc_type(summary: dict[str, Any] | None) -> str | None:
        if not summary:
            return None
        outputs = summary.get("summary", {}).get("final_outputs", [])
        if isinstance(outputs, list) and outputs:
            doc_type = outputs[0].get("doc_type") if isinstance(outputs[0], dict) else None
            if doc_type:
                return str(doc_type)
        return None

    @staticmethod
    def _status_for(base: Path, summary: dict[str, Any] | None, has_final: bool) -> str:
        if summary and summary.get("status") not in {None, "ok"}:
            return "failed"
        if has_final:
            return "completed"
        if (base / "_pipeline_v2_debug").exists() or (base / "final_rebuilt_auto").exists():
            return "processing"
        return "uploaded"

    @staticmethod
    def _progress_for(base: Path) -> int:
        stages = [
            (base / "original").exists(),
            (base / "cleaner").exists(),
            (base / "final_rebuilt_auto").exists(),
            (base / "data" / "pred_reconciled").exists(),
            (base / "data" / "final_json").exists(),
        ]
        return int(sum(1 for item in stages if item) / len(stages) * 100)

    def _filename_for(self, base: Path, summary: dict[str, Any] | None) -> str:
        if summary and summary.get("input_path"):
            return self._fix_text(Path(str(summary["input_path"])).name)
        original_dir = base / "original"
        if original_dir.exists():
            files = sorted(path.name for path in original_dir.iterdir() if path.is_file())
            if files:
                return self._fix_text(files[0])
        return self._fix_text(f"{base.name}.pdf")

    @staticmethod
    def _pages_for(summary: dict[str, Any] | None) -> int | None:
        if not summary:
            return None
        pages = summary.get("pages")
        if isinstance(pages, int):
            return pages
        nested = summary.get("summary", {})
        if isinstance(nested, dict) and isinstance(nested.get("page_count"), int):
            return nested["page_count"]
        return None

    @staticmethod
    def _preview_type(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            return "image"
        if suffix == ".pdf":
            return "pdf"
        if suffix in {".json", ".txt", ".log", ".html", ".csv", ".md"}:
            return "text"
        return "download"

    @staticmethod
    def _iso_from_timestamp(value: float) -> str:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()

    def _redis_events(self, limit: int) -> list[dict[str, object]]:
        try:
            import redis
        except Exception:
            return []
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        try:
            client = redis.Redis(
                host=host,
                port=port,
                db=0,
                decode_responses=True,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
            )
            raw_items = client.lrange("files:events:recent", 0, max(0, limit - 1))
        except Exception:
            return []
        events: list[dict[str, object]] = []
        for item in reversed(raw_items):
            try:
                event = json.loads(item)
            except Exception:
                continue
            events.append(self._display_value(event))
        return events
