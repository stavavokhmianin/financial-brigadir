"""Reproducible planning arithmetic for TZ 17.3/26. No measured business metrics."""

import argparse
import json
from decimal import ROUND_CEILING, Decimal
from typing import Any

D = Decimal
DEFAULTS = {
    "conversion": D("0.03"),
    "family_share": D("0"),
    "plus_price": D("199"),
    "family_price": D("349"),
    "fixed_cost": D("150000"),
    "infrastructure": D("5000"),
    "acquisition_spend": D("0"),
    "cost_per_active": D("0.50"),
    "cost_per_payer": D("5"),
    "processing_rate": D("0.03"),
    "tax_rate": D("0.06"),
}


def calculate(
    *,
    mau: int = 20_000,
    conversion: Decimal = DEFAULTS["conversion"],
    family_share: Decimal = DEFAULTS["family_share"],
    plus_price: Decimal = DEFAULTS["plus_price"],
    family_price: Decimal = DEFAULTS["family_price"],
    fixed_cost: Decimal = DEFAULTS["fixed_cost"],
    infrastructure: Decimal = DEFAULTS["infrastructure"],
    acquisition_spend: Decimal = DEFAULTS["acquisition_spend"],
    cost_per_active: Decimal = DEFAULTS["cost_per_active"],
    cost_per_payer: Decimal = DEFAULTS["cost_per_payer"],
    processing_rate: Decimal = DEFAULTS["processing_rate"],
    tax_rate: Decimal = DEFAULTS["tax_rate"],
    churn: Decimal | None = None,
) -> dict[str, Any]:
    rates = (conversion, family_share, processing_rate, tax_rate)
    costs = (
        plus_price,
        family_price,
        fixed_cost,
        infrastructure,
        acquisition_spend,
        cost_per_active,
        cost_per_payer,
    )
    values = (*rates, *costs, *((churn,) if churn is not None else ()))
    if not all(value.is_finite() for value in values):
        raise ValueError("inputs must be finite")
    if mau < 0 or any(value < 0 for value in costs) or any(not 0 <= r <= 1 for r in rates):
        raise ValueError("negative count/cost or rate outside [0,1]")
    if processing_rate + tax_rate >= 1 or (churn is not None and not 0 < churn <= 1):
        raise ValueError("invalid fee/tax sum or churn")
    payers = D(mau) * conversion
    arppu = (1 - family_share) * plus_price + family_share * family_price
    revenue = payers * arppu
    processing = revenue * processing_rate
    taxes = revenue * tax_rate
    variable = D(mau) * cost_per_active + payers * cost_per_payer
    contribution = revenue - processing - taxes - variable
    fixed = fixed_cost + infrastructure + acquisition_spend
    margin_per_active = (
        conversion * (arppu * (1 - processing_rate - tax_rate) - cost_per_payer) - cost_per_active
    )
    breakeven = (
        int((fixed / margin_per_active).to_integral_value(rounding=ROUND_CEILING))
        if margin_per_active > 0
        else None
    )
    payer_margin = margin_per_active / conversion if conversion else None

    def money(value: Decimal) -> str:
        return str(value.quantize(D("0.01")))

    return {
        "currency": "RUB",
        "period": "month",
        "assumptions_only": True,
        "family_available_in_mvp": False,
        "mau": mau,
        "expected_payers": money(payers),
        "arppu": money(arppu),
        "mrr": money(revenue),
        "processing": money(processing),
        "taxes": money(taxes),
        "variable_cost": money(variable),
        "fixed_infra_acquisition": money(fixed),
        "contribution": money(contribution),
        "operating_result": money(contribution - fixed),
        "break_even_mau": breakeven,
        "ltv_stationary": money(payer_margin / churn)
        if churn and payer_margin is not None
        else None,
        "cac": None,
        "inputs": {
            "conversion": str(conversion),
            "family_share": str(family_share),
            "plus_price": str(plus_price),
            "family_price": str(family_price),
            "fixed_cost": str(fixed_cost),
            "infrastructure": str(infrastructure),
            "acquisition_spend": str(acquisition_spend),
            "cost_per_active": str(cost_per_active),
            "cost_per_payer": str(cost_per_payer),
            "processing_rate": str(processing_rate),
            "tax_rate": str(tax_rate),
            "churn": str(churn) if churn is not None else None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mau", type=int, default=20_000)
    for key, default in DEFAULTS.items():
        parser.add_argument("--" + key.replace("_", "-"), type=D, default=default)
    parser.add_argument("--churn", type=D)
    args = parser.parse_args()
    try:
        result = calculate(**vars(args))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
