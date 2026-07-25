from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.mode import ModeType
from app.schemas.reference import ReferenceStrategy
from app.schemas.semantic import SemanticResult


EditAction = Literal["delete_flower", "replace_region", "repaint_region", "voice_adjust"]
CreativeMode = Literal["commercial", "expressive", "mixed"]
GenerationFocus = Literal["atmosphere", "color", "persona", "material", "premium", "coherence", "symbolism"]
CompositionStyle = Literal["mass", "layered", "airy", "focal"]
MaterialRichness = Literal["single", "limited", "mixed"]
ColorStrategy = Literal["single_tone", "dual_tone", "accent"]
BouquetDensity = Literal["dense", "medium", "airy"]
ScenePreset = Literal["礼宾赠礼", "庆祝纪念", "恋人赠礼", "日常居家"]
StylePreset = Literal["东方留白", "法式浪漫", "清新自然", "现代艺术"]
FlowerMaterialCategory = Literal["main", "transition", "accent", "linear"]


class FlowerMaterialPlan(BaseModel):
    category: FlowerMaterialCategory
    category_label: str
    species: list[str] = Field(default_factory=list)
    stem_count_range: list[int] = Field(default_factory=lambda: [1, 2], min_length=2, max_length=2)
    strategy: str = ""


class FlowerInfo(BaseModel):
    flower_id: str
    name: str
    type: str
    meaning: str
    role: str
    category: FlowerMaterialCategory = "main"
    category_label: str = "主花材"
    point: list[float] = Field(default_factory=list, min_length=2, max_length=2)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    placement_zone: str = ""
    label_side: str = ""
    source_hint: str = ""
    detection_origin: str = "planned_fallback"
    visible_reason: str = ""


class ReferenceUsage(BaseModel):
    reference_id: str
    strength: ReferenceStrategy
    title: str = ""
    cover_url: str = ""
    reason: str | None = None
    matched_tags: list[str] = Field(default_factory=list)
    score: int | None = None
    preferred_display_mode: str = "image_only_modal"
    show_title_by_default: bool = False
    show_reason_by_default: bool = False


class BouquetResult(BaseModel):
    result_id: str
    title: str
    image_url: str
    tags: list[str] = Field(default_factory=list)
    summary: str
    generation_focus: str = ""
    reference_used: list[ReferenceUsage] = Field(default_factory=list)
    planned_flowers: list[FlowerMaterialPlan] = Field(default_factory=list)
    recognized_flowers: list[FlowerInfo] = Field(default_factory=list)
    flowers: list[FlowerInfo] = Field(default_factory=list)
    flower_recognition_status: str = "planned_fallback"
    flower_recognition_summary: str = ""
    scene_preset: ScenePreset | None = None
    style_preset: StylePreset | None = None
    explanation: str = ""
    fit_scenes: list[str] = Field(default_factory=list)
    usage_goal: str = ""
    reality_advice: str = ""


class GenerationVariantPlan(BaseModel):
    variant_id: str
    title: str
    focus: GenerationFocus
    prompt_directive: str
    reference_strategy: ReferenceStrategy = "light"
    composition_style: CompositionStyle = "mass"
    material_richness: MaterialRichness = "limited"
    species_count_cap: int = Field(default=3, ge=1, le=6)
    dominant_flower_ratio: float = Field(default=0.7, ge=0.4, le=1.0)
    color_strategy: ColorStrategy = "dual_tone"
    bouquet_density: BouquetDensity = "medium"
    scene_preset: ScenePreset | None = None
    style_preset: StylePreset | None = None
    explanation: str = ""
    fit_scenes: list[str] = Field(default_factory=list)
    usage_goal: str = ""
    reality_advice: str = ""


class GenerateBouquetRequest(BaseModel):
    user_id: str = ""
    mode: ModeType
    semantic_result: SemanticResult
    reference_strategy: ReferenceStrategy = "light"
    selected_reference_ids: list[str] = Field(default_factory=list)
    creative_mode: CreativeMode = "mixed"
    generation_goals: list[str] = Field(default_factory=list)
    selected_interpretation_id: str | None = None
    selected_interpretation_label: str | None = None
    selected_scene: ScenePreset | None = None
    selected_style: StylePreset | None = None
    variant_plans: list[GenerationVariantPlan] = Field(default_factory=list)


class GenerateBouquetResponse(BaseModel):
    results: list[BouquetResult]
    plan_used: list[GenerationVariantPlan] = Field(default_factory=list)


class EditTarget(BaseModel):
    flower_id: str | None = None
    region_hint: str | None = None


class EditBouquetRequest(BaseModel):
    user_id: str = ""
    result_id: str
    action: EditAction
    target: EditTarget = Field(default_factory=EditTarget)
    instruction: str = ""


class EditBouquetResponse(BaseModel):
    new_result_id: str
    image_url: str
    summary: str
    result: BouquetResult
