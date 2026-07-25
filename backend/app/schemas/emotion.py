from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mode import ModeType


class SaveCard(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    copy_text: str = Field(serialization_alias="copy", validation_alias="copy")


class GiftCard(BaseModel):
    target: str
    reason: str


class OwnOption(BaseModel):
    option_type: str
    title: str
    bouquet_group_id: str
    bouquet_title: str
    reason: str
    generation_brief: str = ""
    should_generate_after_select: bool = True
    image_url: str = ""
    tags: list[str] = Field(default_factory=list)


class OwnCard(BaseModel):
    options: list[str] = Field(default_factory=list)
    candidates: list[OwnOption] = Field(default_factory=list)


class EmotionBuildRequest(BaseModel):
    result_id: str
    mode: ModeType
    voice_context: str = ""


class EmotionBuildResponse(BaseModel):
    save_card: SaveCard
    gift_card: GiftCard
    own_card: OwnCard


BudgetLevel = Literal["auto", "premium", "balanced", "budget"]


class RemakeSubstitute(BaseModel):
    source_flower: str
    replacement_flower: str
    reason: str


class RemakePlan(BaseModel):
    title: str
    budget_level: Literal["premium", "balanced", "budget"]
    seasonality_note: str
    preserve_points: list[str] = Field(default_factory=list)
    selected_flowers: list[str] = Field(default_factory=list)
    substitute_flowers: list[RemakeSubstitute] = Field(default_factory=list)
    materials_note: str = ""
    preview_prompt: str = ""


class EmotionRemakePreviewRequest(BaseModel):
    result_id: str
    mode: ModeType
    option_type: str
    voice_context: str = ""
    budget_level: BudgetLevel = "auto"
    season_month: int | None = Field(default=None, ge=1, le=12)


class EmotionRemakePreviewResponse(BaseModel):
    option_type: str
    option_title: str
    preview_image_url: str
    preview_status: Literal["generated", "fallback"]
    budget_level: Literal["premium", "balanced", "budget"]
    generation_brief: str = ""
    plan: RemakePlan
