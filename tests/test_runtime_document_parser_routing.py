from __future__ import annotations

from pathlib import Path

from src.modules.runtime_document_parser_routing import parse_roi_by_doc_type


class FakeDocumentParser:
    def __init__(self, fallback_type: str = "unknown") -> None:
        self.fallback_type = fallback_type
        self.calls: list[str] = []

    def detect_doc_type(self, roi_path: Path) -> str:
        self.calls.append("detect_doc_type")
        return self.fallback_type

    def parse_payment_order(self, roi_path: Path) -> dict[str, str]:
        self.calls.append("parse_payment_order")
        return {"parsed": "payment_order"}

    def parse_invoice(self, roi_path: Path) -> dict[str, str]:
        self.calls.append("parse_invoice")
        return {"parsed": "invoice"}

    def parse_waybill(self, roi_path: Path) -> dict[str, str]:
        self.calls.append("parse_waybill")
        return {"parsed": "waybill"}

    def parse_account_protocol(self, roi_path: Path) -> dict[str, str]:
        self.calls.append("parse_account_protocol")
        return {"parsed": "account_prot"}


def test_parse_roi_by_doc_type_uses_declared_parser_without_detection() -> None:
    parser = FakeDocumentParser()

    assert parse_roi_by_doc_type(parser, Path("roi.json"), "invoice", page_id="p1") == {"parsed": "invoice"}
    assert parser.calls == ["parse_invoice"]


def test_parse_roi_by_doc_type_detects_fallback_for_unknown_type() -> None:
    parser = FakeDocumentParser(fallback_type="waybill")

    assert parse_roi_by_doc_type(parser, Path("roi.json"), "unknown", page_id="p1") == {"parsed": "waybill"}
    assert parser.calls == ["detect_doc_type", "parse_waybill"]


def test_parse_roi_by_doc_type_reports_unsupported_type_with_page_id() -> None:
    parser = FakeDocumentParser(fallback_type="unknown")

    try:
        parse_roi_by_doc_type(parser, Path("roi.json"), "unknown", page_id="page-42")
    except ValueError as exc:
        assert "page-42" in str(exc)
    else:
        raise AssertionError("Expected unsupported document type to fail")
