from fastapi import APIRouter, HTTPException

from app.repositories.bouquet_repository import get_bouquet_repository
from app.repositories.content_repository import get_content_repository
from app.schemas.bouquet import GenerateBouquetRequest, GenerateBouquetResponse
from app.services.image_generation_provider import get_image_generation_provider


router = APIRouter(prefix="/api/bouquet", tags=["bouquet"])


@router.post("/generate", response_model=GenerateBouquetResponse)
def generate_bouquet(request: GenerateBouquetRequest) -> GenerateBouquetResponse:
    content_repository = get_content_repository()
    bouquet_repository = get_bouquet_repository()
    image_generation_provider = get_image_generation_provider()

    templates = content_repository.list_bouquet_templates(request.mode)
    reference_map = content_repository.get_reference_map()
    try:
        results, plan_used = image_generation_provider.generate(request, templates, reference_map)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    bouquet_repository.save_many(results)

    return GenerateBouquetResponse(results=results, plan_used=plan_used)
