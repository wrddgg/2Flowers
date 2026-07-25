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
