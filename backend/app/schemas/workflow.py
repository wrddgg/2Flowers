from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ComparePanel(BaseModel):
    key: str
    label: str
    order: int
    image_role: str


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
    image_status: str = "pending"
    image_review: str = ""
    image_review_score: float = 0.0
    image_review_issues: list[str] = Field(default_factory=list)
    image_retry_count: int = 0
    image_display_ratio: str = "3:4"
    image_display_fit: str = "contain"


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
