"""SyntheticDataAdapter: демо-профиль → нормализованные записи для реестра.

Берётся только ``known`` — то, что известно на дату выгрузки. ``hidden_future``
и ``truth`` в реестр не попадают, иначе возникнет утечка будущего. Живой учебный
аккаунт (ADR-0007) получает скрытое будущее отдельно и раскрывает его по виртуальному
времени, не раньше.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from synthetic_generator import DEFAULT_HORIZON_DAYS, PROFILES, generate, list_profiles


@dataclass(frozen=True)
class SyntheticBundle:
    profile: dict[str, Any]
    as_of: datetime
    history_from: date
    accounts: list[dict[str, Any]]
    transactions: list[dict[str, Any]]
    reupload: list[dict[str, Any]]
    obligations: list[dict[str, Any]]
    incomes: list[dict[str, Any]]
    anomalies: list[str]
    # Скрытое будущее: только для живого аккаунта, в реестр — по виртуальному времени.
    hidden: list[dict[str, Any]]
    duplicate_external_ids: frozenset[str]


class UnknownProfileError(LookupError):
    pass


class SyntheticDataAdapter:
    def profiles(self) -> list[dict[str, Any]]:
        return list_profiles()

    def is_available(self, profile_id: str) -> bool:
        return profile_id in PROFILES and PROFILES[profile_id].mvp

    def load(
        self,
        profile_id: str,
        seed: int,
        horizon_days: int = DEFAULT_HORIZON_DAYS,
        unregistered: bool = False,
    ) -> SyntheticBundle:
        if profile_id not in PROFILES:
            raise UnknownProfileError(profile_id)
        data = generate(profile_id, seed=seed, horizon_days=horizon_days, unregistered=unregistered)
        known = data["known"]
        return SyntheticBundle(
            profile=data["profile"],
            as_of=datetime.fromisoformat(data["as_of"]),
            history_from=date.fromisoformat(data["history_from"]),
            accounts=known["accounts"],
            transactions=known["transactions"],
            reupload=known["reupload"],
            obligations=known["obligations"],
            incomes=known["incomes"],
            anomalies=[a["type"] for a in data["anomalies"]],
            hidden=data["hidden_future"]["transactions"],
            duplicate_external_ids=frozenset(data["truth"]["duplicate_external_ids"]),
        )
