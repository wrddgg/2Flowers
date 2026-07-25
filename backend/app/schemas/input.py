from typing import Literal

from pydantic import BaseModel, Field


class SelectionBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class AnalyzeInputRequest(BaseModel):
    content_id: str = Field(min_length=1)
    image_url: str = Field(min_length=1)
    selection_box: SelectionBox
    voice_text: str = Field(default="")


InputElementType = Literal["scene", "flower", "person", "portrait", "gift_context", "global"]
InterpretationPerspective = Literal["scene", "flower", "person", "portrait", "life", "global"]


class ElementCandidate(BaseModel):
    element_type: InputElementType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class InterpretationOption(BaseModel):
    option_id: str
    label: str
    perspective: InterpretationPerspective
    recommended_mode: "ModeType"
    semantic_result: "SemanticResult"
    explanation: str = ""
    alignment_axes: list[str] = Field(default_factory=list)
    recommended: bool = False


class AnalyzeInsights(BaseModel):
    mode_result: "ModeResult"
    semantic_result: "SemanticResult"
    detected_elements: list[ElementCandidate] = Field(default_factory=list)
    needs_user_choice: bool = False
    interpretation_options: list[InterpretationOption] = Field(default_factory=list)
    planner_summary: str = ""
    recommended_interpretation_id: str | None = None


class AnalyzeInputResponse(BaseModel):
    request_id: str
    mode_result: "ModeResult"
    semantic_result: "SemanticResult"
    detected_elements: list[ElementCandidate] = Field(default_factory=list)
    needs_user_choice: bool = False
    interpretation_options: list[InterpretationOption] = Field(default_factory=list)
    planner_summary: str = ""
    recommended_interpretation_id: str | None = None
    normalized_input: AnalyzeInputRequest


from app.schemas.mode import ModeResult
from app.schemas.mode import ModeType
from app.schemas.semantic import SemanticResult

AnalyzeInsights.model_rebuild()
AnalyzeInputResponse.model_rebuild()
