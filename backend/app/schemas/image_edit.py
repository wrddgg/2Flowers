from pydantic import BaseModel, Field


class ImageEditRequest(BaseModel):
    imageDataUrl: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    boxes: list[list[int]] = Field(default_factory=list)


class ImageEditResponse(BaseModel):
    ok: bool = True
    imageUrl: str
    remoteImageUrl: str | None = None
    requestId: str | None = None
    traceId: str
