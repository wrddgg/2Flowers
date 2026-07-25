from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.user_cache_repository import UserCacheRepository
from app.schemas.bouquet import BouquetResult
from app.schemas.mode import ModeType
from app.schemas.user_cache import SavedBouquetRecord, UserProgressState
from app.utils.text import new_id


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserCacheService:
    def __init__(self, repository: UserCacheRepository) -> None:
        self.repository = repository

    def save_progress(
        self,
        *,
        user_id: str,
        current_page: str,
        mode: ModeType | None = None,
        content_id: str = "",
        request_id: str = "",
        result_id: str = "",
        result_ids: list[str] | None = None,
        tutorial_task_id: str = "",
        card_image_url: str = "",
        draft: dict[str, Any] | None = None,
    ) -> UserProgressState:
        previous = self.repository.get_progress(user_id)
        state = UserProgressState(
            current_page=current_page,
            mode=mode or (previous.mode if previous else None),
            content_id=content_id or (previous.content_id if previous else ""),
            request_id=request_id or (previous.request_id if previous else ""),
            result_id=result_id or (previous.result_id if previous else ""),
            result_ids=list(result_ids or (previous.result_ids if previous else [])),
            tutorial_task_id=tutorial_task_id or (previous.tutorial_task_id if previous else ""),
            card_image_url=card_image_url or (previous.card_image_url if previous else ""),
            draft=dict(draft or (previous.draft if previous else {})),
            updated_at=iso_now(),
        )
        return self.repository.save_progress(user_id, state)

    def build_saved_record(
        self,
        *,
        result: BouquetResult,
        card_image_url: str = "",
        title: str = "",
        source_context: str = "",
        scene_reason: str = "",
    ) -> SavedBouquetRecord:
        return SavedBouquetRecord(
            record_id=new_id("saved"),
            result_id=result.result_id,
            title=title or result.title,
            summary=result.summary,
            bouquet_image_url=result.image_url,
            card_image_url=card_image_url,
            source_context=source_context,
            scene_reason=scene_reason,
            tags=list(result.tags),
            scene_preset=result.scene_preset or "",
            style_preset=result.style_preset or "",
            saved_at=iso_now(),
        )
