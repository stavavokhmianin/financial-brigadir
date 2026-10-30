"""Обратная связь по тратам (ADR-0007): что уточнить, чтобы прогноз лучше понимал поведение."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core.errors import error_responses
from app.modules.feedback import build_queue
from app.schemas.transactions import FeedbackItemOut, FeedbackOut, TransactionOut

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get(
    "",
    operation_id="getFeedback",
    summary="Траты, которые стоит уточнить: дорогие, новые, недавние",
    responses=error_responses(401),
)
def get_feedback(user: CurrentUser, db: DbSession) -> FeedbackOut:
    queue = build_queue(db, user)
    return FeedbackOut(
        items=[
            FeedbackItemOut(
                transaction=TransactionOut.model_validate(item.transaction), reason=item.reason
            )
            for item in queue.items
        ],
        reducible_30d_minor=queue.reducible_minor,
        labeled=queue.labeled,
    )
