from fastapi.testclient import TestClient
from app.main import app
from app.schemas import CalculationRequest

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

def test_upload_process_review_calculate_xlsx():
    from io import BytesIO
    from openpyxl import Workbook

    deal = client.post("/api/deals", params={"title": "E2E API fixture"}).json()
    deal_id = deal["id"]

    wb = Workbook()
    ws = wb.active
    ws.title = "ТЗ"
    ws.append(["Параметр", "Значение"])
    ws.append(["Общая площадь объекта", "1200 м²"])
    ws.append(["График уборки", "5/2"])
    ws.append(["Отсрочка оплаты", "30 календарных дней"])
    stream = BytesIO()
    wb.save(stream)

    upload = client.post(
        f"/api/deals/{deal_id}/documents",
        files={
            "files": (
                "requirements.xlsx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 200
    assert upload.json()["documents"][0]["filename"] == "requirements.xlsx"

    processed = client.post(f"/api/deals/{deal_id}/process")
    assert processed.status_code == 200
    extraction = processed.json()
    assert extraction["fields"]

    fields = client.get(f"/api/deals/{deal_id}/fields").json()
    area = next(field for field in fields if field["key"] == "area_m2")
    assert area["value"] == "1200"

    confirmed = client.patch(
        f"/api/fields/{area['id']}",
        json={"value": "1200", "confirmed": True},
    )
    assert confirmed.status_code == 200

    calc = client.post(
        f"/api/deals/{deal_id}/calculate",
        json=CalculationRequest().model_dump(),
    )
    assert calc.status_code == 200
    assert calc.json()["decision"] in {"BID", "BID WITH CONDITIONS", "NO BID"}
