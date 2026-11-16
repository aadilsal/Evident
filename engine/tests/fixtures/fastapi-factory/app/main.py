from fastapi import APIRouter, FastAPI

from app.routes.items import router as items_router


def _build_api_router() -> APIRouter:
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(items_router, prefix="/items")
    return api_v1


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(_build_api_router())

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
