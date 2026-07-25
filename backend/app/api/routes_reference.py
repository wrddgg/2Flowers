from fastapi import APIRouter

from app.repositories.content_repository import get_content_repository
from app.schemas.reference import ReferenceSearchRequest, ReferenceSearchResponse
from app.services.reference_retriever import ReferenceRetriever


router = APIRouter(prefix="/api/reference", tags=["reference"])
reference_retriever = ReferenceRetriever()


@router.post("/search", response_model=ReferenceSearchResponse)
def search_reference(request: ReferenceSearchRequest) -> ReferenceSearchResponse:
    repository = get_content_repository()
    references = repository.list_reference_candidates(request.mode)
    excluded_reference_ids = list(request.exclude_reference_ids)
    if request.exclude_source_reference and request.source_asset_id:
        excluded_reference_ids.append(request.source_asset_id)
    results = reference_retriever.search(
        references=references,
        mode=request.mode,
        semantic_result=request.semantic_result,
        semantic_tags=request.semantic_tags,
        limit=request.limit,
        excluded_reference_ids=excluded_reference_ids,
    )
    return ReferenceSearchResponse(references=results)
