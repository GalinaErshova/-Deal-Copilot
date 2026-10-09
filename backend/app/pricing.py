from __future__ import annotations

import math

from .config import settings
from .formula_engine import DEFAULT_FORMULAS, FORMULA_BY_KEY, evaluate_formula
from .schemas import CalculationRequest, CalculationResult


def calculate(req: CalculationRequest, configuration=settings, formula_expressions: dict[str, str] | None = None) -> CalculationResult:
    expressions = {**DEFAULT_FORMULAS, **(formula_expressions or {})}
    values = {
        "area_m2": req.area_m2,
        "productivity_m2_per_shift": req.productivity_m2_per_shift,
        "hours_per_shift": configuration.hours_per_shift,
        "working_days_per_month": configuration.working_days_per_month,
        "service_price_per_m2_month": req.service_price_per_m2_month,
        "vat_rate": req.vat_rate,
        "hourly_staff_cost": req.hourly_staff_cost,
        "replacement_coefficient": req.replacement_coefficient,
        "materials_per_m2_month": req.materials_per_m2_month,
        "equipment_per_m2_month": req.equipment_per_m2_month,
        "manager_monthly_cost": req.manager_monthly_cost,
        "logistics_monthly": req.logistics_monthly,
        "contingency_rate": req.contingency_rate,
        "overhead_rate": req.overhead_rate,
        "target_margin": req.target_margin,
    }
    formula = lambda key: evaluate_formula(expressions[key], FORMULA_BY_KEY[key].variables, values)
    labor_hours_month = formula("labor_hours_month")
    fte = labor_hours_month / req.monthly_hours_per_fte
    physical_staff = max(
        configuration.minimum_physical_staff,
        math.ceil(fte * req.replacement_coefficient),
    )

    values["labor_hours_month"] = labor_hours_month
    values["revenue_with_vat"] = formula("revenue_with_vat")
    values["revenue_net"] = formula("revenue_net")
    values["labor_cost"] = formula("labor_cost")
    values["materials_cost"] = formula("materials_cost")
    values["equipment_cost"] = formula("equipment_cost")
    values["direct_cost"] = formula("direct_cost")
    values["contingency_cost"] = formula("contingency_cost")
    values["overhead_cost"] = formula("overhead_cost")
    values["full_cost"] = formula("full_cost")
    values["profit"] = formula("profit")
    values["margin"] = formula("margin")
    values["break_even_price_per_m2"] = formula("break_even_price_per_m2")
    values["target_price_per_m2"] = formula("target_price_per_m2")

    revenue_with_vat = values["revenue_with_vat"]
    revenue_net = values["revenue_net"]
    direct_cost = values["direct_cost"]
    full_cost = values["full_cost"]
    profit = values["profit"]
    margin = values["margin"]
    break_even_price = values["break_even_price_per_m2"]
    target_price = values["target_price_per_m2"]

    # MVP-3 deterministic BID rules.
    conditions: list[str] = []
    if margin < configuration.no_bid_margin_threshold:
        decision = "NO BID"
        conditions.append("Текущий тариф ниже экономически допустимого уровня")
    elif margin < req.target_margin:
        decision = "BID WITH CONDITIONS"
        minimum_price = f"{target_price:.{configuration.condition_price_decimal_places}f} {configuration.condition_price_unit}"
        conditions.append(f"Поднять тариф минимум до {minimum_price} или снизить затраты")
    else:
        decision = "BID"

    sensitivity = []
    for delta in configuration.parsed_sensitivity_deltas:
        price = req.service_price_per_m2_month * (1 + delta)
        net = evaluate_formula(expressions["revenue_net"], FORMULA_BY_KEY["revenue_net"].variables,
                               {**values, "revenue_with_vat": req.area_m2 * price})
        oh = evaluate_formula(expressions["overhead_cost"], FORMULA_BY_KEY["overhead_cost"].variables,
                              {**values, "revenue_net": net})
        scenario_values = {
            **values,
            "revenue_net": net,
            "overhead_cost": oh,
            "full_cost": evaluate_formula(
                expressions["full_cost"],
                FORMULA_BY_KEY["full_cost"].variables,
                {**values, "overhead_cost": oh},
            ),
        }
        p = evaluate_formula(
            expressions["profit"],
            FORMULA_BY_KEY["profit"].variables,
            scenario_values,
        )
        sensitivity_margin = evaluate_formula(expressions["margin"], FORMULA_BY_KEY["margin"].variables,
                                              {**scenario_values, "profit": p, "revenue_net": net})
        sensitivity.append({"delta":delta,"price":price,"margin":sensitivity_margin})

    return CalculationResult(
        labor_hours_month=round(labor_hours_month,configuration.labor_hours_decimal_places),
        fte=round(fte,configuration.fte_decimal_places),
        physical_staff=physical_staff,
        revenue_with_vat=round(revenue_with_vat,configuration.currency_decimal_places),
        revenue_net=round(revenue_net,configuration.currency_decimal_places),
        direct_cost=round(direct_cost,configuration.currency_decimal_places),
        full_cost=round(full_cost,configuration.currency_decimal_places),
        profit=round(profit,configuration.currency_decimal_places),
        margin=round(margin,configuration.margin_decimal_places),
        break_even_price_per_m2=round(break_even_price,configuration.currency_decimal_places),
        target_price_per_m2=round(target_price,configuration.currency_decimal_places),
        decision=decision,
        conditions=conditions,
        sensitivity=sensitivity,
    )
