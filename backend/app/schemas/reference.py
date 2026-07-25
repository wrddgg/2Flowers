from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.mode import ModeType


ReferenceStrategy = Literal["none", "light", "strong"]
ReferenceOption = Literal["color", "structure", "composition", "flower_types", "wrapping"]


class ReferenceItem(BaseModel):
    reference_id: str
    title: str
    source_type: Literal["video", "image"]
    cover_url: str
    mode: ModeType
    flower_types: list[str] = Field(default_factory=list)
    visual_tags: list[str] = Field(default_factory=list)
    emotion_tags: list[str] = Field(default_factory=list)
    scene_tags: list[str] = Field(default_factory=list)
    reference_options: list[ReferenceOption] = Field(default_factory=list)
    reason: str | None = None
    score: int | None = None
    matched_tags: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, int] = Field(default_factory=dict)


class ReferenceSearchRequest(BaseModel):
    mode: ModeType
    semantic_tags: list[str] = Field(default_factory=list)
    semantic_result: "SemanticResult | None" = None
    source_asset_id: str | None = None
    exclude_source_reference: bool = False
    exclude_reference_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=6, ge=1, le=10)


class ReferenceSearchResponse(BaseModel):
    references: list[ReferenceItem]


from app.schemas.semantic import SemanticResult

ReferenceSearchRequest.model_rebuild()
