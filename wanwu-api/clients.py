"""模型客户端：qwen 视觉/文本 + wan 文生图"""
import base64
import io
import json
import time
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI
from PIL import Image

from config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# 工具：base64 dataURL 处理
# ---------------------------------------------------------------------------
def dataurl_to_bytes(data_url: str, max_side: int = 1280, quality: int = 88) -> bytes:
    """把 dataURL(base64) 解码并压缩为 JPEG 字节，控制请求体体积"""
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    raw = base64.b64decode(data_url)
    with Image.open(io.BytesIO(raw)) as img:
        img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, max_side / max(w, h))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()


def bytes_to_dataurl(data: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def dataurl_to_inline(data_url: str) -> str:
    """把外部 dataURL 规范化为可传给视觉模型的内联 dataURL（压缩后）"""
    return bytes_to_dataurl(dataurl_to_bytes(data_url))


# ---------------------------------------------------------------------------
# qwen 视觉 / 文本
# ---------------------------------------------------------------------------
def get_qwen_client() -> OpenAI:
    """每次新建客户端，避免跨线程共享底层连接"""
    return OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.qwen_base_url,
    )


def call_vision_json(prompt: str, image_urls: list[str], model: str | None = None) -> dict[str, Any]:
    """调用视觉模型并返回 JSON。image_urls 可为 dataURL 或公网 URL"""
    client = get_qwen_client()
    model = model or settings.qwen_vl_model

    content: list[dict[str, Any]] = []
    for url in image_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    content.append({"type": "text", "text": prompt})

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    raw = resp.choices[0].message.content
    if not raw:
        raise RuntimeError("视觉模型未返回内容")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"视觉模型返回的JSON无法解析: {raw[:300]}") from exc


def call_text_json(prompt: str, model: str | None = None) -> dict[str, Any]:
    """调用文本模型并返回 JSON"""
    client = get_qwen_client()
    model = model or settings.qwen_text_model
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        response_format={"type": "json_object"},
        temperature=0.5,
    )
    raw = resp.choices[0].message.content
    if not raw:
        raise RuntimeError("文本模型未返回内容")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"文本模型返回的JSON无法解析: {raw[:300]}") from exc


# ---------------------------------------------------------------------------
# wan 文生图
# ---------------------------------------------------------------------------
def create_wan_text2image_task(prompt: str, *, model: str | None = None, size: str = "1K") -> str:
    """创建 wan 文生图异步任务（MaaS 端点 image-generation 路径，多模态消息格式），返回 task_id"""
    model = model or settings.wan_image_model
    payload = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": {"size": size, "n": 1, "watermark": False},
    }
    resp = requests.post(
        f"{settings.dashscope_base_url}/api/v1/services/aigc/image-generation/generation",
        headers={
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        },
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    task_id = (data.get("output") or {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"创建文生图任务失败: {data}")
    return task_id


def get_wan_task(task_id: str) -> dict:
    resp = requests.get(
        f"{settings.dashscope_base_url}/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_image_url(output: dict) -> str | None:
    """从任务 output 中提取图片 URL，兼容两种返回结构"""
    # 结构1：output.results[0].url（官方 dashscope）
    results = output.get("results") or []
    if results and results[0].get("url"):
        return results[0]["url"]
    # 结构2：output.choices[0].message.content[*].image（MaaS 多模态）
    for choice in output.get("choices") or []:
        content = (choice.get("message") or {}).get("content") or []
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("image"):
                    return part["image"]
        elif isinstance(content, str) and content.startswith("http"):
            return content
    return None


def wait_wan_image_url(task_id: str, *, timeout_seconds: int = 240) -> str:
    """轮询等待任务完成，返回图片临时 URL"""
    start = time.monotonic()
    interval = 1.5
    while True:
        data = get_wan_task(task_id)
        output = data.get("output") or {}
        status = output.get("task_status")
        if status == "SUCCEEDED":
            url = _extract_image_url(output)
            if url:
                return url
            raise RuntimeError(f"任务成功但未找到图片URL: {data}")
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise RuntimeError(f"文生图任务结束，状态={status}: {data}")
        if time.monotonic() - start > timeout_seconds:
            raise TimeoutError(f"文生图任务等待超时 task_id={task_id}")
        time.sleep(interval)
        interval = min(interval * 1.2, 4.0)


def download_image(url: str, out_path: str) -> str:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(resp.content)
    return str(p)


def text2image(prompt: str, out_path: str, *, size: str = "1K") -> str:
    """文生图一站式：创建任务→等待→下载到本地，返回本地路径"""
    task_id = create_wan_text2image_task(prompt, size=size)
    url = wait_wan_image_url(task_id)
    return download_image(url, out_path)
