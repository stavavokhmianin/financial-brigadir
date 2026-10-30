import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import router as v1_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.limits import IngressLimits

DESCRIPTION = """
Расчётный API «Финансового бригадира».

* Все деньги — целые копейки (`*_minor`, int64), валюта MVP — RUB.
* Время хранится в UTC, пользовательские даты считаются в таймзоне профиля.
* `user_id` определяется по токену сессии и никогда не передаётся клиентом.
* Прогнозы — модельные оценки, а не гарантированный остаток.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = FastAPI(
        title="Financial Brigadir API",
        version=__version__,
        description=DESCRIPTION,
        openapi_url="/api/v1/openapi.json",
        # Swagger UI грузит скрипты с CDN — в изолированном пилотном контуре он не нужен.
        docs_url="/api/v1/docs" if settings.app_mode == "demo" else None,
        redoc_url=None,
    )
    app.add_middleware(IngressLimits)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    app.state.settings = settings
    install_error_handlers(app)
    app.include_router(v1_router)
    return app


app = create_app()
