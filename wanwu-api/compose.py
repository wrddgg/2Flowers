"""接口4：合成"原画面 / 我的作品"对比卡片图（1080×1920 上下均分，对齐前端 compose.js）"""
import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _load_image_from_dataurl(data_url: str) -> Image.Image:
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    raw = base64.b64decode(data_url)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """等比缩放并居中裁剪，填满目标尺寸（cover）"""
    w, h = img.size
    scale = max(target_w / w, target_h / h)
    nw, nh = int(w * scale + 0.5), int(h * scale + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - target_w) // 2
    top = (nh - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font) -> None:
    """半透明深色胶囊标签（对齐前端样式）"""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 24, 14
    x1, y1 = x + tw + pad_x * 2, y + th + pad_y * 2
    draw.rounded_rectangle([x, y, x1, y1], radius=(y1 - y) // 2, fill=(31, 41, 55))
    draw.text((x + pad_x, y + pad_y - 2), text, font=font, fill=(255, 255, 255))


def compose_card(before_dataurl: str, after_dataurl: str, title: str, out_path: str) -> str:
    """
    合成对比卡片：1080×1920，上半原画面、下半作品，严格上下均分。
    返回本地路径。
    """
    W, H = 1080, 1920
    half_h = H // 2  # 960，严格均分

    before = _cover_crop(_load_image_from_dataurl(before_dataurl), W, half_h)
    after = _cover_crop(_load_image_from_dataurl(after_dataurl), W, half_h)

    card = Image.new("RGB", (W, H), (250, 248, 243))
    card.paste(before, (0, 0))
    card.paste(after, (0, half_h))

    draw = ImageDraw.Draw(card)
    font_label = _get_font(32)
    _draw_pill(draw, 36, 36, "原画面", font_label)
    _draw_pill(draw, 36, half_h + 36, "我的作品", font_label)

    # 底部水印（叠加在作品图底部，半透明）
    font_sub = _get_font(30)
    sub = "把任何画面，变成一束花"
    sb = draw.textbbox((0, 0), sub, font=font_sub)
    sw = sb[2] - sb[0]
    # 半透明底条
    overlay = Image.new("RGBA", (W, 90), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, 0, W, 90], fill=(0, 0, 0, 90))
    card_rgba = card.convert("RGBA")
    card_rgba.paste(overlay, (0, H - 90), overlay)
    draw2 = ImageDraw.Draw(card_rgba)
    draw2.text(((W - sw) / 2, H - 90 + (90 - (sb[3] - sb[1])) / 2 - 4), sub, font=font_sub, fill=(255, 255, 255))
    card = card_rgba.convert("RGB")

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    card.save(p, format="JPEG", quality=90)
    return str(p)
