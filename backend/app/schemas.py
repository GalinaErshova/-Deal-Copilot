from pydantic import BaseModel, Field
from typing import Any

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
    area_m2: float = 1200
    service_price_per_m2_month: float = 180
    productivity_m2_per_shift: float = 800
    monthly_hours_per_fte: float = 164
    hourly_staff_cost: float = 350
    replacement_coefficient: float = 1.12
    manager_monthly_cost: float = 8000
    materials_per_m2_month: float = 7
    equipment_per_m2_month: float = 2
    logistics_monthly: float = 3000
    overhead_rate: float = 0.08
    contingency_rate: float = 0.03
    target_margin: float = 0.15
    vat_rate: float = 0.22
    contract_months: int = 12

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
