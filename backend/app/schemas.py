from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

class DealExtraction(BaseModel):
    fields: list[FieldEvidence] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)

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

class ManualAreaFieldRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    value: float = Field(gt=0)

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
