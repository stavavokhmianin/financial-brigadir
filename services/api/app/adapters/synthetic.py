"""SyntheticDataAdapter: демо-профиль → нормализованные записи для реестра.

Берётся только ``known`` — то, что известно на дату выгрузки. ``hidden_future``
и ``truth`` в хранилище не попадают, иначе возникнет утечка будущего.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from synthetic_generator import PROFILES, generate, list_profiles


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


class UnknownProfileError(LookupError):
    pass


class SyntheticDataAdapter:
    def profiles(self) -> list[dict[str, Any]]:
        return list_profiles()

    def is_available(self, profile_id: str) -> bool:
        return profile_id in PROFILES and PROFILES[profile_id].mvp

    def load(self, profile_id: str, seed: int) -> SyntheticBundle:
        if profile_id not in PROFILES:
            raise UnknownProfileError(profile_id)
        data = generate(profile_id, seed=seed)
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
        )
