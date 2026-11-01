# -*- coding: utf-8 -*-
"""te_man_open.shared.grid_split_core —— grid_split_core.pyd 的纯 Python 复刻。

逆向规格: spec/grid_split_core.md（含末尾"动态 introspection 回填节"）。

模块定位：内部支撑库（非 ComfyUI 节点、不注册路由）。接收 ComfyUI 前端传来的
图片信息（filename/subfolder/type），把图片按行×列拆分为多张小图并保存到
ComfyUI input 目录；图片上有黑色分隔线时按黑线位置智能切分，否则按行列均分。

实现约定（与 shared/ 其他支撑库一致）：
- PIL / folder_paths / 共享路径解析库一律惰性导入或防御式导入，
  模块顶层仅依赖标准库，保证无 ComfyUI/PIL 环境下亦可加载（契约检查会 import 本包）。
- 图片路径解析与 Save_Image_With_Output 共享：优先
  ``from .save_output_core import resolve_image_info_path``，不可用时在本模块内
  实现最小路径解析（含目录白名单与路径穿越防护）。
"""

import os
import re
import uuid
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "GRID_SEPARATOR_LUMA_THRESHOLD",
    "GRID_SEPARATOR_DARK_RATIO_THRESHOLD",
    "GRID_SEPARATOR_MIN_BAND_THICKNESS",
    "split_image_to_grid_input_files",
]

# ---------------------------------------------------------------------------
# 模块级常量（黑线检测三参数：静态反汇编 + 动态 introspection 双通道实锤）
# ---------------------------------------------------------------------------

#: 像素暗判定阈值（0–255 亮度尺度，BT.709 luma）
GRID_SEPARATOR_LUMA_THRESHOLD = 26

#: 分隔带内暗像素占比阈值
GRID_SEPARATOR_DARK_RATIO_THRESHOLD = 0.9

#: 分隔带最小厚度（px）
GRID_SEPARATOR_MIN_BAND_THICKNESS = 2

#: 逐行/逐列扫描时把相邻"较暗"扫描线聚成候选带的局部阈值（函数内局部立即数，
#: 原版角色未确认，取保守值；带级筛选仍用 GRID_SEPARATOR_DARK_RATIO_THRESHOLD）
_LINE_DARK_RATIO = 0.5

#: 文件名净化正则（规格 §3.6 字符串证据）
_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9._-]+")

#: 净化后 stem 为空时的回退名（routes 双胞胎的对应回退是 te_crop）
_FALLBACK_STEM = "te_grid"

# ---------------------------------------------------------------------------
# 与 save_output_core / save_image_with_output_core 的共享路径解析（防御式导入）
# ---------------------------------------------------------------------------

_SHARED_RESOLVE_IMAGE_INFO_PATH = None
try:  # te_man_open 复刻包内的共享核心
    from .save_output_core import resolve_image_info_path as _SHARED_RESOLVE_IMAGE_INFO_PATH
except Exception:  # noqa: BLE001
    try:  # 兼容原版模块名
        from .save_image_with_output_core import resolve_image_info_path as _SHARED_RESOLVE_IMAGE_INFO_PATH
    except Exception:  # noqa: BLE001
        _SHARED_RESOLVE_IMAGE_INFO_PATH = None


def _get_input_directory() -> str:
    """定位 ComfyUI input 目录（folder_paths 惰性导入）。"""
    try:
        import folder_paths
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("无法定位 ComfyUI input 目录: {}".format(e)) from e
    return folder_paths.get_input_directory()


# ---------------------------------------------------------------------------
# 路径解析（原版委托 save_image_with_output_core.resolve_image_info_path，
# 此处保留同名入口；共享库不可用时给出最小防御式实现）
# ---------------------------------------------------------------------------

