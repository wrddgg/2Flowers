from __future__ import annotations

import os
from typing import Literal


RuntimeMode = Literal["demo", "test", "production"]


def get_runtime_mode() -> RuntimeMode:
    raw_mode = os.getenv("APP_RUNTIME_MODE", "demo").strip().lower()
    if raw_mode in {"production", "prod", "formal", "release"}:
        return "production"
    if raw_mode in {"demo", "hackathon", "showcase"}:
        return "demo"
    return "test"


def is_test_mode() -> bool:
    return get_runtime_mode() in {"demo", "test"}


def is_demo_mode() -> bool:
    return get_runtime_mode() == "demo"


def is_production_mode() -> bool:
    return get_runtime_mode() == "production"
