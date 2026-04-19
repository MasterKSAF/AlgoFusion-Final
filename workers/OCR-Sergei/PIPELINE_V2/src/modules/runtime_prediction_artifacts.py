from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.modules.runtime_services import PipelineRuntimeServices


@dataclass(frozen=True)
class PredictionArtifacts:
    outer_type: str
    pred_norm: dict[str, Any]
    pred_recon: dict[str, Any]
    final_json: dict[str, Any]


def build_prediction_artifacts(
    services: PipelineRuntimeServices,
    prediction: dict[str, Any],
    *,
    file_key: str,
    outer_type: str,
    sanitize_final_json_payload,
) -> PredictionArtifacts:
    pred_norm = services.prediction_normalizer.normalize(prediction)
    pred_recon = services.prediction_reconciler.reconcile(pred_norm)
    final_json = services.final_json_builder.build(pred_recon, file_key=file_key)
    final_json = sanitize_final_json_payload(outer_type, final_json)

    return PredictionArtifacts(
        outer_type=outer_type,
        pred_norm=pred_norm,
        pred_recon=pred_recon,
        final_json=final_json,
    )
