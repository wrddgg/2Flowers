from fastapi import APIRouter, HTTPException

from app.repositories.content_repository import get_content_repository
from app.repositories.user_cache_repository import get_user_cache_repository
from app.schemas.input import AnalyzeInputRequest, AnalyzeInputResponse
from app.services.semantic_recognizer import get_semantic_recognizer
from app.services.user_cache_service import UserCacheService
from app.services.vision_semantic_extractor import VisionSemanticExtractor
from app.utils.text import new_id


router = APIRouter(prefix="/api/input", tags=["input"])


@router.post("/analyze", response_model=AnalyzeInputResponse)
def analyze_input(request: AnalyzeInputRequest) -> AnalyzeInputResponse:
    content_repository = get_content_repository()
    vision_semantic_extractor = VisionSemanticExtractor(content_repository)
    semantic_recognizer = get_semantic_recognizer()
    content_profile = content_repository.get_content_or_asset_profile(
        content_id=request.content_id,
        image_url=request.image_url,
    )
    if not content_profile:
        content_profile = vision_semantic_extractor.extract(
            image_url=request.image_url,
            voice_text=request.voice_text,
        )
    if not content_profile:
        raise HTTPException(status_code=404, detail=f"未找到 content_id={request.content_id} 的预置内容")

    try:
        insights = semantic_recognizer.recognize(request, content_profile)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    response = AnalyzeInputResponse(
        request_id=new_id("req"),
        mode_result=insights.mode_result,
        semantic_result=insights.semantic_result,
        detected_elements=insights.detected_elements,
        needs_user_choice=insights.needs_user_choice,
        interpretation_options=insights.interpretation_options,
        planner_summary=insights.planner_summary,
        recommended_interpretation_id=insights.recommended_interpretation_id,
        normalized_input=request,
    )
    if request.user_id:
        UserCacheService(get_user_cache_repository()).save_progress(
            user_id=request.user_id,
            current_page="analysis",
            mode=insights.mode_result.detected_mode,
            content_id=request.content_id,
            request_id=response.request_id,
            draft={
                "image_url": request.image_url,
                "voice_text": request.voice_text,
                "recommended_interpretation_id": insights.recommended_interpretation_id or "",
            },
        )
    return response
