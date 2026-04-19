from __future__ import annotations

from typing import Any


def probe_surya_dependency() -> str | None:
    try:
        from surya.detection import DetectionPredictor  # noqa: F401
        from surya.foundation import FoundationPredictor  # noqa: F401
        from surya.recognition import RecognitionPredictor  # noqa: F401
    except ModuleNotFoundError as exc:
        return str(exc)
    return None


class SuryaEngine:
    def __init__(self) -> None:
        self.foundation: Any | None = None
        self.det: Any | None = None
        self.rec: Any | None = None

    def load(self) -> None:
        from surya.detection import DetectionPredictor
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor

        self.foundation = FoundationPredictor()
        self.det = DetectionPredictor()
        self.rec = RecognitionPredictor(self.foundation)

    def run(self, image: Any) -> list[dict[str, Any]]:
        if self.rec is None or self.det is None:
            self.load()

        predictions = self.rec([image], det_predictor=self.det)
        items: list[dict[str, Any]] = []
        for page in predictions:
            for line in page.text_lines:
                x1, y1, x2, y2 = line.bbox
                items.append(
                    {
                        "text": line.text,
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    }
                )
        return items
