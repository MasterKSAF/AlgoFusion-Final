from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping

from src.modules.runtime_document_parser_service import (
    detect_doc_type as detect_runtime_doc_type,
    parse_account_protocol as parse_runtime_account_protocol,
    parse_invoice as parse_runtime_invoice,
    parse_payment_order as parse_runtime_payment_order,
    parse_waybill as parse_runtime_waybill,
)
from src.modules import runtime_cleaner_extract
from src.modules.runtime_final_json_builder import build_final_json
from src.modules.runtime_prediction_normalizer import normalize_pred as normalize_runtime_pred
from src.modules.runtime_prediction_reconciler import build_pred_reconciled as build_runtime_pred_reconciled
from src.modules.runtime_raw_ocr_engine import SuryaEngine, probe_surya_dependency
from src.modules.runtime_roi_assignment import run_roi_assignment_pipeline
from src.modules.runtime_roi_render import draw_rois_on_clean, remove_lines


@dataclass(frozen=True)
class CleanerLayoutService:
    namespace: dict[str, Any]

    @property
    def default_dpi(self) -> int:
        cleaner_cfg = self.namespace.get("NB_CLEANER")
        value = getattr(cleaner_cfg, "default_dpi", None)
        if value is None:
            value = getattr(cleaner_cfg, "output_dpi", 200)
        return int(value or 200)

    @property
    def output_dpi(self) -> int:
        cleaner_cfg = self.namespace.get("NB_CLEANER")
        return int(getattr(cleaner_cfg, "output_dpi", 200) or 200)

    @property
    def rotate_min_abs_angle(self) -> float:
        cleaner_cfg = self.namespace.get("NB_CLEANER")
        return float(getattr(cleaner_cfg, "rotate_min_abs_angle", 0.0) or 0.0)

    @property
    def rotate_max_abs_angle(self) -> float:
        cleaner_cfg = self.namespace.get("NB_CLEANER")
        return float(getattr(cleaner_cfg, "rotate_max_abs_angle", 0.0) or 0.0)

    @property
    def a4_canvas_enabled(self) -> bool:
        cleaner_cfg = self.namespace.get("NB_CLEANER")
        return bool(getattr(cleaner_cfg, "a4_canvas_enabled", False))

    def normalize_to_working_dpi(self, image: Any, *, input_dpi: int, working_dpi: int | None = None) -> Any:
        target_dpi = int(working_dpi or self.default_dpi)
        return self.namespace["nb_normalize_to_working_dpi"](image, input_dpi=input_dpi, working_dpi=target_dpi)

    def preprocess_stage_4_1(self, image: Any) -> Any:
        return self.namespace["nb_preprocessing_stage_4_1"](image)

    def preprocess_stage_4_2(self, image: Any) -> Any:
        return self.namespace["nb_preprocessing_stage_4_2"](image)

    def preprocess_stage_4_3(self, image: Any) -> Any:
        return self.namespace["nb_preprocessing_stage_4_3"](image)

    def build_background(self, image: Any) -> Any:
        return self.namespace["nb_preprocessing_stage_5_2_background"](image)

    def build_binary(self, image: Any) -> Any:
        return self.namespace["nb_preprocessing_stage_5_2_binary_and_denoise"](image)

    def detect_rotation_angle(self, image: Any) -> tuple[float, bool]:
        return self.namespace["nb_detect_rotation_angle"](image)

    def rotate_image_by_angle(self, image: Any, angle: float) -> Any:
        return self.namespace["nb_rotate_image_by_angle"](image, angle)

    def fit_to_a4_canvas(self, image: Any, *, target_dpi: int | None = None) -> Any:
        return self.namespace["nb_fit_to_a4_canvas"](image, target_dpi=int(target_dpi or self.output_dpi))

    def detect_table_lines_mask(self, clean_bgr: Any) -> Any:
        return self.namespace["detect_table_lines_mask"](clean_bgr)

    def thin_lines_ximgproc(self, lines: Any) -> Any:
        return self.namespace["thin_lines_ximgproc"](lines)

    def draw_overlay_stage1(self, clean_bgr: Any, line_mask: Any, output_path: Any) -> None:
        self.namespace["draw_overlay_stage1"](clean_bgr, line_mask, output_path)

    def save_mask_json(self, line_mask: Any, mask_json_path: Any, page_id: str, *, source: dict[str, Any]) -> None:
        self.namespace["save_mask_json"](line_mask, mask_json_path, page_id, source=source)

    def detect_layout_type(self, mask: Any) -> tuple[str, dict[str, Any]]:
        return self.namespace["detect_layout_type"](mask)

    def find_main_table_block(self, mask: Any) -> dict[str, Any] | None:
        return self.namespace["find_main_table_block"](mask)

    def process_form_page(self, page_id: str, mask: Any, clean_bgr: Any, temp_out: Any, stats: dict[str, Any]) -> bool:
        return bool(self.namespace["process_form_page"](page_id, mask, clean_bgr, temp_out, stats))

    def process_table_page(
        self,
        page_id: str,
        mask: Any,
        clean_bgr: Any,
        temp_out: Any,
        layout_hint: str,
        stats: dict[str, Any],
    ) -> bool:
        return bool(self.namespace["process_table_page"](page_id, mask, clean_bgr, temp_out, layout_hint, stats))

    def has_form_structure(self, mask: Any) -> bool:
        return bool(self.namespace["has_form_structure"](mask))


