from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None

# =========================================================
# WORKER-LIKE CLEANER FOR NOTEBOOK
# =========================================================



@dataclass
class NotebookCleanerConfig:
    default_dpi: int = 600
    assumed_input_dpi: int = 300
    output_dpi: int = 200
    a4_canvas_enabled: bool = True
    rotate_min_abs_angle: float = 0.3
    rotate_max_abs_angle: float = 15.0
    stage41_diff_min: int = 1
    stage41_diff_max: int = 11
    stage42_diff_min: int = 12
    stage42_diff_max: int = 32
    stage43_diff_min: int = 33
    stage43_diff_max: int = 255
    background_threshold: int = 128
    background_fill_value: int = 255
    binary_threshold: int = 128
    binary_foreground_value: int = 1
    binary_background_value: int = 255
    bin_median_kernel: int = 3
    bin_median_passes: int = 5


NB_CLEANER = NotebookCleanerConfig()


def nb_read_json_maybe_gz(path: Path):
    if path is None or not path.exists():
        return {}
    if str(path).endswith('.gz'):
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            return json.load(f)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def nb_find_mask_json_for_page(page_id: str, stage1_dir: Path):
    for suffix in ('__mask.json', '__mask.json.gz'):
        matches = sorted(stage1_dir.rglob(f'{page_id}{suffix}'))
        if matches:
            return matches[0]
    return None


def nb_extract_input_dpi(dpi_meta, fallback: int):
    if isinstance(dpi_meta, tuple) and dpi_meta:
        try:
            value = float(dpi_meta[0])
            return int(round(value)) if value > 0 else fallback
        except (TypeError, ValueError):
            return fallback
    if isinstance(dpi_meta, (int, float)):
        value = float(dpi_meta)
        return int(round(value)) if value > 0 else fallback
    return fallback


def nb_get_a4_size(target_dpi: int = 600, is_portrait: bool = True):
    portrait_size = (
        max(1, int(round(8.27 * target_dpi))),
        max(1, int(round(11.69 * target_dpi))),
    )
    return portrait_size if is_portrait else (portrait_size[1], portrait_size[0])


def nb_fit_to_a4_canvas(input_img: Image.Image, target_dpi: int = 600):
    if target_dpi <= 0:
        return input_img
    target_size = nb_get_a4_size(target_dpi=target_dpi, is_portrait=input_img.height >= input_img.width)
    scale = min(target_size[0] / input_img.width, target_size[1] / input_img.height)
    new_size = (
        max(1, int(round(input_img.width * scale))),
        max(1, int(round(input_img.height * scale))),
    )
    resized = input_img.resize(new_size, resample=Image.LANCZOS)
    fill = 255 if resized.mode == 'L' else (255, 255, 255)
    canvas = Image.new(resized.mode, target_size, color=fill)
    offset = ((target_size[0] - new_size[0]) // 2, (target_size[1] - new_size[1]) // 2)
    canvas.paste(resized, offset)
    return canvas


def nb_normalize_to_working_dpi(input_img: Image.Image, input_dpi: int, working_dpi: int):
    if working_dpi <= 0:
        return input_img
    safe_input_dpi = input_dpi if input_dpi > 0 else working_dpi
    if safe_input_dpi == working_dpi:
        return input_img
    scale = working_dpi / float(safe_input_dpi)
    new_size = (
        max(1, int(round(input_img.width * scale))),
        max(1, int(round(input_img.height * scale))),
    )
    if new_size == input_img.size:
        return input_img
    return input_img.resize(new_size, resample=Image.LANCZOS)


def nb_detect_rotation_angle(image_bgr: np.ndarray):
    gray = image_bgr if image_bgr.ndim == 2 else cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    x1 = int(round(w * 0.20))
    x2 = int(round(w * 0.80))
    y1 = int(round(h * 0.30))
    y2 = int(round(h * 0.70))
    if x2 - x1 < 50 or y2 - y1 < 50:
        return 0.0, False
    roi = gray[y1:y2, x1:x2]
    bw = cv2.adaptiveThreshold(
        roi,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        35,
        7,
    )
    bw_clean = cv2.medianBlur(bw, 3)
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (35, 1))
    bw_h = cv2.morphologyEx(bw_clean, cv2.MORPH_OPEN, kernel_h)
    lines = cv2.HoughLinesP(
        bw_h,
        rho=1,
        theta=np.pi / 1800,
        threshold=80,
        minLineLength=int(roi.shape[1] * 0.30),
        maxLineGap=60,
    )
    if lines is None:
        return 0.0, False
    angles = []
    for xA, yA, xB, yB in lines[:, 0]:
        dx = xB - xA
        dy = yB - yA
        if dx == 0:
            continue
        angle = np.degrees(np.arctan2(dy, dx))
        length = np.hypot(dx, dy)
        if abs(angle) > 5:
            continue
        if length < roi.shape[1] * 0.30:
            continue
        angles.append(angle)
    if not angles:
        return 0.0, False
    angle = float(np.median(angles))
    angle = float(np.clip(angle, -1.5, 1.5))
    return angle, True


def nb_rotate_image_by_angle(image: np.ndarray, angle: float):
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    border_value = 255 if image.ndim == 2 else (255, 255, 255)
    return cv2.warpAffine(
        image,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
        borderValue=border_value,
    )


def nb_rotate_image(image_bgr: np.ndarray):
    angle, found = nb_detect_rotation_angle(image_bgr)
    if not found:
        return image_bgr
    if abs(angle) < NB_CLEANER.rotate_min_abs_angle:
        return image_bgr
    if abs(angle) > NB_CLEANER.rotate_max_abs_angle:
        return image_bgr
    return nb_rotate_image_by_angle(image_bgr, angle)


