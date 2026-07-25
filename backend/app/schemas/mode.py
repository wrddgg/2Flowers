from typing import Literal

from pydantic import BaseModel, Field


ModeType = Literal["scene", "flower", "life"]


class ModeResult(BaseModel):
    detected_mode: ModeType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
