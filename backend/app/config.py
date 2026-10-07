import json
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/deal_copilot.db"
    data_dir: str = "./data"
    upload_dir: str = "./data/uploads"
    llm_provider: str = "mimo"
    llm_default_model: str = "mimo-v2.6-flash"
    llm_complex_model: str = "mimo-v2.6-pro"
    mimo_base_url: str = "https://api.xiaomimimo.com/v1"
    mimo_api_key: str = ""
    demo_mode: bool = True

    # Runtime and document-processing limits.
    cors_origins: str = "http://localhost:3000"
    accepted_upload_extensions: str = ".pdf,.docx,.xlsx"
    max_upload_bytes: int = 20_000_000
    max_upload_total_bytes: int = 50_000_000
    max_files_per_upload: int = 20
    max_spreadsheet_rows: int = 5000
    max_extraction_chars: int = 500_000
    llm_input_chunk_chars: int = 12_000
    extraction_confidence_label_map: str = '{"высокая":0.95,"высокий":0.95,"high":0.95,"средняя":0.7,"средний":0.7,"medium":0.7,"низкая":0.4,"низкий":0.4,"low":0.4}'

    # Pricing assumptions and defaults. Override these with environment variables.
    working_days_per_month: float = 22.0
    hours_per_shift: float = 8.0
    default_area_m2: float = 1200.0
    default_service_price_per_m2_month: float = 180.0
    default_productivity_m2_per_shift: float = 800.0
    default_monthly_hours_per_fte: float = 164.0
    default_hourly_staff_cost: float = 350.0
    default_replacement_coefficient: float = 1.12
    default_manager_monthly_cost: float = 8000.0
    default_materials_per_m2_month: float = 7.0
    default_equipment_per_m2_month: float = 2.0
    default_logistics_monthly: float = 3000.0
    default_overhead_rate: float = 0.08
    default_contingency_rate: float = 0.03
    default_target_margin: float = 0.15
    default_vat_rate: float = 0.22
    default_contract_months: int = 12
    area_match_tolerance: float = 0.000001
    display_locale: str = "ru-RU"
    currency_code: str = "RUB"
    currency_unit_symbol: str = "₽"
    display_number_max_fraction_digits: int = 1
    display_currency_max_fraction_digits: int = 0
    display_percentage_factor: int = 100
    display_percentage_decimal_places: int = 1
    base_sensitivity_label: str = "Base"
    confidence_good_threshold: float = 0.9
    no_bid_margin_threshold: float = 0.0
    condition_price_decimal_places: int = 1
    condition_price_unit: str = "₽/м²/мес"
    sensitivity_bar_min_width: float = 4.0
    sensitivity_bar_max_width: float = 100.0
    sensitivity_bar_margin_offset: float = 0.2
    sensitivity_bar_scale: float = 180.0
    minimum_physical_staff: int = 1
    currency_decimal_places: int = 2
    labor_hours_decimal_places: int = 2
    fte_decimal_places: int = 2
    margin_decimal_places: int = 4
    sensitivity_deltas: str = "-0.20,-0.10,-0.05,0,0.05,0.10,0.20"

    # Demo reference values and mock extraction are configurable, too.
    mock_extraction_payload: str = '{"fields":[],"missing_fields":[],"contradictions":[]}'
    extraction_prompt_version: str = "cleaning_requirements_v2"
    extraction_system_prompt: str = """Ты извлекаешь данные из тендерных документов для B2B-клининга.
Верни только валидный JSON без Markdown и пояснений, строго в структуре:
{"fields": [], "missing_fields": [], "contradictions": []}.

Для каждого элемента fields верни key и label (строки), value и unit
(строки или null), confidence (число от 0 до 1 или null), source_document,
source_location, source_fragment и status (строки или null).
missing_fields всегда должен быть массивом строк.
contradictions всегда должен быть массивом объектов; если противоречий нет,
верни пустой массив []. Не заменяй его строкой, двоеточием или null.

Документы передаются блоками с маркерами вида:
[DOCUMENT=<имя файла> PATH=<путь блока> page=<номер страницы> KIND=<тип>]

Правила:
1. source_document копируй точно из DOCUMENT.
2. source_location копируй точно из PATH; при наличии номера страницы добавь "page N".
3. source_fragment должен быть короткой дословной выдержкой из того же блока.
4. Не придумывай значения, источники, координаты и цитаты.
5. Если значение отсутствует, не создавай поле: укажи его в missing_fields.
6. Если документы задают разные значения одного параметра, добавь их в contradictions.
7. Для чисел возвращай только число в value, единицу измерения — в unit.
8. confidence возвращай числом от 0 до 1, не словами «высокая/средняя/низкая».

Основные поля: object_type, area_m2, schedule, contract_months,
payment_delay_days, required_staff, sanitary_supplies_provider."""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    @model_validator(mode="after")
    def validate_configuration(self):
        positive_values = {
            "working_days_per_month": self.working_days_per_month,
            "hours_per_shift": self.hours_per_shift,
            "max_upload_bytes": self.max_upload_bytes,
            "max_upload_total_bytes": self.max_upload_total_bytes,
            "max_files_per_upload": self.max_files_per_upload,
            "max_spreadsheet_rows": self.max_spreadsheet_rows,
            "max_extraction_chars": self.max_extraction_chars,
            "llm_input_chunk_chars": self.llm_input_chunk_chars,
        }
        if any(value <= 0 for value in positive_values.values()):
            raise ValueError("Runtime limits and work schedule settings must be positive")
        if self.max_upload_total_bytes < self.max_upload_bytes:
            raise ValueError("max_upload_total_bytes must be at least max_upload_bytes")
        if self.area_match_tolerance < 0 or self.minimum_physical_staff < 0:
            raise ValueError("Calculation tolerances and minimum staffing cannot be negative")
        if any(value < 0 for value in (
            self.currency_decimal_places,
            self.labor_hours_decimal_places,
            self.fte_decimal_places,
            self.margin_decimal_places,
            self.display_number_max_fraction_digits,
            self.display_currency_max_fraction_digits,
            self.display_percentage_decimal_places,
            self.condition_price_decimal_places,
        )):
            raise ValueError("Rounding precision cannot be negative")
        if self.display_percentage_factor <= 0 or self.sensitivity_bar_scale <= 0:
            raise ValueError("Display scaling settings must be positive")
        if not 0 <= self.confidence_good_threshold <= 1:
            raise ValueError("confidence_good_threshold must be between 0 and 1")
        confidence_labels = self.parsed_extraction_confidence_label_map
        if any(not 0 <= value <= 1 for value in confidence_labels.values()):
            raise ValueError("extraction_confidence_label_map values must be between 0 and 1")
        if self.sensitivity_bar_min_width < 0 or self.sensitivity_bar_max_width < self.sensitivity_bar_min_width:
            raise ValueError("Sensitivity bar width settings are invalid")
        if any(delta <= -1 for delta in self.parsed_sensitivity_deltas):
            raise ValueError("Sensitivity deltas must be greater than -1")
        if self.llm_provider not in {"mimo", "local", "mock"}:
            raise ValueError("llm_provider must be one of the configured providers")
        try:
            mock_payload = json.loads(self.mock_extraction_payload)
        except json.JSONDecodeError as exc:
            raise ValueError("mock_extraction_payload must be valid JSON") from exc
        if not isinstance(mock_payload, dict) or not isinstance(mock_payload.get("fields"), list):
            raise ValueError("mock_extraction_payload must contain a fields array")  # noqa: TRY004 — Pydantic validators must raise ValueError
        from .schemas import CalculationRequest

        CalculationRequest(**self.calculation_defaults)
        return self

    @property
    def calculation_defaults(self) -> dict[str, float | int]:
        return {
            "area_m2": self.default_area_m2,
            "service_price_per_m2_month": self.default_service_price_per_m2_month,
            "productivity_m2_per_shift": self.default_productivity_m2_per_shift,
            "monthly_hours_per_fte": self.default_monthly_hours_per_fte,
            "hourly_staff_cost": self.default_hourly_staff_cost,
            "replacement_coefficient": self.default_replacement_coefficient,
            "manager_monthly_cost": self.default_manager_monthly_cost,
            "materials_per_m2_month": self.default_materials_per_m2_month,
            "equipment_per_m2_month": self.default_equipment_per_m2_month,
            "logistics_monthly": self.default_logistics_monthly,
            "overhead_rate": self.default_overhead_rate,
            "contingency_rate": self.default_contingency_rate,
            "target_margin": self.default_target_margin,
            "vat_rate": self.default_vat_rate,
            "contract_months": self.default_contract_months,
        }

    @property
    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def parsed_upload_extensions(self) -> list[str]:
        return [ext.strip().lower() for ext in self.accepted_upload_extensions.split(",") if ext.strip()]

    @property
    def parsed_sensitivity_deltas(self) -> tuple[float, ...]:
        return tuple(float(delta.strip()) for delta in self.sensitivity_deltas.split(",") if delta.strip())

    def resolve_path(self, path: str | Path) -> Path:
        """Разрешает относительные пути от backend/, а не от каталога запуска процесса."""
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = BACKEND_DIR / resolved
        return resolved.resolve()

    @property
    def resolved_database_url(self) -> str:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return self.database_url
        relative_path = self.database_url[len(prefix):]
        if relative_path == ":memory:":
            return self.database_url
        return f"{prefix}{self.resolve_path(relative_path).as_posix()}"

    @property
    def demo_reference_rates(self) -> list[tuple[str, str, str, float, str]]:
        return [
            ("staff", "Стоимость часа клинера", f"{self.currency_unit_symbol}/час", self.default_hourly_staff_cost, "Демо-данные; штатный сотрудник"),
            ("productivity", "Выработка регулярной уборки", "м²/смену", self.default_productivity_m2_per_shift, "Упрощённый MVP-норматив"),
            ("material", "Химия и инвентарь", f"{self.currency_unit_symbol}/м²/мес", self.default_materials_per_m2_month, "Демо-данные"),
            ("equipment", "Техника", f"{self.currency_unit_symbol}/м²/мес", self.default_equipment_per_m2_month, "Демо-данные"),
            ("finance", "Целевая маржа", "доля", self.default_target_margin, "Демо-данные"),
            ("finance", "НДС", "доля", self.default_vat_rate, "Настраиваемый параметр"),
        ]

    @property
    def parsed_mock_extraction(self) -> dict:
        return json.loads(self.mock_extraction_payload)

    @property
    def parsed_extraction_confidence_label_map(self) -> dict[str, float]:
        return {
            str(label).strip().casefold(): float(value)
            for label, value in json.loads(self.extraction_confidence_label_map).items()
        }

    @property
    def is_demo_mode(self) -> bool:
        missing_cloud_key = self.llm_provider == "mimo" and not self.mimo_api_key
        return self.demo_mode or self.llm_provider == "mock" or missing_cloud_key

    def ensure_dirs(self) -> None:
        self.resolve_path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        self.resolve_path(self.data_dir).mkdir(parents=True, exist_ok=True)

settings = Settings()
