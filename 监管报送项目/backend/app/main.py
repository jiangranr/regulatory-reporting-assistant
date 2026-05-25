from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_catalog,
    routes_concepts,
    routes_documents,
    routes_extraction,
    routes_health,
    routes_reporting,
    routes_rule_cards,
    routes_tasks,
)
from app.core.config import get_settings
from app.core.database import init_db


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()
    api = FastAPI(title=settings.app_name, version="0.1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.include_router(routes_health.router)
    api.include_router(routes_documents.router)
    api.include_router(routes_reporting.router)
    api.include_router(routes_tasks.router)
    api.include_router(routes_catalog.router)
    api.include_router(routes_rule_cards.router)
    api.include_router(routes_concepts.router)
    api.include_router(routes_extraction.router)
    return api


app = create_app()


if __name__ == "__main__":
    init_db()
    print(f"{get_settings().app_name} backend ready")
