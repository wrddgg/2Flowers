from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateTutorialRequest(BaseModel):
    bouquet_image: str = ""
    flowers: list[str] = Field(default_factory=list)
    with_images: bool = True


class TutorialStep(BaseModel):
    step: int
    title: str
    description: str
    image_prompt: str
    image_url: str = ""


class GenerateCardRequest(BaseModel):
    source: str | None = None
    before: str
    after: str
    title: str | None = None
    source_context: str | None = None
    scene_reason: str | None = None


class WrappedResponse(BaseModel):
    code: int = 0
    data: dict[str, Any] | None = None
    message: str = "ok"
