"""Локальная проверка извлечённых строк объёма работ перед расчётом."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


def _normal(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).casefold()


def curate_scope_components(
    documents: list[Any], components: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Проверяет ссылки на документы и конфликты, не исправляя значения за пользователя."""
    docs_by_id: dict[int, Any] = {document.id: document for document in documents}
    rows_by_id: dict[int, set[tuple[str, ...]]] = {}
    for document in documents:
        try:
            parsed = json.loads(document.parse_json or "{}")
        except (TypeError, ValueError):
            parsed = {}
        rows_by_id[document.id] = {
            tuple(_normal(cell) for cell in row)
            for block in parsed.get("blocks", [])
            if isinstance(block, dict) and isinstance(block.get("rows"), list)
            for row in block["rows"]
            if isinstance(row, list)
        }
    text_by_id: dict[int, list[str]] = {}
    for document in documents:
        try:
            parsed = json.loads(document.parse_json or "{}")
        except (TypeError, ValueError):
            parsed = {}
        text_by_id[document.id] = [
            _normal(block.get("text"))
            for block in parsed.get("blocks", [])
            if isinstance(block, dict) and block.get("text")
        ]

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for component in components:
        groups[(_normal(component.get("address")), _normal(component.get("area_type")))].append(component)

    curated: list[dict[str, Any]] = []
    for component in components:
        warnings: list[str] = []
        document_id = component.get("source_document_id")
        document = docs_by_id.get(document_id)
        location = str(component.get("source_location") or "").strip()
        source_row = tuple(_normal(cell) for cell in component.get("source_row", []))
        if document is None:
            warnings.append("Документ-источник не найден")
        elif not location:
            warnings.append("Нет страницы или адреса исходной строки")
        elif not source_row or source_row not in rows_by_id.get(document_id, set()):
            warnings.append("Фрагмент источника не найден в разобранном документе")
        work_type_source = _normal(component.get("work_type_source_fragment"))
        work_type_document_id = component.get("work_type_source_document_id")
        if not component.get("work_type") or component.get("work_type") == "Не указан в документах":
            warnings.append("Вид уборки не подтверждён текстом документа")
        elif not work_type_source or not any(work_type_source in text for text in text_by_id.get(work_type_document_id, [])):
            warnings.append("Источник вида уборки не найден в документе")

        schedule_mode = component.get("schedule_mode")
        schedule_document_id = component.get("schedule_source_document_id")
        schedule_source = _normal(component.get("schedule_source_fragment"))
        if schedule_mode == "unspecified":
            component["schedule_status"] = "needs_input"
            component["schedule_warnings"] = ["Режим уборки нужно задать вручную"]
        elif (
            schedule_document_id not in docs_by_id
            or not schedule_source
            or not any(schedule_source in text for text in text_by_id.get(schedule_document_id, []))
        ):
            component["schedule_status"] = "needs_review"
            component["schedule_warnings"] = ["Источник режима уборки не подтверждён"]
        else:
            component["schedule_status"] = "verified"
            component["schedule_warnings"] = []

        related = groups[(_normal(component.get("address")), _normal(component.get("area_type")))]
        values = {round(float(row["area_m2"]), 6) for row in related}
        if len(values) > 1:
            warnings.append("Для этого адреса и вида работ найдены разные площади")

        area = component.get("area_m2")
        if not isinstance(area, (int, float)) or area <= 0:
            warnings.append("Площадь должна быть положительным числом")
        if not str(component.get("address") or "").strip():
            warnings.append("Не удалось определить адрес или объект")
        if not str(component.get("area_type") or "").strip():
            warnings.append("Не удалось определить вид площади/работ")

        curated.append(
            {
                **component,
                "curation_status": "verified" if not warnings else "needs_review",
                "curation_warnings": warnings,
            }
        )
    return curated
