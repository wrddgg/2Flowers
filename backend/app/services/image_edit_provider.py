from __future__ import annotations

import mimetypes
import os
import re
import uuid
from pathlib import Path

import httpx


DATA_URL_RE = re.compile(r"^data:image/(png|jpe?g|webp|bmp);base64,[A-Za-z0-9+/=\s]+$")
MAX_REQUEST_BYTES = 32 * 1024 * 1024


class ImageEditProvider:
    def upload_root(self) -> Path:
        configured = Path(os.getenv("UPLOAD_DIR", "./uploads"))
        if not configured.is_absolute():
            configured = Path(__file__).resolve().parents[3] / configured
        return configured.resolve()

    def normalize_boxes(self, payload_boxes: object, max_boxes: int) -> list[list[int]]:
        if not isinstance(payload_boxes, list) or not payload_boxes:
            raise ValueError("请先在图片上涂抹或框选需要修改的位置。")
        if len(payload_boxes) > max_boxes:
            raise ValueError(f"最多支持 {max_boxes} 个修改区域。")

        boxes: list[list[int]] = []
        for raw_box in payload_boxes:
            if not isinstance(raw_box, list) or len(raw_box) != 4:
                raise ValueError("区域坐标格式不正确。")
            try:
                x1, y1, x2, y2 = [int(round(float(v))) for v in raw_box]
            except (TypeError, ValueError) as exc:
                raise ValueError("区域坐标必须是数字。") from exc

            left, right = sorted((x1, x2))
            top, bottom = sorted((y1, y2))
            if right - left < 4 or bottom - top < 4:
                raise ValueError("修改区域太小，请涂抹或框选更大的范围。")
            boxes.append([left, top, right, bottom])
        return boxes

    def validate_image_data_url(self, image_data_url: str) -> None:
        if not DATA_URL_RE.match(image_data_url):
            raise ValueError("图片数据格式不正确，请上传 PNG、JPEG、WEBP 或 BMP 图片。")
        if len(image_data_url.encode("utf-8")) > MAX_REQUEST_BYTES:
            raise ValueError("图片过大，请压缩后重试。")

    def edit(self, image_data_url: str, prompt: str, boxes: list[list[int]]) -> dict[str, str | None]:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        endpoint = os.getenv("WAN_IMAGE_EDIT_ENDPOINT")
        model = os.getenv("WAN_IMAGE_EDIT_MODEL") or os.getenv("WAN_IMAGE_PRO_MODEL") or "wan2.7-image-pro"

        if not api_key:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY，请先在 .env 中配置。")
        if not endpoint:
            raise RuntimeError("缺少 WAN_IMAGE_EDIT_ENDPOINT，请先在 .env 中配置。")

        request_body = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": image_data_url},
                            {"text": prompt},
                        ],
                    }
                ]
            },
            "parameters": {
                "bbox_list": [boxes],
                "size": os.getenv("WAN_IMAGE_EDIT_SIZE", "2K"),
                "n": int(os.getenv("WAN_IMAGE_EDIT_N", "1")),
                "watermark": _bool_env("WAN_IMAGE_EDIT_WATERMARK", False),
            },
        }

        try:
            with httpx.Client(timeout=180.0) as client:
                response = client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "X-DashScope-SSE": "disable",
                    },
                    json=request_body,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:1000]
            raise RuntimeError(f"百炼接口返回错误 {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"无法连接百炼接口: {exc}") from exc

        api_response = response.json()
        remote_image_url = self.extract_image_url(api_response)
        if not remote_image_url:
            raise RuntimeError(f"百炼接口未返回图片 URL: {str(api_response)[:800]}")

        local_image_url = self.save_remote_image(remote_image_url)
        return {
            "imageUrl": local_image_url,
            "remoteImageUrl": remote_image_url,
            "requestId": api_response.get("request_id") or api_response.get("requestId"),
        }

    def extract_image_url(self, response: dict[str, object]) -> str | None:
        output = response.get("output")
        if not isinstance(output, dict):
            return None

        choices = output.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get("image"), str):
                        return item["image"]

        for key in ("image", "url"):
            value = output.get(key)
            if isinstance(value, str):
                return value

        results = output.get("results")
        if isinstance(results, list):
            for result in results:
                if not isinstance(result, dict):
                    continue
                for key in ("image", "url"):
                    value = result.get(key)
                    if isinstance(value, str):
                        return value
        return None

    def save_remote_image(self, image_url: str) -> str:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(image_url, headers={"User-Agent": "WanwuShenghua/0.1"})
            response.raise_for_status()

        content_type = response.headers.get("Content-Type", "image/png").split(";", 1)[0].strip()
        extension = mimetypes.guess_extension(content_type) or ".png"
        if extension == ".jpe":
            extension = ".jpg"

        result_dir = self.upload_root() / "results"
        result_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}{extension}"
        output_path = result_dir / filename
        output_path.write_bytes(response.content)
        return f"/uploads/results/{filename}"


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).lower()
    return value in {"1", "true", "yes", "on"}
