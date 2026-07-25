from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse


BACKEND_DIR = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = BACKEND_DIR.parent
LIBRARY_ASSET_DIR = WORKSPACE_DIR / "images"
MOCK_ASSET_DIR = BACKEND_DIR / "data" / "mock_assets"


def upload_root() -> Path:
    configured = Path(os.getenv("UPLOAD_DIR", "./uploads"))
    if not configured.is_absolute():
        configured = WORKSPACE_DIR / configured
    return configured.resolve()


def resolve_local_image_path(image_url: str) -> Path | None:
    candidate = image_url.strip()
    if not candidate:
        return None

    # base64 dataURL 不是本地文件，直接透传（避免被当路径解析导致超长崩溃）
    if candidate.startswith("data:"):
        return None

    if candidate.startswith("/library/assets/"):
        asset_name = Path(candidate).name
        asset_path = LIBRARY_ASSET_DIR / asset_name
        return asset_path if asset_path.exists() else None

    if candidate.startswith("/mock/assets/"):
        asset_name = Path(candidate).name
        asset_path = MOCK_ASSET_DIR / asset_name
        return asset_path if asset_path.exists() else None

    if candidate.startswith("/uploads/"):
        relative_path = candidate.removeprefix("/uploads/").strip("/")
        if not relative_path:
            return None
        upload_path = upload_root() / relative_path
        return upload_path if upload_path.exists() else None

    if candidate.startswith("file://"):
        file_path = Path(urlparse(candidate).path)
        return file_path if file_path.exists() else None

    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"}:
        return None

    direct_path = Path(candidate)
    if direct_path.is_absolute() and direct_path.exists():
        return direct_path

    backend_path = (BACKEND_DIR / candidate).resolve()
    if backend_path.exists():
        return backend_path

    workspace_path = (WORKSPACE_DIR / candidate).resolve()
    if workspace_path.exists():
        return workspace_path

    return None


def to_provider_image_input(image_url: str) -> str:
    local_path = resolve_local_image_path(image_url)
    if local_path is None:
        return image_url
    return path_to_data_url(local_path)


def path_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"
