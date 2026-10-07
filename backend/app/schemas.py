import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FieldEvidence(BaseModel):
    key: str
    label: str
    value: str | None = None
    unit: str | None = None
    confidence: float | None = None
    source_document: str | None = None
    source_location: str | None = None
    source_fragment: str | None = None
    status: str = "extracted"

    @field_validator("value", mode="before")
    @classmethod
    def normalize_numeric_value(cls, value):
        # Модели часто возвращают числа как JSON number, а в UI значение хранится строкой.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_model_confidence(cls, value):
        # MiMo может вернуть качественную оценку словами вместо числа.
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if not normalized:
                return None
            # Ленивый импорт не создаёт цикл: конфиг использует CalculationRequest
            # для проверки настроек, а распознавание вызывается уже после старта.
            from .config import settings

            mapped = settings.parsed_extraction_confidence_label_map.get(normalized)
            if mapped is not None:
                return mapped
            try:
                return float(normalized.replace(",", "."))
            except ValueError:
                return None
        return None

    @field_validator("status", mode="before")
    @classmethod
    def normalize_model_status(cls, value):
        # Явный null от модели не должен отменять статус поля по умолчанию.
        if not isinstance(value, str) or not value.strip():
            return "extracted"
        return value.strip()

class DealExtraction(BaseModel):
    fields: list[FieldEvidence] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("missing_fields", mode="before")
    @classmethod
    def normalize_missing_fields(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        return value

    @field_validator("contradictions", mode="before")
    @classmethod
    def normalize_contradictions(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            # Пустой маркер вроде ": " не содержит противоречия.
            if not text.strip(":;,.—- "):
                return []
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                return [{"description": text}]
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return [item if isinstance(item, dict) else {"description": str(item)} for item in value]
        if isinstance(value, str) and value.strip():
            return [{"description": value.strip()}]
        return []

class CalculationRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    area_m2: float = Field(gt=0)
    service_price_per_m2_month: float = Field(gt=0)
    productivity_m2_per_shift: float = Field(gt=0)
    monthly_hours_per_fte: float = Field(gt=0)
    hourly_staff_cost: float = Field(ge=0)
    replacement_coefficient: float = Field(ge=1)
    manager_monthly_cost: float = Field(ge=0)
    materials_per_m2_month: float = Field(ge=0)
    equipment_per_m2_month: float = Field(ge=0)
    logistics_monthly: float = Field(ge=0)
    overhead_rate: float = Field(ge=0, lt=1)
    contingency_rate: float = Field(ge=0, lt=1)
    target_margin: float = Field(ge=0, lt=1)
    vat_rate: float = Field(ge=0, lt=1)
    contract_months: int = Field(ge=1)

    @model_validator(mode="after")
    def target_margin_must_be_achievable(self):
        if self.overhead_rate + self.target_margin >= 1:
            raise ValueError("overhead_rate + target_margin must be less than 1")
        return self

class AreaComponentCalculation(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    id: str
    area_m2: float = Field(gt=0)
    productivity_m2_per_shift: float | None = Field(default=None, gt=0)
    schedule_mode: Literal["daily", "weekly", "monthly", "on_request", "custom", "unspecified"]
    shifts_per_month: float | None = Field(default=None, gt=0)

class CalculationBreakdownRequest(BaseModel):
    confirmed: bool = False
    components: list[AreaComponentCalculation] = Field(min_length=1)
    assumptions: CalculationRequest

    @model_validator(mode="after")
    def validate_unique_components(self):
        component_ids = [component.id for component in self.components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("component ids must be unique")
        return self

class ManualAreaFieldRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    value: float = Field(gt=0)

class ProposalExportRequest(BaseModel):
    customer_name: str = Field(default="", max_length=250)
    supplier_name: str = Field(default="", max_length=250)
    contact_details: str = Field(default="", max_length=500)
    validity_days: int = Field(default=10, ge=1, le=365)
    additional_terms: str = Field(default="", max_length=4000)

class CalculationResult(BaseModel):
    labor_hours_month: float
    fte: float
    physical_staff: int
    revenue_with_vat: float
    revenue_net: float
    direct_cost: float
    full_cost: float
    profit: float
    margin: float
    break_even_price_per_m2: float
    target_price_per_m2: float
    decision: str
    conditions: list[str]
    sensitivity: list[dict[str, float]]
