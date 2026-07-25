from __future__ import annotations

import json
import mimetypes
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config.runtime import is_test_mode
from app.utils.image_assets import to_provider_image_input


def upload_root() -> Path:
    configured = Path(os.getenv("UPLOAD_DIR", "./uploads"))
    if not configured.is_absolute():
        configured = Path(__file__).resolve().parents[3] / configured
    return configured.resolve()


def public_upload_url(local_path: str | Path) -> str:
    path = Path(local_path).resolve()
    rel = path.relative_to(upload_root()).as_posix()
    base = os.getenv("PUBLIC_BASE", "").rstrip("/")
    return f"{base}/uploads/{rel}" if base else f"/uploads/{rel}"


def has_qwen_text_config() -> bool:
    return bool(_chat_base_url() and _api_key())


def has_wan_image_config() -> bool:
    return bool(_api_key() and _dashscope_base_url())


def call_text_json(
    prompt: str,
    model: str | None = None,
    *,
    system_prompt: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    resolved_base_url = (base_url or _chat_base_url()).rstrip("/")
    resolved_api_key = api_key or _api_key()
    if is_test_mode() or not resolved_base_url or not resolved_api_key:
        raise RuntimeError("text model unavailable")
    endpoint = f"{resolved_base_url}/chat/completions"
    messages: list[dict[str, object]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": [{"type": "text", "text": prompt}]})
    payload = {
        "model": model or os.getenv("QWEN_TEXT_MODEL", "qwen-turbo"),
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.5,
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {resolved_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    raw = (((response.json().get("choices") or [{}])[0]).get("message") or {}).get("content")
    if not raw:
        raise RuntimeError("text model returned empty content")
    if isinstance(raw, list):
        raw = "".join(
            part.get("text", "") for part in raw if isinstance(part, dict)
        )
    return json.loads(raw)


def call_multimodal_json(
    prompt: str,
    image_urls: list[str],
    model: str | None = None,
    *,
    system_prompt: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    resolved_base_url = (base_url or _chat_base_url()).rstrip("/")
    resolved_api_key = api_key or _api_key()
    if is_test_mode() or not resolved_base_url or not resolved_api_key:
        raise RuntimeError("multimodal model unavailable")
    endpoint = f"{resolved_base_url}/chat/completions"
    user_content: list[dict[str, Any]] = []
    for image_url in image_urls:
        cleaned = str(image_url or "").strip()
        if not cleaned:
            continue
        user_content.append({"type": "image_url", "image_url": {"url": to_provider_image_input(cleaned)}})
    user_content.append({"type": "text", "text": prompt})

    messages: list[dict[str, object]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})
    payload = {
        "model": model or os.getenv("QWEN_TEXT_MODEL", "qwen-vl-max-latest"),
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {resolved_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    raw = (((response.json().get("choices") or [{}])[0]).get("message") or {}).get("content")
    if not raw:
        raise RuntimeError("multimodal model returned empty content")
    if isinstance(raw, list):
        raw = "".join(part.get("text", "") for part in raw if isinstance(part, dict))
    return json.loads(raw)


def text2image(prompt: str, out_path: str, *, size: str = "1K") -> str:
    if is_test_mode() or not has_wan_image_config():
        raise RuntimeError("image model unavailable")

    task_id = _create_image_task(prompt, size=size)
    remote_url = _wait_image_url(task_id)
    return _download_image(remote_url, out_path)


def _create_image_task(prompt: str, *, size: str) -> str:
    payload = {
        "model": os.getenv("WAN_IMAGE_MODEL", "wan2.7-image"),
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": {"size": size, "n": 1, "watermark": False},
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{_dashscope_base_url().rstrip('/')}/api/v1/services/aigc/image-generation/generation",
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
            },
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    task_id = (data.get("output") or {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"create image task failed: {str(data)[:500]}")
    return task_id


def _wait_image_url(task_id: str, timeout_seconds: int = 240) -> str:
    start = time.monotonic()
    interval = 1.2
    while True:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{_dashscope_base_url().rstrip('/')}/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {_api_key()}"},
            )
            response.raise_for_status()
        data = response.json()
        output = data.get("output") or {}
        status = output.get("task_status")
        if status == "SUCCEEDED":
            url = _extract_image_url(output)
            if url:
                return url
            raise RuntimeError("image task succeeded without image url")
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise RuntimeError(f"image task failed: {status}")
        if time.monotonic() - start > timeout_seconds:
            raise TimeoutError(f"image task timeout: {task_id}")
        time.sleep(interval)
        interval = min(interval * 1.2, 4.0)


def _extract_image_url(output: dict[str, Any]) -> str | None:
    results = output.get("results") or []
    if results and isinstance(results[0], dict):
        url = results[0].get("url")
        if isinstance(url, str):
            return url

    for choice in output.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        content = (choice.get("message") or {}).get("content") or []
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("image"), str):
                    return part["image"]
        elif isinstance(content, str) and content.startswith("http"):
            return content
    return None


def _download_image(url: str, out_path: str) -> str:
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = target.suffix
    if not suffix:
        extension = mimetypes.guess_extension(response.headers.get("Content-Type", "image/png").split(";", 1)[0].strip()) or ".png"
        if extension == ".jpe":
            extension = ".jpg"
        target = target.with_suffix(extension)
    target.write_bytes(response.content)
    return str(target)


def create_result_path(folder: str, stem: str, suffix: str) -> Path:
    return upload_root() / folder / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"


def resolve_workflow_planner_config() -> tuple[str | None, str | None, str]:
    base_url = (
        os.getenv("WORKFLOW_PLANNER_API_URL")
        or os.getenv("PLANNER_API_URL")
        or os.getenv("SEMANTIC_API_URL")
        or os.getenv("QWEN_BASE_URL")
    )
    api_key = (
        os.getenv("WORKFLOW_PLANNER_API_KEY")
        or os.getenv("PLANNER_API_KEY")
        or os.getenv("SEMANTIC_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    model = (
        os.getenv("WORKFLOW_PLANNER_MODEL")
        or os.getenv("PLANNER_MODEL")
        or os.getenv("QWEN_TEXT_MODEL")
        or "qwen-turbo"
    )
    return base_url, api_key, model


def resolve_workflow_text_config() -> tuple[str | None, str | None, str]:
    base_url = (
        os.getenv("WORKFLOW_TEXT_API_URL")
        or os.getenv("WORKFLOW_PLANNER_API_URL")
        or os.getenv("QWEN_BASE_URL")
    )
    api_key = (
        os.getenv("WORKFLOW_TEXT_API_KEY")
        or os.getenv("WORKFLOW_PLANNER_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    model = (
        os.getenv("WORKFLOW_TEXT_MODEL")
        or os.getenv("QWEN_TEXT_MODEL")
        or os.getenv("WORKFLOW_PLANNER_MODEL")
        or "qwen-turbo"
    )
    return base_url, api_key, model


def _chat_base_url() -> str:
    return os.getenv("QWEN_BASE_URL", "") or os.getenv("OPENAI_COMPAT_BASE_URL", "")


def _dashscope_base_url() -> str:
    return os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode")


def _api_key() -> str:
    return os.getenv("DASHSCOPE_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
