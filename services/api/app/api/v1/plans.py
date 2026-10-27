from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, error_responses
from app.db.models import AuditEvent, User
from app.domain.enums import Plan
from app.modules.plans import account_count, lock_profile
from app.schemas.plans import PlanPreviewRequest, PlansOut, PlanSpec

router = APIRouter(prefix="/plans", tags=["plans"])


def _out(db: DbSession, user: User) -> PlansOut:
    count = account_count(db, user)
    return PlansOut(
        current_plan=user.plan,
        demo_preview=user.is_demo,
        account_count=count,
        existing_accounts_over_limit=user.plan == Plan.FREE and count > 1,
        plans=[
            PlanSpec(
                plan=Plan.FREE, max_new_accounts=1, max_horizon_days=30, advanced_scenarios=False
            ),
            PlanSpec(
                plan=Plan.PLUS, max_new_accounts=None, max_horizon_days=90, advanced_scenarios=True
            ),
        ],
    )


@router.get("", operation_id="getPlans", responses=error_responses(401))
def get_plans(user: CurrentUser, db: DbSession) -> PlansOut:
    return _out(db, user)


@router.patch("/demo-preview", operation_id="previewDemoPlan", responses=error_responses(401, 403))
def preview_plan(body: PlanPreviewRequest, user: CurrentUser, db: DbSession) -> PlansOut:
    user = lock_profile(db, user)
    if not user.is_demo:
        raise APIError(403, "demo_only", "Переключение доступно только в демо-профиле.")
    previous = user.plan
    user.plan = body.plan
    if previous != user.plan:
        db.add(
            AuditEvent(
                user_id=user.id,
                action="demo_plan_changed",
                meta={"from": previous.value, "to": body.plan.value},
            )
        )
    db.commit()
    return _out(db, user)
