from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class RuntimeModelSelection(Base):
    """Хранит активный профиль модели между запросами и перезапусками API."""

    __tablename__ = "runtime_model_selection"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_code: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)


class Deal(Base):
    __tablename__ = "deals"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250))
    status: Mapped[str] = mapped_column(String(50), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    documents: Mapped[list["Document"]] = relationship(cascade="all, delete-orphan")
    fields: Mapped[list["ExtractedField"]] = relationship(cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120), default="")
    file_path: Mapped[str] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(50), default="uploaded")
    parser: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parse_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_json: Mapped[str | None] = mapped_column(Text, nullable=True)

class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"), index=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    label: Mapped[str] = mapped_column(String(200))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="extracted")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    source_location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_fragment: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class PipelineStep(Base):
    __tablename__ = "pipeline_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40))
    input_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

class ReferenceRate(Base):
    __tablename__ = "reference_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(150))
    unit: Mapped[str] = mapped_column(String(50))
    value: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

class Calculation(Base):
    __tablename__ = "calculations"
    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    input_json: Mapped[str] = mapped_column(Text)
    output_json: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(40))

class PriceListItem(Base):
    __tablename__ = "price_list_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(250))
    area_type: Mapped[str] = mapped_column(String(200), default="Площадь объекта")
    work_type: Mapped[str] = mapped_column(String(250))
    price_per_m2_month: Mapped[float] = mapped_column(Float)
    productivity_m2_per_shift: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

class DealComponentPriceSelection(Base):
    __tablename__ = "deal_component_price_selections"
    __table_args__ = (UniqueConstraint("deal_id", "component_id", name="uq_deal_component_price_selection"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    component_id: Mapped[str] = mapped_column(String(500))
    # Null explicitly means the company chose to price this line manually.
    price_list_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("price_list_items.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

class ManualServiceLine(Base):
    __tablename__ = "manual_service_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    address: Mapped[str] = mapped_column(String(500))
    area_type: Mapped[str] = mapped_column(String(200), default="Площадь объекта")
    work_type: Mapped[str] = mapped_column(String(250))
    area_m2: Mapped[float] = mapped_column(Float)
    schedule_mode: Mapped[str] = mapped_column(String(30), default="unspecified")
    shifts_per_month: Mapped[float | None] = mapped_column(Float, nullable=True)
    productivity_m2_per_shift: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_list_item_id: Mapped[int | None] = mapped_column(ForeignKey("price_list_items.id", ondelete="SET NULL"), nullable=True)
    price_per_m2_month: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

class CalculationFormula(Base):
    __tablename__ = "calculation_formulas"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    expression: Mapped[str] = mapped_column(String(240))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
