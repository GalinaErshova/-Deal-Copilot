from __future__ import annotations

import math

from .config import settings
from .schemas import CalculationRequest, CalculationResult


def calculate(req: CalculationRequest, configuration=settings) -> CalculationResult:
    # MVP-1: labor model. One regular-cleaning operation for the demo.
    labor_hours_month = (
        req.area_m2
        / req.productivity_m2_per_shift
        * configuration.hours_per_shift
        * configuration.working_days_per_month
    )
    fte = labor_hours_month / req.monthly_hours_per_fte
    physical_staff = max(
        configuration.minimum_physical_staff,
        math.ceil(fte * req.replacement_coefficient),
    )

    # MVP-2: deterministic economics.
    revenue_with_vat = req.area_m2 * req.service_price_per_m2_month
    revenue_net = revenue_with_vat / (1 + req.vat_rate)
    labor_cost = labor_hours_month * req.hourly_staff_cost * req.replacement_coefficient
    materials = req.area_m2 * req.materials_per_m2_month
    equipment = req.area_m2 * req.equipment_per_m2_month
    direct_cost = labor_cost + req.manager_monthly_cost + materials + equipment + req.logistics_monthly
    contingency = direct_cost * req.contingency_rate
    overhead = revenue_net * req.overhead_rate
    full_cost = direct_cost + contingency + overhead
    profit = revenue_net - full_cost
    margin = profit / revenue_net

    fixed_plus_direct = direct_cost + contingency
    net_share_break_even = 1 - req.overhead_rate
    break_even_net = fixed_plus_direct / net_share_break_even
    break_even_price = break_even_net * (1 + req.vat_rate) / req.area_m2

    net_share_target = 1 - req.overhead_rate - req.target_margin
    target_net = fixed_plus_direct / net_share_target
    target_price = target_net * (1 + req.vat_rate) / req.area_m2

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
        net = req.area_m2 * price / (1 + req.vat_rate)
        oh = net * req.overhead_rate
        p = net - (direct_cost + contingency + oh)
        sensitivity.append({"delta":delta,"price":price,"margin":p/net})

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
