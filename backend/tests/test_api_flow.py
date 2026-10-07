from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "model" in body

def test_create_deal_and_calculate():
    r = client.post("/api/deals", params={"title": "Integration test"})
    assert r.status_code == 200
    deal_id = r.json()["id"]

    calc = client.post(
        f"/api/deals/{deal_id}/calculate",
        json={
            "area_m2": 1200,
            "service_price_per_m2_month": 180,
            "productivity_m2_per_shift": 800,
            "monthly_hours_per_fte": 164,
            "hourly_staff_cost": 350,
            "replacement_coefficient": 1.12,
            "manager_monthly_cost": 8000,
            "materials_per_m2_month": 7,
            "equipment_per_m2_month": 2,
            "logistics_monthly": 3000,
            "overhead_rate": 0.08,
            "contingency_rate": 0.03,
            "target_margin": 0.15,
            "vat_rate": 0.22,
            "contract_months": 12
        },
    )
    assert calc.status_code == 200
    body = calc.json()
    assert body["calculation_id"] > 0
    assert body["fte"] > 0
    assert body["physical_staff"] >= 1
    assert body["decision"] in {"BID", "BID WITH CONDITIONS", "NO BID"}

    pipeline = client.get(f"/api/deals/{deal_id}/pipeline")
    assert pipeline.status_code == 200
    runs = pipeline.json()
    assert any(
        any(step["name"] == "deterministic_calculation" for step in run["steps"])
        for run in runs
    )
