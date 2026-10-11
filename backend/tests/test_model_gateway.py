"""Проверки переключения модели без сети и перезапуска API."""

import io
import json

from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.model_gateway import ModelGateway, OllamaProvider


def test_admin_switch_persists_and_does_not_expose_secrets(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'model.db').as_posix()}")
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    monkeypatch.setattr(settings, "model_admin_token", "a" * 40)
    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:11434")
    monkeypatch.setattr(settings, "ollama_models", "qwen3:8b")
    client = TestClient(app)
    headers = {"X-Model-Admin-Token": "a" * 40}
    try:
        assert client.get("/api/admin/model-profiles").status_code == 403
        monkeypatch.setattr(settings, "model_admin_token", "")
        assert client.get("/api/admin/model-profiles", headers=headers).status_code == 503
        monkeypatch.setattr(settings, "model_admin_token", "a" * 40)
        listed = client.get("/api/admin/model-profiles", headers=headers)
        assert listed.status_code == 200
        assert {"code": "ollama:qwen3:8b", "provider": "ollama", "model": "qwen3:8b"} in listed.json()["profiles"]
        assert "11434" not in listed.text
        assert "a" * 40 not in listed.text

        rejected = client.put(
            "/api/admin/model-profile", headers=headers, json={"profile_code": "ollama:unknown"},
        )
        assert rejected.status_code == 422
        changed = client.put(
            "/api/admin/model-profile", headers=headers, json={"profile_code": "ollama:qwen3:8b"},
        )
        assert changed.status_code == 200
        assert client.get("/api/settings").json()["llm_provider"] == "ollama"
        assert client.get("/api/settings").json()["demo_mode"] is False
        with Session(engine) as db:
            assert ModelGateway().active_profile(db).code == "ollama:qwen3:8b"
        assert client.put(
            "/api/admin/model-profile", headers=headers, json={"profile_code": "mock"},
        ).status_code == 200
        assert client.get("/api/settings").json()["demo_mode"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_mock_instance_does_not_offer_cloud_profile_from_leftover_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "mock")
    monkeypatch.setattr(settings, "mimo_api_key", "unused-cloud-key")
    assert not any(code.startswith("mimo:") for code in ModelGateway().profiles())


def test_ollama_provider_sends_schema_and_validates_result(monkeypatch):
    class Answer(BaseModel):
        value: int

    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:11434")
    sent = {}

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["payload"] = json.loads(request.data)
        sent["timeout"] = timeout
        return io.BytesIO(b'{"message":{"content":"{\\"value\\":7}"}}')

    monkeypatch.setattr("app.model_gateway.urlopen", fake_urlopen)
    answer = OllamaProvider().structured(
        model="qwen3:8b", system="Instruction", user="Document", schema=Answer,
    )
    assert answer.value == 7
    assert sent["url"] == "http://127.0.0.1:11434/api/chat"
    assert sent["payload"]["format"] == Answer.model_json_schema()
    assert sent["payload"]["messages"] == [
        {"role": "system", "content": "Instruction"},
        {"role": "user", "content": "Document"},
    ]
    assert sent["payload"]["stream"] is False
