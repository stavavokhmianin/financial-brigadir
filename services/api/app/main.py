import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import router as v1_router
from app.core.config import get_settings

DESCRIPTION = """
Расчётный API «Финансового бригадира».

* Все деньги — целые копейки (`*_minor`, int64), валюта MVP — RUB.
* Время хранится в UTC, пользовательские даты считаются в таймзоне профиля.
* `user_id` определяется по токену сессии и никогда не передаётся клиентом.
* Прогнозы — модельные оценки, а не гарантированный остаток.
"""


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = FastAPI(
        title="Financial Brigadir API",
        version=__version__,
        description=DESCRIPTION,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    app.include_router(v1_router)
    return app


app = create_app()
