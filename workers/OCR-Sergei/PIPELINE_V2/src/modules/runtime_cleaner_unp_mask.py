from __future__ import annotations

import cv2
import numpy as np

from src.modules.runtime_cleaner_unp_segments import (
    _build_mask_from_segments,
    _cm_to_px,
    _extract_axis_segments_for_unp,
    _extend_segments_stepwise,
    _segments_to_component_candidates,
    _analyze_unp_component,
)


def _detect_unp_cells_from_mask(mask: np.ndarray, table_top_y: int, dpi: int = 200):
    H, W = mask.shape[:2]

    # зона поиска: только над основной таблицей
    y0 = max(0, table_top_y - int(H * 0.26))
    y1 = max(y0 + 20, table_top_y - 20)

    roi = (mask[y0:y1] > 0).astype(np.uint8) * 255

    # ищем только центрально-правую часть шапки
    x0 = int(W * 0.18)
    x1 = int(W * 0.92)
    roi = roi[:, x0:x1]

    if roi.size == 0 or np.count_nonzero(roi) == 0:
        return []

    roi_h, roi_w = roi.shape[:2]

    # параметры вытягивания
    step_px = _cm_to_px(0.5, dpi)   # 0.5 см
    max_px = _cm_to_px(4.0, dpi)    # 4 см

    # 1) извлекаем осевые сегменты
    h_segments, v_segments = _extract_axis_segments_for_unp(roi)

    if not h_segments and not v_segments:
        return []

    # 2) сначала пробуем найти идеальный блок без вытягивания,
    #    потом с вытягиванием 0.5см, 1см, ... до 4см
    best_result = []
    best_score = -1

    for hs, vs, ext_px in _extend_segments_stepwise(
        h_segments=h_segments,
        v_segments=v_segments,
        step_px=step_px,
        max_px=max_px,
        w=roi_w,
        h=roi_h,
    ):
        grid = _build_mask_from_segments((roi_h, roi_w), hs, vs, thickness=1)

        # небольшой close, чтобы соединить почти касающиеся линии
        grid = cv2.morphologyEx(
            grid,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        )

        candidates = _segments_to_component_candidates(grid)

        for cand in candidates:
            x, y, w_box, h_box = cand["bbox"]
            area = cand["area"]
            comp = cand["mask"]

            # мягкие фильтры размера
            if area < 200:
                continue
            if not (20 <= h_box <= max(25, int(0.50 * roi_h))):
                continue
            if not (30 <= w_box <= int(0.80 * roi_w)):
                continue

            info = _analyze_unp_component(comp)
            if info is None:
                continue

            rows_n = info["rows_n"]
            cols_n = info["cols_n"]
            ys = info["ys"]
            xs = info["xs"]

            # собираем ячейки
            cells = []
            for r in range(rows_n):
                for c in range(cols_n):
                    cx1 = x0 + x + xs[c]
                    cx2 = x0 + x + xs[c + 1]
                    cy1 = y0 + y + ys[r]
                    cy2 = y0 + y + ys[r + 1]
                    cells.append((int(cx1), int(cy1), int(cx2), int(cy2)))

            # score:
            # - меньше вытягивание лучше
            # - 2x2 / 2x3 подходит
            # - чуть выше на странице лучше
            score = (
                area
                + cols_n * 500
                - y * 2
                - ext_px * 3
            )

            # как только нашли валидный 2x2/2x3 на текущем шаге —
            # можно сразу выбрать лучший среди найденных на этом шаге
            if score > best_score:
                best_score = score
                best_result = cells

        if best_result:
            return best_result

    return []
