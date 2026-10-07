import json
from abc import ABC, abstractmethod

from openai import OpenAI
from pydantic import BaseModel

from .config import settings


class ModelProvider(ABC):
    @abstractmethod
    def structured(self, *, model: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        raise NotImplementedError

class MiMoProvider(ModelProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self.client = OpenAI(api_key=api_key or settings.mimo_api_key, base_url=settings.mimo_base_url)

    def structured(self, *, model: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        # Локальному llama.cpp передаём JSON Schema, чтобы ограничить форму ответа.
        response_format = {"type": "json_object"}
        if settings.llm_provider == "local":
            response_format["schema"] = schema.model_json_schema()

        completion = self.client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            response_format=response_format,
        )
        content = completion.choices[0].message.content or "{}"
        return schema.model_validate(json.loads(content))

class MockProvider(ModelProvider):
    def structured(self, *, model: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        del model, system, user
        return schema.model_validate(settings.parsed_mock_extraction)

class ModelGateway:
    def __init__(self) -> None:
        if settings.is_demo_mode:
            self.provider: ModelProvider = MockProvider()
        elif settings.llm_provider == "mimo":
            self.provider = MiMoProvider()
        elif settings.llm_provider == "local":
            # Локальный llama.cpp endpoint не использует облачный API-ключ.
            self.provider = MiMoProvider(api_key="local")
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

    def structured(self, *, task: str, system: str, user: str, schema: type[BaseModel], complex_task: bool=False) -> BaseModel:
        model = settings.llm_complex_model if complex_task else settings.llm_default_model
        return self.provider.structured(model=model, system=system, user=user, schema=schema)

gateway = ModelGateway()
