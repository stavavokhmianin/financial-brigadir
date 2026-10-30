from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    alerts,
    bank_mock,
    demo,
    feedback,
    forecasts,
    health,
    imports,
    incomes,
    live,
    meta,
    notifications,
    obligations,
    pilot,
    plans,
    privacy,
    transactions,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(meta.router)
router.include_router(pilot.router)
router.include_router(demo.router)
router.include_router(live.router)
router.include_router(accounts.router)
router.include_router(transactions.router)
router.include_router(feedback.router)
router.include_router(obligations.router)
router.include_router(notifications.router)
router.include_router(imports.router)
router.include_router(incomes.router)
router.include_router(forecasts.router)
router.include_router(alerts.router)
router.include_router(bank_mock.router)
router.include_router(privacy.router)
router.include_router(plans.router)
