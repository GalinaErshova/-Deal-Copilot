from io import BytesIO

from docx import Document as WordDocument
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def create_deal() -> int:
    response = client.post("/api/deals", params={"title": "API validation test"})
    assert response.status_code == 200
    return response.json()["id"]


def test_settings_endpoint_exposes_public_defaults_only():
    response = client.get("/api/settings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["calculation_defaults"]["area_m2"] == settings.default_area_m2
    assert payload["accepted_upload_extensions"] == settings.parsed_upload_extensions
    assert "mimo_api_key" not in payload


def test_calculation_requires_confirmed_area_and_matching_value():
    deal_id = create_deal()
    defaults = settings.calculation_defaults

    assert client.post(f"/api/deals/{deal_id}/calculate", json=defaults).status_code == 409

    response = client.post(f"/api/deals/{deal_id}/fields/area", json={"value": defaults["area_m2"]})
    assert response.status_code == 200
    field_id = response.json()["id"]
    assert client.patch(f"/api/fields/{field_id}", json={"value": defaults["area_m2"], "confirmed": True}).status_code == 200

    changed_area = defaults | {"area_m2": defaults["area_m2"] + 1}
    assert client.post(f"/api/deals/{deal_id}/calculate", json=changed_area).status_code == 409

    response = client.post(f"/api/deals/{deal_id}/calculate", json=defaults)
    assert response.status_code == 200
    assert response.json()["decision"] in {"BID", "BID WITH CONDITIONS", "NO BID"}


def test_calculation_rejects_invalid_numeric_input():
    deal_id = create_deal()
    defaults = settings.calculation_defaults
    response = client.post(f"/api/deals/{deal_id}/fields/area", json={"value": defaults["area_m2"]})
    field_id = response.json()["id"]
    client.patch(f"/api/fields/{field_id}", json={"value": defaults["area_m2"], "confirmed": True})

    invalid = defaults | {"productivity_m2_per_shift": 0}
    assert client.post(f"/api/deals/{deal_id}/calculate", json=invalid).status_code == 422


def test_upload_rejects_unsupported_extensions():
    deal_id = create_deal()
    response = client.post(
        f"/api/deals/{deal_id}/documents",
        files=[("files", ("payload.exe", b"not an accepted document", "application/octet-stream"))],
    )
    assert response.status_code == 415


def test_docx_upload_processing_completes_in_mock_mode_without_invented_fields():
    deal_id = create_deal()
    document = WordDocument()
    document.add_paragraph("Техническое задание на уборку офисного здания.")
    binary = BytesIO()
    document.save(binary)

    uploaded = client.post(
        f"/api/deals/{deal_id}/documents",
        files=[("files", ("requirements.docx", binary.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
    )
    assert uploaded.status_code == 200

    processed = client.post(f"/api/deals/{deal_id}/process")
    assert processed.status_code == 200
    assert processed.json()["fields"] == []
    assert client.get(f"/api/deals/{deal_id}/fields").json() == []

    pipeline = client.get(f"/api/deals/{deal_id}/pipeline").json()
    assert all(run["status"] == "success" for run in pipeline)


def test_uploaded_documents_remain_available_when_model_extraction_fails(monkeypatch):
    deal_id = create_deal()
    document = WordDocument()
    document.add_paragraph("Техническое задание на уборку офисного здания.")
    binary = BytesIO()
    document.save(binary)
    uploaded = client.post(
        f"/api/deals/{deal_id}/documents",
        files=[("files", ("requirements.docx", binary.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
    )
    assert uploaded.status_code == 200

    def fail_extraction(**_kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.main.gateway.structured", fail_extraction)
    processed = client.post(f"/api/deals/{deal_id}/process")

    assert processed.status_code == 502
    documents = client.get(f"/api/deals/{deal_id}/documents").json()
    assert len(documents) == 1
    assert documents[0]["status"] == "parsed"
    original = client.get(f"/api/documents/{documents[0]['id']}/original")
    assert original.status_code == 200
    parsed = client.get(f"/api/documents/{documents[0]['id']}/parsed").json()
    assert "Техническое задание" in parsed["blocks"][0]["text"]
    deals = client.get("/api/deals").json()
    assert next(deal for deal in deals if deal["id"] == deal_id)["document_count"] == 1
