import json
from types import SimpleNamespace

from app.scope_schedule import calculate_monthly_shifts, extract_cleaning_schedule


def document(blocks):
    return SimpleNamespace(id=7, filename="requirements.docx", parse_json=json.dumps({"blocks": blocks}, ensure_ascii=False))


def test_daily_frequency_is_detected_with_secondary_weekly_and_monthly_work():
    text = "Строка 2: Описание работ: Влажная уборка пола; Ежедневно*: Х\nСтрока 3: Описание работ: Мойка окон; 1 раз в месяц: х"
    parsed = document([{
        "kind": "table",
        "path": "/table/26",
        "text": text,
        "rows": [
            ["№ п/п", "Описание работ", "Ежедневно*", "1 раз в неделю", "1 раз в месяц"],
            ["1", "Влажная уборка пола", "Х", "", ""],
            ["2", "Мойка окон", "", "", "х"],
        ],
    }])

    schedule = extract_cleaning_schedule([parsed], "Комплексная уборка помещений")

    assert schedule["schedule_mode"] == "daily"
    assert "Ежедневно" in schedule["schedule_label"]
    assert "Ежемесячно" in schedule["schedule_additional_frequencies"]
    assert schedule["schedule_source_fragment"] == text.splitlines()[0]


def test_snow_requests_do_not_invent_monthly_visit_count():
    quote = "Периодичность: Услуги оказываются по разовым заявкам Заказчика."
    parsed = document([{"kind": "paragraph", "path": "/p/38", "text": quote}])

    schedule = extract_cleaning_schedule([parsed], "Механизированная уборка снега")
    shifts = calculate_monthly_shifts(
        schedule["schedule_mode"],
        working_days_per_month=22,
        working_days_per_week=5,
        monthly_frequency_shifts=1,
    )

    assert schedule["schedule_mode"] == "on_request"
    assert shifts is None
    assert schedule["schedule_source_fragment"] == quote


def test_frequency_to_monthly_shifts_uses_configuration_and_manual_fallback():
    shared = {
        "working_days_per_month": 22,
        "working_days_per_week": 5,
        "monthly_frequency_shifts": 1,
    }

    assert calculate_monthly_shifts("daily", **shared) == 22
    assert calculate_monthly_shifts("weekly", **shared) == 4.4
    assert calculate_monthly_shifts("monthly", **shared) == 1
    assert calculate_monthly_shifts("custom", **shared, manual_shifts=3) == 3
    assert calculate_monthly_shifts("unspecified", **shared) is None
