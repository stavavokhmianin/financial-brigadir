from typing import Literal

from pydantic import ConfigDict

from app.domain.enums import Plan
from app.schemas.common import APIModel


class PlanSpec(APIModel):
    plan: Plan
    max_new_accounts: int | None
    max_horizon_days: int
    advanced_scenarios: bool


class PlansOut(APIModel):
    current_plan: Plan
    demo_preview: bool
    billing_enabled: Literal[False] = False
    account_count: int
    existing_accounts_over_limit: bool
    plans: list[PlanSpec]


class PlanPreviewRequest(APIModel):
    model_config = ConfigDict(extra="forbid")
    plan: Plan