@dataclass(frozen=True)
class RoiRenderService:
    namespace: dict[str, Any]

    def remove_lines(self, clean_bgr: Any, mask: Any) -> Any:
        return self.namespace["remove_lines"](clean_bgr, mask)

    def draw_rois_on_clean(self, no_lines_bgr: Any, rois: list[dict[str, Any]]) -> Any:
        return self.namespace["draw_rois_on_clean"](no_lines_bgr, rois)


@dataclass(frozen=True)
class RawOcrService:
    namespace: dict[str, Any]

    @property
    def load_error(self) -> Exception | None:
        err = self.namespace.get("__load_error__")
        return err if isinstance(err, Exception) else None

    def ensure_available(self) -> None:
        if self.load_error is not None:
            raise ModuleNotFoundError(
                "Raw OCR engine is unavailable. Install the missing dependency first: " + str(self.load_error)
            )

    def create_engine(self) -> Any:
        self.ensure_available()
        engine = self.namespace["SuryaEngine"]()
        engine.load()
        return engine

    def run_image(self, image: Any) -> list[dict[str, Any]]:
        return self.create_engine().run(image)


@dataclass(frozen=True)
class RoiAssignmentService:
    namespace: dict[str, Any]

    def run(self, clean_png: str, roi_coords_path: str, raw_ocr_json_path: str) -> tuple[Any, str | None]:
        return self.namespace["run_roi_assignment_pipeline"](clean_png, roi_coords_path, raw_ocr_json_path)


@dataclass(frozen=True)
class DocumentParserService:
    namespace: dict[str, Any]

    def detect_doc_type(self, roi_path: Any) -> str | None:
        detected = self.namespace["detect_doc_type"](roi_path)
        return str(detected) if detected else None

    def parse_payment_order(self, roi_path: Any) -> dict[str, Any]:
        return self.namespace["parse_payment_order"](roi_path)

    def parse_invoice(self, roi_path: Any) -> dict[str, Any]:
        return self.namespace["parse_invoice"](roi_path)

    def parse_waybill(self, roi_path: Any) -> dict[str, Any]:
        return self.namespace["parse_waybill"](roi_path)

    def parse_account_protocol(self, roi_path: Any) -> dict[str, Any]:
        return self.namespace["parse_account_protocol"](roi_path)


@dataclass(frozen=True)
class PredictionNormalizerService:
    namespace: dict[str, Any]

    def normalize(self, prediction: dict[str, Any]) -> dict[str, Any]:
        return self.namespace["normalize_pred"](prediction)


@dataclass(frozen=True)
class PredictionReconcilerService:
    namespace: dict[str, Any]

    def reconcile(self, prediction: dict[str, Any]) -> dict[str, Any]:
        return self.namespace["build_pred_reconciled"](prediction)


@dataclass(frozen=True)
class FinalJsonBuilderService:
    namespace: dict[str, Any]

    def build(self, prediction: dict[str, Any], *, file_key: str) -> dict[str, Any]:
        return self.namespace["build_final_json"](prediction, file_key=file_key)


