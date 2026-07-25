from fastapi import APIRouter, HTTPException

from app.repositories.bouquet_repository import get_bouquet_repository
from app.repositories.content_repository import get_content_repository
from app.repositories.user_cache_repository import get_user_cache_repository
from app.schemas.emotion import (
    EmotionBuildRequest,
    EmotionBuildResponse,
    EmotionRemakePreviewRequest,
    EmotionRemakePreviewResponse,
)
from app.services.emotion_builder import EmotionBuilder
from app.services.user_cache_service import UserCacheService


router = APIRouter(prefix="/api/emotion", tags=["emotion"])
emotion_builder = EmotionBuilder()


@router.post("/build", response_model=EmotionBuildResponse)
def build_emotion(request: EmotionBuildRequest) -> EmotionBuildResponse:
    bouquet_repository = get_bouquet_repository()
    content_repository = get_content_repository()
    result = bouquet_repository.get_result(request.result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到 result_id={request.result_id} 的花束结果")
    response = emotion_builder.build(
        result=result,
        voice_context=request.voice_context,
        reference_candidates=content_repository.list_reference_candidates("flower"),
    )
    if request.user_id:
        UserCacheService(get_user_cache_repository()).save_progress(
            user_id=request.user_id,
            current_page="emotion",
            mode=request.mode,
            result_id=result.result_id,
            draft={"voice_context": request.voice_context},
        )
    return response


@router.post("/remake-preview", response_model=EmotionRemakePreviewResponse)
def build_emotion_remake_preview(request: EmotionRemakePreviewRequest) -> EmotionRemakePreviewResponse:
    bouquet_repository = get_bouquet_repository()
    content_repository = get_content_repository()
    result = bouquet_repository.get_result(request.result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到 result_id={request.result_id} 的花束结果")
    try:
        response = emotion_builder.build_remake_preview(
            result=result,
            request=request,
            reference_candidates=content_repository.list_reference_candidates("flower"),
        )
        if request.user_id:
            UserCacheService(get_user_cache_repository()).save_progress(
                user_id=request.user_id,
                current_page="remake-preview",
                mode=request.mode,
                result_id=result.result_id,
                draft={
                    "option_type": request.option_type,
                    "budget_level": request.budget_level,
                    "season_month": request.season_month,
                },
            )
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
