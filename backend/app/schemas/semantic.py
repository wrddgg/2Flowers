from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.mode import ModeType


UseIntent = Literal["表达氛围", "gift", "self", "decorate", "celebrate"]


class ColorSwatch(BaseModel):
    label: str
    hex: str


class SemanticResult(BaseModel):
    mode: ModeType
    subject_tags: list[str] = Field(default_factory=list)
    scene_tags: list[str] = Field(default_factory=list)
    emotion_tags: list[str] = Field(default_factory=list)
    visual_tags: list[str] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)
    color_swatches: list[ColorSwatch] = Field(default_factory=list)
    relation_tags: list[str] = Field(default_factory=list)
    use_intent: UseIntent = "表达氛围"
    semantic_summary: str
    translation_axes: list[str] = Field(default_factory=list)
