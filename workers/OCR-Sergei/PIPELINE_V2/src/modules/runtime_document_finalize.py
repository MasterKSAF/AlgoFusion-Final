from __future__ import annotations

import copy
from typing import Any

from src.modules.runtime_document_type_resolution import infer_doc_type_from_name
from src.modules.runtime_io import write_json
from src.modules.runtime_postprocess import unwrap_page_prediction
from src.modules.runtime_prediction_artifacts import build_prediction_artifacts
from src.modules.runtime_services import PipelineRuntimeServices
from src.modules.runtime_waybill_text import finalize_waybill_payload_text
from src.modules.runtime_invoice_postprocess import finalize_invoice_payload_text


def sanitize_final_json_payload(outer_type: str, final_json: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(final_json)
    if outer_type == "waybill":
        if not isinstance(out, dict):
            return out
        if len(out) == 1:
            file_key, payload = next(iter(out.items()))
            if isinstance(payload, dict):
                out[file_key] = finalize_waybill_payload_text(payload, "single")
                return out
        if isinstance(out, dict):
            return finalize_waybill_payload_text(out, "single")
        return out
    if not isinstance(out, dict):
        return out
    docs = out.get(outer_type)
    if not isinstance(docs, dict):
        return out
    for file_key, payload in list(docs.items()):
        if not isinstance(payload, dict):
            continue
        if outer_type == "invoice":
            docs[file_key] = finalize_invoice_payload_text(payload)
    return out


def finalize_document(
    services: PipelineRuntimeServices,
    pred: dict[str, Any],
    docs_dir,
    file_name: str,
) -> dict[str, Any]:
    outer_type, _old_key, _payload = unwrap_page_prediction(pred, infer_doc_type_from_name(file_name))

    artifacts = build_prediction_artifacts(
        services,
        pred,
        file_key=file_name,
        outer_type=outer_type,
        sanitize_final_json_payload=sanitize_final_json_payload,
    )

    write_json(docs_dir / "pred.json", pred)
    write_json(docs_dir / "pred_norm.json", artifacts.pred_norm)
    write_json(docs_dir / "pred_recon.json", artifacts.pred_recon)
    write_json(docs_dir / "final.json", artifacts.final_json)
    return artifacts.final_json
