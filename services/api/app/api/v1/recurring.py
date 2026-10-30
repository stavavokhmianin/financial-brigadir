"""Регулярные платежи (FR-11, ADR-0007 этап B): найти, подтвердить, отклонить."""

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.api.effects import forecast_effect
from app.core.errors import error_responses, not_found
from app.modules import recurring
from app.schemas.obligations import ObligationOut
from app.schemas.recurring import RecurringCandidateOut, RecurringConfirmOut, RecurringOut
from forecast_core.recurring import RecurringCandidate

router = APIRouter(prefix="/recurring", tags=["recurring"])


def _out(candidate: RecurringCandidate) -> RecurringCandidateOut:
    return RecurringCandidateOut(
        id=candidate.key,
        title=candidate.title,
        account_id=candidate.account_id,
        category=candidate.category,
        period=candidate.period,
        anchor=candidate.anchor,
        amount_minor=candidate.amount_minor,
        amount_min_minor=candidate.amount_min_minor,
        amount_max_minor=candidate.amount_max_minor,
        occurrences=candidate.occurrences,
        last_date=candidate.last_day,
        next_date=candidate.next_day,
        confidence=candidate.confidence,
    )


@router.get(
    "",
    operation_id="listRecurringCandidates",
    summary="Похоже на регулярный платёж: повторения, которых нет в календаре",
    responses=error_responses(401),
)
def list_candidates(user: CurrentUser, db: DbSession) -> RecurringOut:
    return RecurringOut(items=[_out(c) for c in recurring.candidates(db, user)])


@router.post(
    "/{candidate_id}/confirm",
    operation_id="confirmRecurring",
    summary="Добавить в обязательные платежи: в календарь, из повседневных трат — убрать",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 404),
)
def confirm(candidate_id: str, user: CurrentUser, db: DbSession) -> RecurringConfirmOut:
    try:
        done = recurring.confirm(db, user, candidate_id)
    except recurring.CandidateNotFoundError:
        raise not_found("Кандидат") from None
    return RecurringConfirmOut(
        obligation=ObligationOut.model_validate(done.obligation),
        effect=forecast_effect(done.before, done.after),
    )


@router.post(
    "/{candidate_id}/reject",
    operation_id="rejectRecurring",
    summary="Это не регулярный платёж: больше не предлагать",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 404),
)
def reject(candidate_id: str, user: CurrentUser, db: DbSession) -> Response:
    try:
        recurring.reject(db, user, candidate_id)
    except recurring.CandidateNotFoundError:
        raise not_found("Кандидат") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
