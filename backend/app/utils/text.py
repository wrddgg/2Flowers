from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def contains_any(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]