def _resolve_shared_image_info_path(image_info: Dict[str, Any]) -> str:
    """最小路径解析：目录白名单（input/temp/output）+ 子目录穿越防护。

    错误文案与 save_image_with_output_core.pyd 的共享实现保持一致
    （spec/save_image_with_output_core.md §5）。
    """
    if not isinstance(image_info, dict):
        raise ValueError("非法的图片路径")
    filename = str(image_info.get("filename") or "").strip()
    if not filename:
        raise ValueError("缺少图片文件名")
    image_type = str(image_info.get("type") or "input").strip() or "input"
    subfolder = str(image_info.get("subfolder") or "").strip()

    try:
        import folder_paths
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("无法解析图片目录: {}".format(e)) from e
    base = folder_paths.get_directory_by_type(image_type)
    if not base:
        raise ValueError("不支持的图片目录类型: {}".format(image_type))

    if subfolder:
        norm = os.path.normpath(subfolder)
        if os.path.isabs(norm) or norm == ".." or norm.startswith(".." + os.sep):
            raise ValueError("非法的图片子目录")
        full = os.path.join(base, norm, filename)
    else:
        full = os.path.join(base, filename)

    real_base = os.path.realpath(base)
    real_full = os.path.realpath(full)
    try:
        inside = os.path.commonpath([real_base, real_full]) == real_base
    except ValueError:
        inside = False
    if not inside:
        raise ValueError("非法的图片路径")
    if not os.path.isfile(real_full):
        raise FileNotFoundError("图片不存在: {}".format(filename))
    return real_full


def _resolve_ui_image_path(image_info: Dict[str, Any]) -> str:
    """解析 ComfyUI 前端图片信息 → 实际文件路径（优先共享解析库）。"""
    if _SHARED_RESOLVE_IMAGE_INFO_PATH is not None:
        return _SHARED_RESOLVE_IMAGE_INFO_PATH(image_info)
    return _resolve_shared_image_info_path(image_info)


# ---------------------------------------------------------------------------
# 黑线检测（BT.709 亮度权重 0.2126 / 0.7152 / 0.0722）
# ---------------------------------------------------------------------------

def _get_pixel_luma(pixel: Sequence[Any]) -> float:
    """BT.709 亮度（0–255 尺度）；多余通道（A 等）忽略。"""
    r = float(pixel[0])
    g = float(pixel[1])
    b = float(pixel[2])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _is_dark_separator_pixel(pixel: Sequence[Any]) -> bool:
    """单个像素是否属于黑色分隔线。

    RGBA 时基本透明的像素按背景处理（不计入分隔线）——原版细节未确认，
    属防御性推断（spec §3 步骤 4）。
    """
    if len(pixel) >= 4 and float(pixel[3]) < 16.0:
        return False
    return _get_pixel_luma(pixel) <= GRID_SEPARATOR_LUMA_THRESHOLD


def _detect_dark_bands(image, axis: str) -> List[Dict[str, Any]]:
    """按方向扫描候选暗带。

    axis="horizontal" → 逐行扫描（检测水平延伸的分隔线，用于切行）；
    axis="vertical"   → 逐列扫描（检测垂直延伸的分隔线，用于切列）。

    返回带列表：{"start", "end"( exclusive), "center", "thickness", "averageRatio"}，
    仅保留 thickness ≥ GRID_SEPARATOR_MIN_BAND_THICKNESS 且
    averageRatio ≥ GRID_SEPARATOR_DARK_RATIO_THRESHOLD 的带。
    """
    width, height = image.size
    if width <= 0 or height <= 0:
        return []
    pixels = image.load()
    if axis == "horizontal":
        scan_total, span = height, width

        def pixel_at(i, j):
            return pixels[j, i]

    else:
        scan_total, span = width, height

        def pixel_at(i, j):
            return pixels[i, j]

    raw_bands = []
    current = None
    for i in range(scan_total):
        dark = 0
        for j in range(span):
            if _is_dark_separator_pixel(pixel_at(i, j)):
                dark += 1
        ratio = dark / float(span) if span else 0.0
        if ratio >= _LINE_DARK_RATIO:
            if current is None:
                current = {"start": i, "end": i, "ratios": [ratio]}
            else:
                current["end"] = i
                current["ratios"].append(ratio)
        elif current is not None:
            raw_bands.append(current)
            current = None
    if current is not None:
        raw_bands.append(current)

    bands = []
    for band in raw_bands:
        thickness = band["end"] - band["start"] + 1
        average_ratio = sum(band["ratios"]) / float(len(band["ratios"]))
        if (
            thickness >= GRID_SEPARATOR_MIN_BAND_THICKNESS
            and average_ratio >= GRID_SEPARATOR_DARK_RATIO_THRESHOLD
        ):
            bands.append(
                {
                    "start": band["start"],
                    "end": band["end"] + 1,  # exclusive
                    "center": (band["start"] + band["end"] + 1) / 2.0,
                    "thickness": thickness,
                    "averageRatio": average_ratio,
                }
            )
    return bands


