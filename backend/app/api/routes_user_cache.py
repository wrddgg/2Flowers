from fastapi import APIRouter, HTTPException, Query

from app.repositories.bouquet_repository import get_bouquet_repository
from app.repositories.user_cache_repository import get_user_cache_repository
from app.schemas.user_cache import (
    SaveBouquetRecordRequest,
    SaveBouquetRecordResponse,
    UpsertUserProgressRequest,
    UserProgressResponse,
    UserSavedRecordsResponse,
)
from app.services.user_cache_service import UserCacheService


router = APIRouter(prefix="/api/user-cache", tags=["user-cache"])


@router.post("/progress", response_model=UserProgressResponse)
def upsert_user_progress(request: UpsertUserProgressRequest) -> UserProgressResponse:
    repository = get_user_cache_repository()
    service = UserCacheService(repository)
    state = service.save_progress(
        user_id=request.user_id,
        current_page=request.state.current_page,
        mode=request.state.mode,
        content_id=request.state.content_id,
        request_id=request.state.request_id,
        result_id=request.state.result_id,
        result_ids=request.state.result_ids,
        tutorial_task_id=request.state.tutorial_task_id,
        card_image_url=request.state.card_image_url,
        draft=request.state.draft,
    )
    return UserProgressResponse(user_id=request.user_id, state=state)


@router.get("/progress", response_model=UserProgressResponse)
def get_user_progress(user_id: str = Query(..., min_length=1)) -> UserProgressResponse:
    repository = get_user_cache_repository()
    return UserProgressResponse(user_id=user_id, state=repository.get_progress(user_id))


@router.post("/records", response_model=SaveBouquetRecordResponse)
def save_bouquet_record(request: SaveBouquetRecordRequest) -> SaveBouquetRecordResponse:
    bouquet_repository = get_bouquet_repository()
    cache_repository = get_user_cache_repository()
    service = UserCacheService(cache_repository)

    result = bouquet_repository.get_result(request.result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到 result_id={request.result_id} 的花束结果")

    record = service.build_saved_record(
        result=result,
        card_image_url=request.card_image_url,
        title=request.title,
        source_context=request.source_context,
        scene_reason=request.scene_reason,
    )
    cache_repository.save_record(request.user_id, record)
    service.save_progress(
        user_id=request.user_id,
        current_page="records",
        mode=None,
        result_id=result.result_id,
        card_image_url=request.card_image_url,
        draft={"saved_record_id": record.record_id},
    )
    return SaveBouquetRecordResponse(user_id=request.user_id, record=record)


@router.get("/records", response_model=UserSavedRecordsResponse)
def list_saved_bouquet_records(user_id: str = Query(..., min_length=1)) -> UserSavedRecordsResponse:
    repository = get_user_cache_repository()
    return UserSavedRecordsResponse(user_id=user_id, records=repository.list_records(user_id))
