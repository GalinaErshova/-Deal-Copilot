import json
from pathlib import Path
from app.pricing import calculate
from app.schemas import CalculationRequest

def test_golden_pricing_case_001():
    path = Path(__file__).parent / "golden" / "pricing_case_001.json"
    case = json.loads(path.read_text(encoding="utf-8"))
    result = calculate(CalculationRequest(**case["input"]))
    expected = case["expected"]

    assert result.labor_hours_month == expected["labor_hours_month"]
    assert result.fte == expected["fte"]
    assert result.physical_staff == expected["physical_staff"]

    # Guardrails for regression: economics must remain internally consistent.
    assert result.revenue_net > 0
    assert result.full_cost > 0
    assert result.break_even_price_per_m2 > 0
    assert result.target_price_per_m2 > result.break_even_price_per_m2