def _select_separator_bands(
    bands: List[Dict[str, Any]], segment_count: int, dimension: int
) -> Optional[List[Dict[str, Any]]]:
    """在候选带中选出最佳分隔带组合（目标数 = segment_count - 1）。

    只考虑内部带（不贴图像边缘，避免黑边框被当成分隔线）；打分取各带中心到
    均分理想分隔位置的累计距离，取最小者。组合搜索空间过大时退化为按距离贪心。
    候选不足时返回 None（调用方回退均分）。
    """
    if segment_count <= 1:
        return []
    separator_count = segment_count - 1
    internal_bands = [b for b in bands if b["start"] > 0 and b["end"] < dimension]
    if len(internal_bands) < separator_count:
        return None

    ideal = [dimension * k / float(segment_count) for k in range(1, segment_count)]

    def band_distance(band: Dict[str, Any]) -> float:
        return min(abs(band["center"] - p) for p in ideal)

    def score(selection: Sequence[Dict[str, Any]]) -> float:
        return sum(band_distance(b) for b in selection)

    if comb(len(internal_bands), separator_count) <= 20000:

        def search(candidates: List[Dict[str, Any]], need: int) -> Optional[List[Dict[str, Any]]]:
            best: Optional[Tuple[Dict[str, Any], ...]] = None
            best_score: Optional[float] = None
            for combo in combinations(candidates, need):
                current_score = score(combo)
                if best_score is None or current_score < best_score:
                    best = combo
                    best_score = current_score
            return list(best) if best is not None else None

        selected = search(internal_bands, separator_count)
    else:
        ordered = sorted(internal_bands, key=band_distance)
        selected = ordered[:separator_count]

    if selected is None:
        return None
    return sorted(selected, key=lambda b: b["start"])


def _build_axis_slices_from_bands(
    bands: List[Dict[str, Any]], dimension: int, segment_count: int
) -> Optional[List[Tuple[int, int]]]:
    """按分隔带把一个轴切成 (start, end) 段；过窄切片或段数不符时判失败。"""
    if len(bands) != max(0, segment_count - 1):
        return None
    slices: List[Tuple[int, int]] = []
    prev = 0
    for band in bands:
        if band["start"] <= prev or band["end"] > dimension:
            return None
        slices.append((prev, int(band["start"])))
        prev = int(band["end"])
    slices.append((prev, dimension))
    # 最小切片宽度/高度过滤（原版 min_allowed_width/height 的具体缩放未确认，
    # 按常量池局部立即数 0.02 / 24.0 的推断取保守实现）
    min_allowed = max(2.0, dimension * 0.02)
    for start, end in slices:
        if (end - start) < min_allowed:
            return None
    return slices


