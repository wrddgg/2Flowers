from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.mode import ModeType


class UserProgressState(BaseModel):
    current_page: str
    mode: ModeType | None = None
    content_id: str = ""
    request_id: str = ""
    result_id: str = ""
    result_ids: list[str] = Field(default_factory=list)
    tutorial_task_id: str = ""
    card_image_url: str = ""
    draft: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""


class UpsertUserProgressRequest(BaseModel):
    user_id: str = Field(min_length=1)
    state: UserProgressState


class UserProgressResponse(BaseModel):
    user_id: str
    state: UserProgressState | None = None


class SavedBouquetRecord(BaseModel):
    record_id: str
    result_id: str
    title: str
    summary: str = ""
    bouquet_image_url: str = ""
    card_image_url: str = ""
    source_context: str = ""
    scene_reason: str = ""
    tags: list[str] = Field(default_factory=list)
    scene_preset: str = ""
    style_preset: str = ""
    saved_at: str


class SaveBouquetRecordRequest(BaseModel):
    user_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    card_image_url: str = ""
    title: str = ""
    source_context: str = ""
    scene_reason: str = ""


class SaveBouquetRecordResponse(BaseModel):
    user_id: str
    record: SavedBouquetRecord


class UserSavedRecordsResponse(BaseModel):
    user_id: str
    records: list[SavedBouquetRecord] = Field(default_factory=list)
