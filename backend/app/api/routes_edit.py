from fastapi import APIRouter, HTTPException

from app.repositories.bouquet_repository import get_bouquet_repository
from app.schemas.bouquet import EditBouquetRequest, EditBouquetResponse, FlowerInfo
from app.services.bouquet_editor import BouquetEditor


router = APIRouter(prefix="/api/bouquet", tags=["edit"])
bouquet_editor = BouquetEditor()


@router.get("/{result_id}/flowers/{flower_id}", response_model=FlowerInfo)
def get_flower_info(result_id: str, flower_id: str) -> FlowerInfo:
    bouquet_repository = get_bouquet_repository()
    result = bouquet_repository.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"未找到 result_id={result_id} 的花束结果")

    for flower in result.flowers:
        if flower.flower_id == flower_id:
            return flower
    raise HTTPException(status_code=404, detail=f"未找到 flower_id={flower_id} 的花朵信息")


@router.post("/edit", response_model=EditBouquetResponse)
def edit_bouquet(request: EditBouquetRequest) -> EditBouquetResponse:
    bouquet_repository = get_bouquet_repository()
    source = bouquet_repository.get_result(request.result_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"未找到 result_id={request.result_id} 的花束结果")

    result = bouquet_editor.edit(source, request)
    bouquet_repository.save_one(result)

    return EditBouquetResponse(
        new_result_id=result.result_id,
        image_url=result.image_url,
        summary=result.summary,
        result=result,
    )