def nb_preprocessing_stage_4_1(input_img: Image.Image):
    arr = np.array(input_img.convert('RGB')).copy()
    rgb = arr[..., :3]
    min_val = rgb.min(axis=2)
    max_val = rgb.max(axis=2)
    diff = max_val - min_val
    mask = (diff >= NB_CLEANER.stage41_diff_min) & (diff <= NB_CLEANER.stage41_diff_max)
    rgb[mask] = np.stack([min_val[mask], min_val[mask], min_val[mask]], axis=1)
    arr[..., :3] = rgb
    return Image.fromarray(arr)


def nb_preprocessing_stage_4_2(input_img: Image.Image):
    arr = np.array(input_img.convert('RGB')).copy()
    rgb = arr[..., :3]
    min_val = rgb.min(axis=2)
    max_val = rgb.max(axis=2)
    diff = max_val - min_val
    gray_value = ((min_val.astype(np.uint16) + max_val.astype(np.uint16)) // 2).astype(np.uint8)
    mask = (diff >= NB_CLEANER.stage42_diff_min) & (diff <= NB_CLEANER.stage42_diff_max)
    rgb[mask] = np.stack([gray_value[mask], gray_value[mask], gray_value[mask]], axis=1)
    arr[..., :3] = rgb
    return Image.fromarray(arr)


def nb_preprocessing_stage_4_3(input_img: Image.Image):
    arr = np.array(input_img.convert('RGB')).copy()
    rgb = arr[..., :3]
    min_val = rgb.min(axis=2)
    max_val = rgb.max(axis=2)
    diff = max_val - min_val
    mask = (diff >= NB_CLEANER.stage43_diff_min) & (diff <= NB_CLEANER.stage43_diff_max)
    rgb[mask] = np.stack([max_val[mask], max_val[mask], max_val[mask]], axis=1)
    arr[..., :3] = rgb
    return Image.fromarray(arr)


def nb_preprocessing_stage_5_2_background(input_img: Image.Image):
    arr = np.array(input_img).copy()
    arr[arr > NB_CLEANER.background_threshold] = NB_CLEANER.background_fill_value
    return Image.fromarray(arr.astype(np.uint8))


def nb_preprocessing_stage_5_2_binary_and_denoise(input_img: Image.Image):
    arr = np.array(input_img).copy()
    arr[arr <= NB_CLEANER.binary_threshold] = NB_CLEANER.binary_foreground_value
    arr[arr > NB_CLEANER.binary_threshold] = NB_CLEANER.binary_background_value
    result = Image.fromarray(arr.astype(np.uint8))
    kernel = NB_CLEANER.bin_median_kernel
    if kernel % 2 == 0:
        kernel += 1
    for _ in range(max(0, NB_CLEANER.bin_median_passes)):
        result = result.filter(ImageFilter.MedianFilter(size=kernel))
    return result


def nb_preprocess_page_bgr(image_bgr: np.ndarray, input_dpi: int = 600, working_dpi: int = 600, target_dpi: int = 200):
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    img = nb_normalize_to_working_dpi(img, input_dpi=input_dpi, working_dpi=working_dpi)
    img = nb_preprocessing_stage_4_1(img)
    img = nb_preprocessing_stage_4_2(img)
    img = nb_preprocessing_stage_4_3(img)
    img = nb_preprocessing_stage_5_2_background(img)
    img = nb_preprocessing_stage_5_2_binary_and_denoise(img)
    processed_bgr = cv2.cvtColor(np.array(img.convert('RGB')), cv2.COLOR_RGB2BGR)
    rotated = nb_rotate_image(processed_bgr)
    img = Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))
    if NB_CLEANER.a4_canvas_enabled:
        img = nb_fit_to_a4_canvas(img, target_dpi=target_dpi)
    return cv2.cvtColor(np.array(img.convert('RGB')), cv2.COLOR_RGB2BGR)


def nb_clean_page_bgr_exact(img_bgr: np.ndarray, input_dpi: int = 600, working_dpi: int = 600, target_dpi: int = 200):
    return nb_preprocess_page_bgr(
        img_bgr,
        input_dpi=input_dpi,
        working_dpi=working_dpi,
        target_dpi=target_dpi,
    )


def nb_load_input_image_with_dpi(path: Path):
    with Image.open(path) as source_img:
        source_rgb = source_img.convert('RGB')
        dpi_meta = source_img.info.get('dpi')
        input_dpi = nb_extract_input_dpi(dpi_meta, NB_CLEANER.assumed_input_dpi)
    img = cv2.cvtColor(np.array(source_rgb), cv2.COLOR_RGB2BGR)
    return img, input_dpi


__all__ = [
    "NB_CLEANER",
    "NotebookCleanerConfig",
    "convert_from_path",
    "nb_clean_page_bgr_exact",
    "nb_detect_rotation_angle",
    "nb_extract_input_dpi",
    "nb_find_mask_json_for_page",
    "nb_fit_to_a4_canvas",
    "nb_get_a4_size",
    "nb_load_input_image_with_dpi",
    "nb_normalize_to_working_dpi",
    "nb_preprocess_page_bgr",
    "nb_preprocessing_stage_4_1",
    "nb_preprocessing_stage_4_2",
    "nb_preprocessing_stage_4_3",
    "nb_preprocessing_stage_5_2_background",
    "nb_preprocessing_stage_5_2_binary_and_denoise",
    "nb_read_json_maybe_gz",
    "nb_rotate_image",
    "nb_rotate_image_by_angle",
]
