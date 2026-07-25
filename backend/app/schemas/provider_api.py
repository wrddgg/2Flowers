from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.bouquet import GenerationVariantPlan, ReferenceUsage
from app.schemas.input import SelectionBox
from app.schemas.mode import ModeResult, ModeType
from app.schemas.semantic import SemanticResult


ProviderModeType = Literal["scene", "flower", "life"]
ImageAspectRatio = Literal["1:1", "4:5", "3:4", "16:9", "9:16"]


class ProviderTagTaxonomy(BaseModel):
    modes: list[ProviderModeType] = Field(default_factory=lambda: ["scene", "flower", "life"])
    element_types: list[str] = Field(default_factory=list)
    scene_tags: list[str] = Field(default_factory=list)
    emotion_tags: list[str] = Field(default_factory=list)
    visual_tags: list[str] = Field(default_factory=list)
    relation_tags: list[str] = Field(default_factory=list)
    use_intents: list[str] = Field(default_factory=list)


class SemanticRecognitionApiRequest(BaseModel):
    request_id: str
    image_url: str
    selection_box: SelectionBox
    voice_text: str = ""
    allowed_modes: list[ProviderModeType] = Field(default_factory=lambda: ["scene", "flower", "life"])
    candidate_tags: list[str] = Field(default_factory=list)
    taxonomy: ProviderTagTaxonomy = Field(default_factory=ProviderTagTaxonomy)
    return_raw_caption: bool = True


class SemanticRecognitionApiResponse(BaseModel):
    request_id: str
    provider_name: str
    model_name: str
    mode_result: ModeResult
    semantic_result: SemanticResult
    raw_caption: str = ""
    raw_labels: list[str] = Field(default_factory=list)
    latency_ms: int | None = None


class ProviderReferenceInput(BaseModel):
    reference_id: str
    title: str
    cover_url: str
    mode: ModeType
    score: int | None = None
    matched_tags: list[str] = Field(default_factory=list)
    flower_types: list[str] = Field(default_factory=list)
    visual_tags: list[str] = Field(default_factory=list)
    emotion_tags: list[str] = Field(default_factory=list)
    scene_tags: list[str] = Field(default_factory=list)
    package_style: list[str] = Field(default_factory=list)
    reference_used: ReferenceUsage | None = None


class ImageGenerationConstraints(BaseModel):
    output_count: int = Field(default=3, ge=1, le=4)
    aspect_ratio: ImageAspectRatio = "3:4"
    preserve_reference_strength: Literal["none", "light", "strong"] = "light"
    allow_text_overlay: bool = False
    return_revised_prompt: bool = True


class ImageGenerationApiRequest(BaseModel):
    request_id: str
    mode: ModeType
    semantic_result: SemanticResult
    reference_strategy: Literal["none", "light", "strong"] = "light"
    creative_mode: Literal["commercial", "expressive", "mixed"] = "mixed"
    generation_goals: list[str] = Field(default_factory=list)
    selected_interpretation_label: str | None = None
    selected_references: list[ProviderReferenceInput] = Field(default_factory=list)
    variant_plans: list[GenerationVariantPlan] = Field(default_factory=list)
    generation_constraints: ImageGenerationConstraints = Field(default_factory=ImageGenerationConstraints)
    style_prompt: str = ""
    negative_prompt: str = ""


class GeneratedBouquetImage(BaseModel):
    image_url: str
    prompt_summary: str = ""
    revised_prompt: str = ""
    seed: str | None = None
    provider_metadata: dict[str, str] = Field(default_factory=dict)


class ImageGenerationApiResponse(BaseModel):
    request_id: str
    provider_name: str
    model_name: str
    images: list[GeneratedBouquetImage] = Field(default_factory=list)
    latency_ms: int | None = None
