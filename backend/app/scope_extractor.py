"""Извлечение адресных площадей из таблиц документов сделки."""

from __future__ import annotations

import json
import re
from typing import Any


def _normal(text: Any) -> str:
    return " ".join(str(text or "").replace("\u00a0", " ").split()).casefold()


def _area_value(text: Any) -> float | None:
    value = str(text or "").replace("\u00a0", " ").replace(" ", " ")
    match = re.search(r"(?<!\w)\d[\d ]*(?:[,.]\d+)?", value)
    if not match:
        return None
    try:
        return float(match.group().replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _source_quote(address_header: str, address: str, area_header: str, area_value: Any) -> str:
    return f"{address_header}: {address}; {area_header}: {area_value}"


def _work_type_evidence(documents: list[Any], territory: bool) -> tuple[str, int | None, str, str]:
    tokens = ("механизированн", "снег") if territory else ("комплексн", "уборк")
    for document in documents:
        try:
            parsed = json.loads(document.parse_json or "{}")
        except (TypeError, ValueError):
            continue
        for block in parsed.get("blocks", []):
            text = str(block.get("text") or "")
            normalized = _normal(text)
            if all(token in normalized for token in tokens):
                label = "Механизированная уборка снега" if territory else "Комплексная уборка помещений"
                return label, document.id, str(block.get("path") or ""), text
    return "Не указан в документах", None, "", ""


def extract_area_components(documents: list[Any]) -> list[dict[str, Any]]:
    """Возвращает строки таблиц с адресом и числовой колонкой площади."""
    components: list[dict[str, Any]] = []
    seen: set[tuple[str, str, float]] = set()

    for document in documents:
        try:
            parsed = json.loads(document.parse_json or "{}")
        except (TypeError, ValueError):
            continue
        for block in parsed.get("blocks", []):
            rows = block.get("rows")
            if block.get("kind") not in {"table", "sheet"} or not isinstance(rows, list):
                continue
            for header_index, header_row in enumerate(rows[:4]):
                headers = [str(cell or "").strip() for cell in header_row]
                area_index = next((i for i, cell in enumerate(headers) if "площад" in _normal(cell)), None)
                if area_index is None:
                    continue
                address_index = next(
                    (
                        i
                        for i, cell in enumerate(headers)
                        if i != area_index and re.search(r"адрес|объект|здани|территори|наименован", _normal(cell))
                    ),
                    None,
                )
                if address_index is None:
                    address_index = next(
                        (i for i, cell in enumerate(headers) if i != area_index and _normal(cell) not in {"№", "номер"}),
                        None,
                    )
                if address_index is None:
                    continue

                address_header = headers[address_index] or "Объект"
                area_header = headers[area_index] or "Площадь"
                for row_index, row in enumerate(rows[header_index + 1 :], start=header_index + 1):
                    if not isinstance(row, list) or max(address_index, area_index) >= len(row):
                        continue
                    description = " ".join(str(row[address_index] or "").replace("\u00a0", " ").split()).strip(" .;,:\t")
                    raw_area = str(row[area_index] or "").strip()
                    area_m2 = _area_value(raw_area)
                    if not description or not area_m2 or re.search(r"итого|всего|суммарн", _normal(description)):
                        continue

                    territory = bool(re.search(r"прилега|территори|снег|наружн", _normal(description)))
                    if territory:
                        address_match = re.search(r"по адресу\s*[:—-]?\s*(.+)$", description, flags=re.IGNORECASE)
                        address = address_match.group(1).strip(" .;,:\t") if address_match else description
                        area_type = "Прилегающая территория"
                    else:
                        address = description
                        area_type = "Помещения"
                    work_type, work_type_doc_id, work_type_location, work_type_source = _work_type_evidence(documents, territory)

                    identity = (address.casefold(), area_type.casefold(), area_m2)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    path = str(block.get("path") or "")
                    page = block.get("page_no")
                    location = f"{path} page {page}" if page else path
                    components.append(
                        {
                            "id": f"{document.id}:{path}:{row_index + 1}",
                            "address": address,
                            "area_type": area_type,
                            "work_type": work_type,
                            "work_type_source_document_id": work_type_doc_id,
                            "work_type_source_location": work_type_location,
                            "work_type_source_fragment": work_type_source,
                            "area_m2": area_m2,
                            "source_document_id": document.id,
                            "source_document_name": document.filename,
                            "source_location": location,
                            "source_fragment": _source_quote(address_header, description, area_header, raw_area),
                            "source_row": [str(cell or "").strip() for cell in row],
                        }
                    )
                break

    return components