def _build_equal_axis_slices(dimension: int, segment_count: int) -> List[Tuple[int, int]]:
    """黑线检测失败时的行列均匀切分。"""
    if segment_count <= 0:
        return [(0, dimension)]
    step = dimension / float(segment_count)
    slices = []
    for k in range(segment_count):
        start = int(round(k * step))
        if k == segment_count - 1:
            end = dimension
        else:
            end = int(round((k + 1) * step))
        if end <= start:
            end = min(dimension, start + 1)
        slices.append((start, end))
    return slices


def _detect_grid_slices_from_black_lines(
    image, rows: int, cols: int
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """先按黑线切分；任一轴失败则该轴回退均分。"""
    height, width = image.size[1], image.size[0]
    row_bands = _detect_dark_bands(image, "horizontal")
    col_bands = _detect_dark_bands(image, "vertical")
    row_selected = _select_separator_bands(row_bands, rows, height)
    col_selected = _select_separator_bands(col_bands, cols, width)
    row_slices = (
        _build_axis_slices_from_bands(row_selected, height, rows)
        if row_selected is not None
        else None
    )
    col_slices = (
        _build_axis_slices_from_bands(col_selected, width, cols)
        if col_selected is not None
        else None
    )
    if row_slices is None:
        row_slices = _build_equal_axis_slices(height, rows)
    if col_slices is None:
        col_slices = _build_equal_axis_slices(width, cols)
    return row_slices, col_slices


def _sanitize_filename_stem(value: Any) -> str:
    """净化源图 stem：非法字符替换为下划线并剥离首尾 ``._-``，空则回退 te_grid。"""
    cleaned = _SANITIZE_RE.sub("_", str(value or "")).strip("._-")
    return cleaned or _FALLBACK_STEM


# ---------------------------------------------------------------------------
# 唯一对外 API
# ---------------------------------------------------------------------------

def split_image_to_grid_input_files(
    image_info: Dict[str, Any], rows: Any, cols: Any
) -> List[Dict[str, Any]]:
    """把图片按 rows×cols 拆分并落盘到 ComfyUI input 目录。

    返回 ``[{"filename", "subfolder", "type": "input"}, ...]``（routes 层原样放入
    ``{"success": True, "images": [...]}``）。

    错误文案（与原版一致，spec/grid_split_core.md §5）：
    - ``rows 和 cols 必须大于 0``
    - ``当前图片尺寸无效，无法拆分``
    """
    try:
        rows_i = int(rows)
        cols_i = int(cols)
    except (TypeError, ValueError):
        raise ValueError("rows 和 cols 必须大于 0") from None
    if rows_i <= 0 or cols_i <= 0:
        raise ValueError("rows 和 cols 必须大于 0")

    image_path = _resolve_ui_image_path(image_info)

    from PIL import Image, ImageOps  # 惰性导入

    with Image.open(image_path) as src:
        oriented = ImageOps.exif_transpose(src)
        try:
            width, height = oriented.size
        except Exception:  # noqa: BLE001
            width, height = 0, 0
        if not width or not height:
            raise ValueError("当前图片尺寸无效，无法拆分")

        work = oriented.convert("RGB")
        row_slices, col_slices = _detect_grid_slices_from_black_lines(work, rows_i, cols_i)

        input_root = Path(_get_input_directory())
        raw_stem = Path(str(image_info.get("filename") or "")).stem
        stem = _sanitize_filename_stem(raw_stem)

        results: List[Dict[str, Any]] = []
        index = 0
        for y0, y1 in row_slices:
            for x0, x1 in col_slices:
                tile = work.crop((x0, y0, x1, y1))
                filename = "{}_grid_{:02d}.png".format(stem, index)
                target = input_root / filename
                if target.exists():  # uuid4().hex 用于文件名防重（spec §3.6）
                    filename = "{}_grid_{:02d}_{}.png".format(stem, index, uuid.uuid4().hex[:10])
                    target = input_root / filename
                tile.save(str(target), format="PNG")
                results.append({"filename": filename, "subfolder": "", "type": "input"})
                index += 1
        return results
