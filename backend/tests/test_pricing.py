import pytest
from pydantic import ValidationError

from app.config import Settings
from app.formula_engine import FormulaError, evaluate_formula, validate_formula
from app.pricing import calculate
from app.schemas import CalculationRequest

CONFIG = Settings(_env_file=None)

def test_pricing_is_deterministic():
    req = CalculationRequest(**CONFIG.calculation_defaults)
    first = calculate(req, CONFIG)
    second = calculate(req, CONFIG)
    assert first == second
    assert first.physical_staff >= 1
    assert first.break_even_price_per_m2 > 0
    assert first.target_price_per_m2 > first.break_even_price_per_m2
    assert first.decision in {"BID", "BID WITH CONDITIONS", "NO BID"}

def test_low_price_is_no_bid():
    values = CONFIG.calculation_defaults | {"service_price_per_m2_month": 80}
    result = calculate(CalculationRequest(**values), CONFIG)
    assert result.decision == "NO BID"
    assert result.margin < 0

@pytest.mark.parametrize("field,value", [
    ("area_m2", 0),
    ("productivity_m2_per_shift", 0),
    ("monthly_hours_per_fte", 0),
    ("service_price_per_m2_month", -1),
    ("hourly_staff_cost", -1),
    ("vat_rate", 1),
    ("contract_months", 0),
    ("overhead_rate", float("nan")),
])
def test_invalid_calculation_inputs_are_rejected(field, value):
    with pytest.raises(ValidationError):
        CalculationRequest(**(CONFIG.calculation_defaults | {field: value}))

def test_target_margin_and_overhead_cannot_consume_all_revenue():
    values = CONFIG.calculation_defaults | {"overhead_rate": 0.9, "target_margin": 0.1}
    with pytest.raises(ValidationError, match=r"overhead_rate \+ target_margin"):
        CalculationRequest(**values)

def test_configured_sensitivity_deltas_are_used():
    configuration = Settings(_env_file=None, sensitivity_deltas="-0.1,0,0.1")
    result = calculate(CalculationRequest(**configuration.calculation_defaults), configuration)
    assert [item["delta"] for item in result.sensitivity] == [-0.1, 0.0, 0.1]


def test_sensitivity_reuses_custom_revenue_formula():
    configuration = Settings(_env_file=None, sensitivity_deltas="-0.1,0,0.1")
    req = CalculationRequest(**configuration.calculation_defaults)
    result = calculate(req, configuration, {"revenue_with_vat": "area_m2 * service_price_per_m2_month * 2"})
    assert result.sensitivity[1]["margin"] == pytest.approx(result.margin, abs=10 ** -configuration.margin_decimal_places)
    assert result.sensitivity[0]["margin"] < result.sensitivity[1]["margin"] < result.sensitivity[2]["margin"]


def test_sensitivity_scales_revenue_override_and_keeps_labor_override():
    configuration = Settings(_env_file=None, sensitivity_deltas="-0.1,0,0.1")
    req = CalculationRequest(**configuration.calculation_defaults)
    revenue = req.area_m2 * req.service_price_per_m2_month * 2
    result = calculate(req, configuration, labor_hours_override=40, revenue_with_vat_override=revenue)
    assert result.labor_hours_month == 40
    assert result.revenue_with_vat == round(revenue, configuration.currency_decimal_places)
    assert result.sensitivity[1]["margin"] == pytest.approx(result.margin, abs=10 ** -configuration.margin_decimal_places)
    assert result.sensitivity[0]["margin"] < result.sensitivity[1]["margin"] < result.sensitivity[2]["margin"]


@pytest.mark.parametrize("expression", ["1e309", "-1e309", "1e101"])
def test_nonfinite_or_oversized_constant_is_rejected(expression):
    with pytest.raises(FormulaError):
        validate_formula(expression, ())
    with pytest.raises(FormulaError):
        evaluate_formula(expression, (), {})


def test_nonfinite_variable_is_rejected():
    with pytest.raises(FormulaError):
        evaluate_formula("value", ("value",), {"value": float("inf")})
