from app.pricing import calculate
from app.schemas import CalculationRequest

def test_pricing_is_deterministic():
    req = CalculationRequest()
    first = calculate(req)
    second = calculate(req)
    assert first == second
    assert first.physical_staff >= 1
    assert first.break_even_price_per_m2 > 0
    assert first.target_price_per_m2 > first.break_even_price_per_m2
    assert first.decision in {"BID", "BID WITH CONDITIONS", "NO BID"}

def test_low_price_is_no_bid():
    result = calculate(CalculationRequest(service_price_per_m2_month=80))
    assert result.decision == "NO BID"
    assert result.margin < 0
