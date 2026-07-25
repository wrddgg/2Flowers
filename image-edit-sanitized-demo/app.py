from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
ENV_PATH = ROOT / ".env"
MAX_REQUEST_BYTES = 32 * 1024 * 1024
DATA_URL_RE = re.compile(r"^data:image/(png|jpe?g|webp|bmp);base64,[A-Za-z0-9+/=\s]+$")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = load_env(ENV_PATH)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name) or ENV.get(name) or default


def bool_env(name: str, default: bool = False) -> bool:
    value = env(name, str(default)).lower()
    return value in {"1", "true", "yes", "on"}


def upload_root() -> Path:
    configured = Path(env("UPLOAD_DIR", "./uploads"))
    if not configured.is_absolute():
        configured = ROOT / configured
    return configured.resolve()


def json_error(message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> tuple[int, dict[str, Any]]:
    return int(status), {"ok": False, "error": message}


def normalize_boxes(payload_boxes: Any, max_boxes: int) -> list[list[int]]:
    if not isinstance(payload_boxes, list):
        raise ValueError("请先在图片上涂抹或框选需要修改的位置。")
    if len(payload_boxes) == 0:
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


def extract_image_url(response: dict[str, Any]) -> str | None:
    output = response.get("output")
    if not isinstance(output, dict):
        return None

    # DashScope multimodal generation responses commonly return choices with
    # assistant content items that include an "image" URL.
    choices = output.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            message = choice.get("message") if isinstance(choice, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get("image"), str):
                        return item["image"]

    # Keep a few conservative fallbacks for model/version response drift.
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


def save_remote_image(image_url: str) -> str:
    request = urllib.request.Request(image_url, headers={"User-Agent": "ImageEditDemo/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        content_type = response.headers.get("Content-Type", "image/png").split(";", 1)[0].strip()
        data = response.read()

    extension = mimetypes.guess_extension(content_type) or ".png"
    if extension == ".jpe":
        extension = ".jpg"

    result_dir = upload_root() / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{extension}"
    output_path = result_dir / filename
    output_path.write_bytes(data)
    return f"/uploads/results/{filename}"


def call_image_edit_api(image_data_url: str, prompt: str, boxes: list[list[int]]) -> dict[str, Any]:
    api_key = env("DASHSCOPE_API_KEY")
    endpoint = env("WAN_IMAGE_EDIT_ENDPOINT")
    model = env("WAN_IMAGE_EDIT_MODEL", env("WAN_IMAGE_PRO_MODEL", "wan2.7-image-pro"))

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
            "size": env("WAN_IMAGE_EDIT_SIZE", "2K"),
            "n": int(env("WAN_IMAGE_EDIT_N", "1")),
            "watermark": bool_env("WAN_IMAGE_EDIT_WATERMARK", False),
        },
    }

    encoded_body = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=encoded_body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-DashScope-SSE": "disable",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"百炼接口返回错误 {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接百炼接口: {exc.reason}") from exc

    try:
        api_response = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"百炼接口返回了非 JSON 内容: {raw[:240]}") from exc

    image_url = extract_image_url(api_response)
    if not image_url:
        raise RuntimeError(f"百炼接口未返回图片 URL: {json.dumps(api_response, ensure_ascii=False)[:800]}")

    local_image_url = save_remote_image(image_url)
    return {
        "imageUrl": local_image_url,
        "remoteImageUrl": image_url,
        "raw": api_response,
        "requestId": api_response.get("request_id") or api_response.get("requestId"),
    }


class ImageEditHandler(BaseHTTPRequestHandler):
    server_version = "ImageEditDemo/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"", "/"}:
            self.serve_file(STATIC_DIR / "index.html")
            return
        if path.startswith("/static/"):
            relative = path.removeprefix("/static/").replace("/", os.sep)
            self.serve_file(STATIC_DIR / relative)
            return
        if path.startswith("/uploads/"):
            relative = path.removeprefix("/uploads/").replace("/", os.sep)
            self.serve_file(upload_root() / relative, upload_root())
            return
        if path == "/health":
            self.send_json(HTTPStatus.OK, {"ok": True})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/image/edit":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            status, payload = json_error("请求体为空或图片过大。")
            self.send_json(status, payload)
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except json.JSONDecodeError:
            status, data = json_error("请求体不是有效 JSON。")
            self.send_json(status, data)
            return

        try:
            image_data_url = str(payload.get("imageDataUrl", "")).strip()
            prompt = str(payload.get("prompt", "")).strip()
            max_boxes = int(env("WAN_IMAGE_EDIT_MAX_BBOXES", "2"))
            boxes = normalize_boxes(payload.get("boxes"), max_boxes)

            if not prompt:
                status, data = json_error("请输入图片修改指令。")
                self.send_json(status, data)
                return
            if not DATA_URL_RE.match(image_data_url):
                status, data = json_error("图片数据格式不正确，请上传 PNG、JPEG、WEBP 或 BMP 图片。")
                self.send_json(status, data)
                return

            result = call_image_edit_api(image_data_url, prompt, boxes)
            self.send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "imageUrl": result["imageUrl"],
                    "remoteImageUrl": result["remoteImageUrl"],
                    "requestId": result.get("requestId"),
                    "traceId": uuid.uuid4().hex,
                },
            )
        except ValueError as exc:
            status, data = json_error(str(exc))
            self.send_json(status, data)
        except Exception as exc:
            status, data = json_error(str(exc), HTTPStatus.BAD_GATEWAY)
            self.send_json(status, data)

    def serve_file(self, path: Path, base_dir: Path = STATIC_DIR) -> None:
        resolved = path.resolve()
        try:
            resolved.relative_to(base_dir.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not resolved.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        data = resolved.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    host = env("HOST", "127.0.0.1")
    port = int(env("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ImageEditHandler)
    print(f"Image edit demo running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