@dataclass(frozen=True)
class PipelineRuntimeServices:
    cleaner_layout: CleanerLayoutService
    roi_render: RoiRenderService
    raw_ocr: RawOcrService
    roi_assignment: RoiAssignmentService
    document_parser: DocumentParserService
    prediction_normalizer: PredictionNormalizerService
    prediction_reconciler: PredictionReconcilerService
    final_json_builder: FinalJsonBuilderService

    @classmethod
    def from_namespaces(cls, namespaces: Mapping[str, Mapping[str, Any]]) -> "PipelineRuntimeServices":
        return _build_runtime_services(namespaces)

    @classmethod
    def load(cls) -> "PipelineRuntimeServices":
        return _load_runtime_services()


def _build_runtime_services(namespaces: Mapping[str, Mapping[str, Any]]) -> PipelineRuntimeServices:
    return PipelineRuntimeServices(
        cleaner_layout=CleanerLayoutService(dict(namespaces["cleaner_layout"])),
        roi_render=RoiRenderService(dict(namespaces["roi_render"])),
        raw_ocr=RawOcrService(dict(namespaces["raw_ocr"])),
        roi_assignment=RoiAssignmentService(dict(namespaces["roi_assignment"])),
        document_parser=DocumentParserService(dict(namespaces["document_parser"])),
        prediction_normalizer=PredictionNormalizerService(dict(namespaces["prediction_normalizer"])),
        prediction_reconciler=PredictionReconcilerService(dict(namespaces["prediction_reconciler"])),
        final_json_builder=FinalJsonBuilderService(dict(namespaces["final_json_builder"])),
    )


@lru_cache(maxsize=1)
def _cleaner_namespace() -> dict[str, Any]:
    namespace = dict(vars(runtime_cleaner_extract))
    nb_cleaner = namespace.get("NB_CLEANER")
    if nb_cleaner is None:
        nb_cleaner = runtime_cleaner_extract.NotebookCleanerConfig()
        namespace["NB_CLEANER"] = nb_cleaner
    namespace["DPI"] = int(getattr(nb_cleaner, "output_dpi", 200) or 200)
    return namespace


@lru_cache(maxsize=1)
def _document_parser_namespace() -> dict[str, Any]:
    return {
        "detect_doc_type": detect_runtime_doc_type,
        "parse_payment_order": parse_runtime_payment_order,
        "parse_invoice": parse_runtime_invoice,
        "parse_waybill": parse_runtime_waybill,
        "parse_account_protocol": parse_runtime_account_protocol,
    }


@lru_cache(maxsize=1)
def _prediction_normalizer_namespace() -> dict[str, Any]:
    return {"normalize_pred": normalize_runtime_pred}


@lru_cache(maxsize=1)
def _prediction_reconciler_namespace() -> dict[str, Any]:
    return {"build_pred_reconciled": build_runtime_pred_reconciled}


@lru_cache(maxsize=1)
def _final_json_builder_namespace() -> dict[str, Any]:
    return {"build_final_json": build_final_json}


@lru_cache(maxsize=1)
def _roi_render_namespace() -> dict[str, Any]:
    return {
        "remove_lines": remove_lines,
        "draw_rois_on_clean": draw_rois_on_clean,
    }


@lru_cache(maxsize=1)
def _raw_ocr_namespace() -> dict[str, Any]:
    load_error = probe_surya_dependency()
    namespace: dict[str, Any] = {"SuryaEngine": SuryaEngine}
    if load_error:
        namespace["__load_error__"] = load_error
    return namespace


@lru_cache(maxsize=1)
def _roi_assignment_namespace() -> dict[str, Any]:
    return {"run_roi_assignment_pipeline": run_roi_assignment_pipeline}


@lru_cache(maxsize=1)
def _load_runtime_services() -> PipelineRuntimeServices:
    return PipelineRuntimeServices(
        cleaner_layout=CleanerLayoutService(_cleaner_namespace()),
        roi_render=RoiRenderService(_roi_render_namespace()),
        raw_ocr=RawOcrService(_raw_ocr_namespace()),
        roi_assignment=RoiAssignmentService(_roi_assignment_namespace()),
        document_parser=DocumentParserService(_document_parser_namespace()),
        prediction_normalizer=PredictionNormalizerService(_prediction_normalizer_namespace()),
        prediction_reconciler=PredictionReconcilerService(_prediction_reconciler_namespace()),
        final_json_builder=FinalJsonBuilderService(_final_json_builder_namespace()),
    )
