from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.repositories.user_cache_repository import get_user_cache_repository
from app.schemas.workflow import GenerateCardRequest, GenerateTutorialRequest, WrappedResponse
from app.services.user_cache_service import UserCacheService
from app.services.workflow_service import (
    generate_card_payload,
    generate_tutorial_payload,
    tutorial_status_payload,
)


router = APIRouter(tags=["workflow"])


@router.post("/api/generate-tutorial", response_model=WrappedResponse)
def generate_tutorial(request: GenerateTutorialRequest) -> WrappedResponse:
    try:
        data = generate_tutorial_payload(
            flowers=request.flowers,
            bouquet_image=request.bouquet_image,
            with_images=request.with_images,
        )
    except ValueError as exc:
        return WrappedResponse(code=1, data=None, message=str(exc))
    except Exception as exc:
        return WrappedResponse(code=1, data=None, message=f"制作教程失败: {exc}")
    if request.user_id:
        UserCacheService(get_user_cache_repository()).save_progress(
            user_id=request.user_id,
            current_page="tutorial",
            tutorial_task_id=str(data.get("task_id") or ""),
            draft={
                "flowers": list(request.flowers),
                "bouquet_image": request.bouquet_image,
                "with_images": request.with_images,
            },
        )
    return WrappedResponse(data=data)


@router.get("/api/tutorial-status", response_model=WrappedResponse)
def tutorial_status(task_id: str = Query(..., min_length=1)) -> WrappedResponse:
    data = tutorial_status_payload(task_id)
    if not data:
        return WrappedResponse(code=404, data=None, message="任务不存在或已过期")
    return WrappedResponse(data=data)


@router.post("/api/generate-card", response_model=WrappedResponse)
def generate_card(request: GenerateCardRequest) -> WrappedResponse:
    try:
        data = generate_card_payload(
            source=request.source or "",
            before=request.before,
            after=request.after,
            title=request.title,
            source_context=request.source_context or "",
            scene_reason=request.scene_reason or "",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成分享卡片失败: {exc}") from exc
    if request.user_id:
        UserCacheService(get_user_cache_repository()).save_progress(
            user_id=request.user_id,
            current_page="card",
            result_id=request.result_id,
            card_image_url=str(data.get("card_image") or ""),
            draft={
                "title": request.title or "",
                "source_context": request.source_context or "",
                "scene_reason": request.scene_reason or "",
            },
        )
    return WrappedResponse(data=data)
