"""Единая точка выбора и вызова настроенных моделей Deal Copilot."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.request import Request, urlopen

from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import settings
from .models import RuntimeModelSelection, utc_now_naive


@dataclass(frozen=True)
class ModelProfile:
    """Описывает разрешённую модель без секретов и адреса подключения."""

    code: str
    provider: str
    model: str


class ModelProvider(ABC):
    """Общий контракт получения и проверки структурированного ответа модели."""

    @abstractmethod
    def structured(self, *, model: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        """Возвращает ответ, проверенный по переданной схеме."""


class OpenAICompatibleProvider(ModelProvider):
    """Вызывает MiMo или прежний локальный OpenAI-совместимый сервер."""

    def __init__(self, *, api_key: str, base_url: str, local_schema: bool = False) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.local_schema = local_schema

    def structured(self, *, model: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        """Разделяет системную инструкцию и документ, затем проверяет JSON."""
        response_format = {"type": "json_object"}
        if self.local_schema:
            response_format["schema"] = schema.model_json_schema()
        completion = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format=response_format,
        )
        return schema.model_validate_json(completion.choices[0].message.content or "{}")


class OllamaProvider(ModelProvider):
    """Вызывает локальный Ollama API с JSON Schema и ограничением времени."""

    def structured(self, *, model: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        """Передаёт документ отдельно от инструкции и проверяет ответ локальной модели."""
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": schema.model_json_schema(),
            "stream": False,
        }).encode("utf-8")
        request = Request(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=settings.ollama_timeout_seconds) as response:
            answer = json.load(response)
        return schema.model_validate_json(answer["message"]["content"])


class MockProvider(ModelProvider):
    """Возвращает детерминированный ответ без сетевого вызова."""

    def structured(self, *, model: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        """Проверяет настроенный тестовый ответ той же схемой, что и реальные модели."""
        del model, system, user
        return schema.model_validate(settings.parsed_mock_extraction)


class ModelGateway:
    """Маршрутизирует вызовы по профилю, сохранённому в SQLite."""

    def profiles(self) -> dict[str, ModelProfile]:
        """Строит список разрешённых профилей только из настроек сервера."""
        available = {"mock": ModelProfile("mock", "mock", "mock")}
        if settings.mimo_api_key:
            available["mimo:default"] = ModelProfile("mimo:default", "mimo", settings.llm_default_model)
            available["mimo:complex"] = ModelProfile("mimo:complex", "mimo", settings.llm_complex_model)
        if settings.llm_provider == "local" and settings.mimo_base_url:
            available["local:default"] = ModelProfile("local:default", "local", settings.llm_default_model)
            available["local:complex"] = ModelProfile("local:complex", "local", settings.llm_complex_model)
        for name in settings.parsed_ollama_models:
            code = f"ollama:{name}"
            available[code] = ModelProfile(code, "ollama", name)
        return available

    def default_code(self) -> str:
        """Определяет начальный профиль из прежних настроек экземпляра."""
        if settings.is_demo_mode:
            return "mock"
        return f"{settings.llm_provider}:default"

    def active_profile(self, db: Session) -> ModelProfile:
        """Читает текущий профиль при каждом запросе, включая смену другим процессом API."""
        selected = db.get(RuntimeModelSelection, 1)
        code = selected.profile_code if selected else self.default_code()
        profile = self.profiles().get(code)
        if profile is None:
            raise ValueError(f"Model profile {code!r} is no longer configured")
        return profile

    def select_profile(self, db: Session, code: str) -> ModelProfile:
        """Сохраняет разрешённый профиль в SQLite для всех следующих запросов."""
        profile = self.profiles().get(code)
        if profile is None:
            raise ValueError("Model profile is not configured")
        selected = db.get(RuntimeModelSelection, 1)
        if selected is None:
            selected = RuntimeModelSelection(id=1, profile_code=code)
            db.add(selected)
        else:
            selected.profile_code = code
            selected.updated_at = utc_now_naive()
        db.commit()
        return profile

    def structured(
        self, *, task: str, system: str, user: str, schema: type[BaseModel],
        complex_task: bool = False, profile: ModelProfile | None = None,
    ) -> BaseModel:
        """Выполняет задачу через выбранный профиль; секреты остаются на сервере."""
        del task
        if profile is None:
            code = self.default_code()
            if complex_task and code.endswith(":default"):
                code = code.removesuffix(":default") + ":complex"
            profile = self.profiles()[code]
        if profile.provider == "mock":
            provider: ModelProvider = MockProvider()
        elif profile.provider == "ollama":
            provider = OllamaProvider()
        elif profile.provider == "local":
            provider = OpenAICompatibleProvider(
                api_key="local", base_url=settings.mimo_base_url, local_schema=True,
            )
        else:
            provider = OpenAICompatibleProvider(
                api_key=settings.mimo_api_key, base_url=settings.mimo_base_url,
            )
        return provider.structured(model=profile.model, system=system, user=user, schema=schema)


gateway = ModelGateway()
