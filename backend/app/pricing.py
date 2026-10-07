from __future__ import annotations
import math
from .schemas import CalculationRequest, CalculationResult

def calculate(req: CalculationRequest) -> CalculationResult:
    # MVP-1: labor model. One regular-cleaning operation for the demo.
    shifts_per_month = 22.0
    labor_hours_month = req.area_m2 / req.productivity_m2_per_shift * 8.0 * shifts_per_month
    fte = labor_hours_month / req.monthly_hours_per_fte
    physical_staff = max(1, math.ceil(fte * req.replacement_coefficient))

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
    margin = profit / revenue_net if revenue_net else 0.0

    fixed_plus_direct = direct_cost + contingency
    net_share_break_even = max(0.01, 1 - req.overhead_rate)
    break_even_net = fixed_plus_direct / net_share_break_even
    break_even_price = break_even_net * (1 + req.vat_rate) / req.area_m2

    net_share_target = max(0.01, 1 - req.overhead_rate - req.target_margin)
    target_net = fixed_plus_direct / net_share_target
    target_price = target_net * (1 + req.vat_rate) / req.area_m2

    # MVP-3 deterministic BID rules.
    conditions: list[str] = []
    if margin < 0:
        decision = "NO BID"
        conditions.append("Текущий тариф ниже экономически допустимого уровня")
    elif margin < req.target_margin:
        decision = "BID WITH CONDITIONS"
        conditions.append(f"Поднять тариф минимум до {target_price:.1f} ₽/м²/мес или снизить затраты")
    else:
        decision = "BID"

    sensitivity = []
    for delta in (-0.20,-0.10,-0.05,0.0,0.05,0.10,0.20):
        price = req.service_price_per_m2_month * (1 + delta)
        net = req.area_m2 * price / (1 + req.vat_rate)
        oh = net * req.overhead_rate
        p = net - (direct_cost + contingency + oh)
        sensitivity.append({"delta":delta,"price":price,"margin":p/net if net else 0.0})

    return CalculationResult(
        labor_hours_month=round(labor_hours_month,2),
        fte=round(fte,2),
        physical_staff=physical_staff,
        revenue_with_vat=round(revenue_with_vat,2),
        revenue_net=round(revenue_net,2),
        direct_cost=round(direct_cost,2),
        full_cost=round(full_cost,2),
        profit=round(profit,2),
        margin=round(margin,4),
        break_even_price_per_m2=round(break_even_price,2),
        target_price_per_m2=round(target_price,2),
        decision=decision,
        conditions=conditions,
        sensitivity=sensitivity,
    )
