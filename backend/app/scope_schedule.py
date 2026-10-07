"""Извлечение режима работ и перевод периодичности в смены за месяц."""

from __future__ import annotations

import json
import re
from typing import Any


def _normal(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).casefold()


def extract_cleaning_schedule(documents: list[Any], work_type: str) -> dict[str, Any]:
    """Находит подтверждённый график в ТЗ, не назначая его без источника."""
    is_snow = "снег" in _normal(work_type) or "механизирован" in _normal(work_type)
    for document in documents:
        try:
            parsed = json.loads(document.parse_json or "{}")
        except (TypeError, ValueError):
            continue
        for block in parsed.get("blocks", []):
            text = str(block.get("text") or "")
            if is_snow and re.search(r"периодичност.{0,50}разов.{0,30}заяв", _normal(text)):
                return {
                    "schedule_mode": "on_request",
                    "schedule_label": "По разовым заявкам заказчика",
                    "schedule_source_document_id": document.id,
                    "schedule_source_document_name": document.filename,
                    "schedule_source_location": str(block.get("path") or ""),
                    "schedule_source_fragment": text,
                    "schedule_additional_frequencies": [],
                }
            rows = block.get("rows")
            if is_snow or block.get("kind") not in {"table", "sheet"} or not isinstance(rows, list) or not rows:
                continue
            header = [str(cell or "") for cell in rows[0]]
            frequency_columns: list[tuple[int, str]] = []
            for index, value in enumerate(header):
                normalized = _normal(value)
                if "ежеднев" in normalized:
                    frequency_columns.append((index, "Ежедневно"))
                elif "недел" in normalized:
                    frequency_columns.append((index, "Еженедельно"))
                elif "месяц" in normalized:
                    frequency_columns.append((index, "Ежемесячно"))
            if not frequency_columns:
                continue
            marked: set[str] = set()
            for row in rows[1:]:
                if not isinstance(row, list):
                    continue
                for index, label in frequency_columns:
                    if index < len(row) and _normal(row[index]) in {"x", "х", "✓", "да"}:
                        marked.add(label)
            if not marked:
                continue
            selected = [label for label in ("Ежедневно", "Еженедельно", "Ежемесячно") if label in marked]
            primary_mode = "daily" if "Ежедневно" in marked else "weekly" if "Еженедельно" in marked else "monthly"
            source_line = next(
                (
                    line.strip()
                    for line in text.splitlines()
                    if "ежеднев" in _normal(line) and re.search(r":\s*[xх✓](?:\s|$)", line, flags=re.IGNORECASE)
                ),
                text,
            )
            additional = [label for label in selected if label != ("Ежедневно" if primary_mode == "daily" else selected[0])]
            return {
                "schedule_mode": primary_mode,
                "schedule_label": "Основные операции: " + "; дополнительные работы: ".join([selected[0], *additional]),
                "schedule_source_document_id": document.id,
                "schedule_source_document_name": document.filename,
                "schedule_source_location": str(block.get("path") or ""),
                "schedule_source_fragment": source_line,
                "schedule_additional_frequencies": additional,
            }
    return {
        "schedule_mode": "unspecified",
        "schedule_label": "Режим не найден в документах",
        "schedule_source_document_id": None,
        "schedule_source_document_name": None,
        "schedule_source_location": "",
        "schedule_source_fragment": "",
        "schedule_additional_frequencies": [],
    }


def calculate_monthly_shifts(
    mode: str,
    *,
    working_days_per_month: float,
    working_days_per_week: float,
    monthly_frequency_shifts: float,
    manual_shifts: float | None = None,
) -> float | None:
    """Переводит стандартный режим в смены/месяц; неизвестный режим требует ввода."""
    if mode == "daily":
        return working_days_per_month
    if mode == "weekly":
        return working_days_per_month / working_days_per_week
    if mode == "monthly":
        return monthly_frequency_shifts
    if mode in {"on_request", "custom", "unspecified"}:
        return manual_shifts
    return None
