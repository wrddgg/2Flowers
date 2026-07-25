from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes_image_edit import router as image_edit_router
from app.api.routes_edit import router as edit_router
from app.api.routes_emotion import router as emotion_router
from app.api.routes_generate import router as generate_router
from app.api.routes_input import router as input_router
from app.api.routes_reference import router as reference_router
from app.api.routes_workflow import router as workflow_router
from app.config.env import load_environment


load_environment()

BASE_DIR = Path(__file__).resolve().parent
MOCK_ASSET_DIR = BASE_DIR / "data" / "mock_assets"
LIBRARY_ASSET_DIR = BASE_DIR.parent.parent / "images"
UPLOAD_DIR = BASE_DIR.parent.parent / "uploads"


def create_app() -> FastAPI:
    app = FastAPI(
        title="万物生花后端",
        description="为 Hackathon Demo 提供多模态生花链路的本地 mock 后端。",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(input_router)
    app.include_router(reference_router)
    app.include_router(generate_router)
    app.include_router(edit_router)
    app.include_router(image_edit_router)
    app.include_router(emotion_router)
    app.include_router(workflow_router)

    app.mount("/mock/assets", StaticFiles(directory=MOCK_ASSET_DIR), name="mock-assets")
    if LIBRARY_ASSET_DIR.exists():
        app.mount("/library/assets", StaticFiles(directory=LIBRARY_ASSET_DIR), name="library-assets")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    @app.get("/", tags=["system"])
    def root() -> dict[str, str]:
        return {
            "product": "万物生花",
            "service": "backend-demo",
            "docs": "/docs",
            "health": "ok",
        }

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
