from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    demo,
    health,
    imports,
    incomes,
    notifications,
    obligations,
    planned,
    transactions,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(demo.router)
router.include_router(accounts.router)
router.include_router(transactions.router)
router.include_router(obligations.router)
router.include_router(notifications.router)
router.include_router(imports.router)
router.include_router(incomes.router)
router.include_router(planned.router)
