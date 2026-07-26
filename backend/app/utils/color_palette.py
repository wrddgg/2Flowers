from __future__ import annotations

from app.schemas.semantic import ColorSwatch


COLOR_NAME_HEX = {
    "深蓝": "#355C7D",
    "蓝白": "#A8C5DA",
    "浅蓝": "#BFD7EA",
    "雾蓝": "#9EB6C8",
    "海盐蓝": "#8DA9C4",
    "白色": "#F7F4EE",
    "奶白": "#F3E9DA",
    "米白": "#E9DEC9",
    "暖白": "#F5EBDD",
    "象牙白": "#F7F1E3",
    "香槟色": "#E6C79C",
    "香槟金": "#D8B26E",
    "暖黄": "#F3C567",
    "浅黄": "#F6DEA6",
    "金黄": "#DDAE45",
    "粉白": "#EFD6D2",
    "柔粉": "#E7C3CB",
    "豆沙粉": "#C98C94",
    "珊瑚粉": "#E9A39B",
    "红橙": "#D86B4D",
    "橙色": "#E58F65",
    "暖橙": "#E8A15C",
    "浅绿": "#B7C9A8",
    "鼠尾草绿": "#9CAF88",
    "银灰": "#C8CCD0",
    "灰绿": "#AEB8A2",
    "紫色": "#A88BBE",
    "淡紫": "#C4B2D6",
}

VISUAL_TAG_HEX = {
    "冷色": "#7FA7C6",
    "暖色": "#E8B07C",
    "留白": "#F5F2EA",
    "空气感": "#DCE7EF",
    "高级": "#8C7B75",
    "克制": "#B7C2CC",
    "治愈": "#C7D8C6",
    "轻治愈": "#D7E7D1",
}


def build_color_swatches(color_palette: list[str], visual_tags: list[str]) -> list[ColorSwatch]:
    swatches: list[ColorSwatch] = []
    seen: set[str] = set()

    for label in color_palette:
        hex_code = resolve_color_hex(label)
        if not hex_code or hex_code in seen:
            continue
        swatches.append(ColorSwatch(label=label, hex=hex_code))
        seen.add(hex_code)

    if swatches:
        return swatches[:4]

    for tag in visual_tags:
        hex_code = VISUAL_TAG_HEX.get(tag)
        if not hex_code or hex_code in seen:
            continue
        swatches.append(ColorSwatch(label=tag, hex=hex_code))
        seen.add(hex_code)
        if len(swatches) >= 4:
            break
    return swatches


def build_dominant_color_palette(color_palette: list[str], visual_tags: list[str]) -> list[str]:
    dominant: list[str] = []
    seen: set[str] = set()

    for label in color_palette:
        normalized = str(label or "").strip()
        if not normalized:
            continue
        dedupe_key = resolve_color_hex(normalized) or normalized
        if dedupe_key in seen:
            continue
        dominant.append(normalized)
        seen.add(dedupe_key)
        if len(dominant) >= 2:
            return dominant

    for tag in visual_tags:
        normalized = str(tag or "").strip()
        if normalized not in VISUAL_TAG_HEX:
            continue
        dedupe_key = VISUAL_TAG_HEX[normalized]
        if dedupe_key in seen:
            continue
        dominant.append(normalized)
        seen.add(dedupe_key)
        if len(dominant) >= 2:
            break
    return dominant


def resolve_color_hex(label: str) -> str | None:
    normalized = str(label or "").strip()
    if not normalized:
        return None
    if normalized.startswith("#") and len(normalized) in {4, 7}:
        return normalized.upper()
    if normalized in COLOR_NAME_HEX:
        return COLOR_NAME_HEX[normalized]
    for key, value in COLOR_NAME_HEX.items():
        if key in normalized or normalized in key:
            return value
    return None
