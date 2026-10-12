"""Проверки исправлений по замечаниям 2, 3, 4 и 6 код-ревью от 12 октября 2026 года."""

import io
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.db import Base, get_db
from app.field_values import normalize_field_value
from app.main import app
from app.model_gateway import OllamaProvider

ADMIN_TOKEN = "t" * 40


@pytest.fixture
def client(monkeypatch, tmp_path):
    """API на временной базе и каталоге загрузок, чтобы не трогать рабочие данные."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'review.db').as_posix()}")
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "model_admin_token", ADMIN_TOKEN)
    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:11434")
    monkeypatch.setattr(settings, "deal_copilot_ollama_models", "qwen2.5:7b")
    (tmp_path / "uploads").mkdir()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _deal_with_document(client: TestClient) -> int:
    deal_id = client.post("/api/deals", params={"title": "Проверка ответа модели"}).json()["id"]
    uploaded = client.post(
        f"/api/deals/{deal_id}/documents",
        files={"files": ("tz.txt", "Площадь 1 200,5 м². Срок 12 месяцев.".encode(), "text/plain")},
    )
    assert uploaded.status_code == 200
    return deal_id


# Замечание 2: переменная Ollama с путём к моделям больше не читается как список моделей.

def test_ollama_models_path_variable_is_ignored(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODELS", r"C:\Users\Galina\.ollama\models")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("DEAL_COPILOT_OLLAMA_MODELS", raising=False)

    configuration = Settings(_env_file=None)

    assert configuration.parsed_ollama_models == ()


def test_deal_copilot_ollama_models_variable_sets_allowed_models(monkeypatch):
    monkeypatch.setenv("DEAL_COPILOT_OLLAMA_MODELS", "qwen2.5:7b, llama3.1:8b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    configuration = Settings(_env_file=None)

    assert configuration.parsed_ollama_models == ("qwen2.5:7b", "llama3.1:8b")


# Замечание 4: размер контекста передаётся Ollama и согласован с длиной фрагмента.

def test_ollama_num_ctx_default_fits_default_chunk():
    configuration = Settings(_env_file=None)

    assert configuration.ollama_num_ctx == 16384
    assert configuration.required_ollama_num_ctx <= configuration.ollama_num_ctx


def test_too_small_ollama_num_ctx_is_rejected_for_ollama_models():
    with pytest.raises(ValidationError, match="ollama_num_ctx"):
        Settings(
            _env_file=None,
            ollama_base_url="http://127.0.0.1:11434",
            deal_copilot_ollama_models="qwen2.5:7b",
            ollama_num_ctx=4096,
        )
    with pytest.raises(ValidationError, match="ollama_num_ctx"):
        Settings(
            _env_file=None,
            ollama_base_url="http://127.0.0.1:11434",
            deal_copilot_ollama_models="qwen2.5:7b",
            llm_input_chunk_chars=40_000,
        )


def test_ollama_provider_sends_num_ctx(monkeypatch):
    class Answer(BaseModel):
        value: int

    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:11434")
    monkeypatch.setattr(settings, "ollama_num_ctx", 20480)
    sent = {}

    def fake_urlopen(request, timeout):
        del timeout
        sent["payload"] = json.loads(request.data)
        return io.BytesIO(b'{"message":{"content":"{\\"value\\":1}"}}')

    monkeypatch.setattr("app.model_gateway.urlopen", fake_urlopen)
    OllamaProvider().structured(model="qwen2.5:7b", system="s", user="u", schema=Answer)

    assert sent["payload"]["options"] == {"num_ctx": 20480}


# Замечание 3: числовые поля приводятся к числу, нечисловые требуют проверки.

@pytest.mark.parametrize(("key", "raw", "expected"), [
    ("area_m2", "1200", "1200"),
    ("area_m2", "1 200", "1200"),
    ("area_m2", "1\u00a0200,5", "1200.5"),
    ("area_m2", " 1200.0 ", "1200"),
    ("contract_months", "12", "12"),
    ("contract_months", "12,0", "12"),
    ("payment_delay_days", "30", "30"),
])
def test_numeric_field_values_are_normalized(key, raw, expected):
    normalized = normalize_field_value(key, raw)

    assert normalized.value == expected
    assert normalized.needs_review is False


@pytest.mark.parametrize(("key", "raw"), [
    ("area_m2", "log(1200)"),
    ("area_m2", "около 1200"),
    ("area_m2", "0"),
    ("area_m2", "-5"),
    ("area_m2", "inf"),
    ("contract_months", "log(12)"),
    ("contract_months", "12,5"),
])
def test_non_numeric_field_values_need_review(key, raw):
    normalized = normalize_field_value(key, raw)

    assert normalized.value == raw
    assert normalized.needs_review is True


def test_text_fields_are_left_untouched():
    assert normalize_field_value("schedule", "5/2, с 8:00").value == "5/2, с 8:00"
    assert normalize_field_value("area_m2", None).value is None


def test_process_normalizes_numbers_and_flags_non_numeric(client, monkeypatch):
    deal_id = _deal_with_document(client)
    monkeypatch.setattr(settings, "mock_extraction_payload", json.dumps({
        "fields": [
            {"key": "area_m2", "label": "Площадь", "value": "1 200,5", "unit": "м²"},
            {"key": "contract_months", "label": "Срок", "value": "log(12)", "unit": "мес."},
            {"key": "schedule", "label": "График", "value": "5/2"},
        ],
    }, ensure_ascii=False))

    processed = client.post(f"/api/deals/{deal_id}/process")
    assert processed.status_code == 200

    fields = {field["key"]: field for field in client.get(f"/api/deals/{deal_id}/fields").json()}
    assert fields["area_m2"]["value"] == "1200.5"
    assert fields["area_m2"]["status"] != "needs_review"
    assert fields["contract_months"]["value"] == "log(12)"
    assert fields["contract_months"]["status"] == "needs_review"
    assert fields["schedule"]["value"] == "5/2"
    assert not any(field["confirmed"] for field in fields.values())


# Замечание 6: убранный из настроек профиль не роняет интерфейс.

def test_removed_active_profile_keeps_health_and_settings_available(client, monkeypatch):
    headers = {"X-Model-Admin-Token": ADMIN_TOKEN}
    selected = client.put(
        "/api/admin/model-profile", headers=headers, json={"profile_code": "ollama:qwen2.5:7b"},
    )
    assert selected.status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"

    monkeypatch.setattr(settings, "deal_copilot_ollama_models", "")

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "degraded", "model": None, "demo_mode": False, "model_configured": False,
    }

    public = client.get("/api/settings")
    assert public.status_code == 200
    assert public.json()["model_configured"] is False
    assert public.json()["llm_provider"] is None
    assert public.json()["demo_mode"] is False

    listed = client.get("/api/admin/model-profiles", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["active"] == "ollama:qwen2.5:7b"
    assert listed.json()["active_configured"] is False


def test_removed_active_profile_fails_only_on_processing(client, monkeypatch):
    headers = {"X-Model-Admin-Token": ADMIN_TOKEN}
    client.put("/api/admin/model-profile", headers=headers, json={"profile_code": "ollama:qwen2.5:7b"})
    deal_id = _deal_with_document(client)
    monkeypatch.setattr(settings, "deal_copilot_ollama_models", "")

    processed = client.post(f"/api/deals/{deal_id}/process")

    assert processed.status_code == 409
    assert "ollama:qwen2.5:7b" in processed.json()["detail"]
    latest_run = client.get(f"/api/deals/{deal_id}/pipeline").json()[0]
    assert latest_run["status"] == "failed"
