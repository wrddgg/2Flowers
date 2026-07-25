import os
import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.image_edit import ImageEditRequest, ImageEditResponse
from app.services.image_edit_provider import ImageEditProvider


router = APIRouter(prefix="/api/image", tags=["image-edit"])
provider = ImageEditProvider()


@router.post("/edit", response_model=ImageEditResponse)
def edit_image(request: ImageEditRequest) -> ImageEditResponse:
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="请输入图片修改指令。")

    try:
        provider.validate_image_data_url(request.imageDataUrl)
        boxes = provider.normalize_boxes(
            request.boxes,
            max_boxes=int(os.getenv("WAN_IMAGE_EDIT_MAX_BBOXES", "2")),
        )
        result = provider.edit(
            image_data_url=request.imageDataUrl,
            prompt=prompt,
            boxes=boxes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ImageEditResponse(
        imageUrl=str(result["imageUrl"]),
        remoteImageUrl=str(result["remoteImageUrl"]) if result["remoteImageUrl"] else None,
        requestId=str(result["requestId"]) if result["requestId"] else None,
        traceId=uuid.uuid4().hex,
    )
