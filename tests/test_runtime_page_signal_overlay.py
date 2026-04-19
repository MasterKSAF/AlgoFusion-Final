from __future__ import annotations

import numpy as np

from src.modules.runtime_page_signal_overlay import draw_page_signal_zones


def test_draw_page_signal_zones_preserves_input_image() -> None:
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    original = image.copy()

    overlay = draw_page_signal_zones(image)

    assert overlay.shape == image.shape
    assert np.array_equal(image, original)
    assert not np.array_equal(overlay, original)
