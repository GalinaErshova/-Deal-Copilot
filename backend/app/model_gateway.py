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
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.mimo_api_key, base_url=settings.mimo_base_url)

    def structured(self, *, model: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        # MiMo is OpenAI-protocol compatible. We request strict JSON and validate locally.
        completion = self.client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            response_format={"type":"json_object"},
        )
        content = completion.choices[0].message.content or "{}"
        return schema.model_validate(json.loads(content))

class MockProvider(ModelProvider):
    def structured(self, *, model: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        del model, system, user
        payload = {
            "fields": [
                {"key":"object_type","label":"Тип объекта","value":"Офис","confidence":0.96,"status":"extracted"},
                {"key":"area_m2","label":"Площадь","value":"1200","unit":"м²","confidence":0.94,"status":"extracted"},
                {"key":"schedule","label":"График","value":"5/2","confidence":0.91,"status":"extracted"},
                {"key":"payment_delay_days","label":"Отсрочка оплаты","value":"30","unit":"дней","confidence":0.88,"status":"extracted"}
            ],
            "missing_fields":["Кто поставляет гигиенические расходники"],
            "contradictions":[]
        }
        return schema.model_validate(payload)

class ModelGateway:
    def __init__(self) -> None:
        self.provider: ModelProvider = MockProvider() if settings.demo_mode or not settings.mimo_api_key else MiMoProvider()

    def structured(self, *, task: str, system: str, user: str, schema: type[BaseModel], complex_task: bool=False) -> BaseModel:
        model = settings.llm_complex_model if complex_task else settings.llm_default_model
        return self.provider.structured(model=model, system=system, user=user, schema=schema)

gateway = ModelGateway()
