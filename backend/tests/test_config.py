from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR, Settings


def test_business_defaults_and_reference_rates_share_settings_values():
    configuration = Settings(
        _env_file=None,
        default_area_m2=2500,
        default_hourly_staff_cost=475,
        default_vat_rate=0.2,
        currency_unit_symbol="$",
    )

    assert configuration.calculation_defaults["area_m2"] == 2500
    assert configuration.demo_reference_rates[0][3] == 475
    assert configuration.demo_reference_rates[0][2] == "$/час"
    assert configuration.demo_reference_rates[-1][3] == 0.2


def test_settings_parse_runtime_lists():
    configuration = Settings(
        _env_file=None,
        cors_origins="http://localhost:3000, https://demo.example",
        accepted_upload_extensions=".pdf, .docx",
        sensitivity_deltas="-0.1,0,0.1",
    )

    assert configuration.parsed_cors_origins == ["http://localhost:3000", "https://demo.example"]
    assert configuration.parsed_upload_extensions == [".pdf", ".docx"]
    assert configuration.parsed_sensitivity_deltas == (-0.1, 0.0, 0.1)


def test_invalid_runtime_configuration_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_upload_bytes=0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, sensitivity_deltas="-1,0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, default_area_m2=0)


def test_backend_env_example_loads_as_valid_settings():
    example = Path(__file__).parents[1] / ".env.example"
    configuration = Settings(_env_file=example)

    assert configuration.calculation_defaults["area_m2"] == 1200
    assert configuration.parsed_mock_extraction == {
        "fields": [],
        "missing_fields": [],
        "contradictions": [],
    }


def test_relative_sqlite_and_upload_paths_resolve_from_backend_directory():
    configuration = Settings(
        _env_file=None,
        database_url="sqlite:///../.local-model/local_mimo_smoke.db",
        data_dir="../.local-model",
        upload_dir="../.local-model/uploads",
    )

    expected_db = (BACKEND_DIR / "../.local-model/local_mimo_smoke.db").resolve()
    assert configuration.resolved_database_url == f"sqlite:///{expected_db.as_posix()}"
    assert configuration.resolve_path(configuration.upload_dir) == (
        BACKEND_DIR / "../.local-model/uploads"
    ).resolve()
