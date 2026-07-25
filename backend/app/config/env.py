from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]


@lru_cache
def load_environment() -> None:
    """Load environment files in a predictable order.

    Order:
    1. .env
    2. .env.test or .env.production
    3. process environment variables override file values
    """
    base_env_file = BASE_DIR / ".env"
    base_values = {
        key: value
        for key, value in dotenv_values(base_env_file).items()
        if value is not None
    }
    original_env = dict(os.environ)
    load_dotenv(base_env_file, override=False)

    runtime_mode = os.getenv("APP_RUNTIME_MODE", "demo").strip().lower() or "demo"
    mode_file = BASE_DIR / f".env.{runtime_mode}"
    if mode_file.exists():
        mode_values = {
            key: value
            for key, value in dotenv_values(mode_file).items()
            if value is not None
        }
        for key, value in mode_values.items():
            if key not in original_env and os.getenv(key) == base_values.get(key):
                os.environ[key] = value
            elif key not in os.environ:
                os.environ[key] = value
