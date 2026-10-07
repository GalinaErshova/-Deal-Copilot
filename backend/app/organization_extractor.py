"""Детерминированно извлекает реквизиты заказчика из разобранных файлов сделки."""
from __future__ import annotations

import json
import re
from typing import Any


def extract_organization_profile(documents: list[Any]) -> dict[str, dict[str, Any]]:
    """Возвращает только найденные значения вместе с точной ссылкой на исходный блок."""
    candidates: dict[str, dict[str, Any]] = {}

    def add(key: str, match: re.Match[str], block: dict[str, Any], document: Any) -> None:
        value = match.group("value").strip(" \t\r\n,;:")
        if not value:
            return
        candidates[key] = {
            "value": value,
            "document_id": document.id,
            "document_name": document.filename,
            "source_location": block.get("path", ""),
            "source_fragment": match.group(0).strip(),
        }

    for document in documents:
        if not document.parse_json:
            continue
        parsed = json.loads(document.parse_json)
        for block in parsed.get("blocks", []):
            text = " ".join(str(block.get("text") or "").split())
            if not text:
                continue

            customer = re.search(r"Заказчик\s*:\s*(?P<value>.+?)(?=\s+(?:Адрес(?: места нахождения)?|ИНН(?:/КПП)?|КПП|ОГРН|БИК|тел\.?|E-?mail)\s*:?)", text, re.IGNORECASE)
            if customer:
                add("customer_name", customer, block, document)
                customer_start = customer.start()
                customer_scope = text[customer_start:]

                address = re.search(
                    r"(?:Адрес(?: места нахождения)?\s*:\s*(?:Юр\.\s*адрес\s*:\s*)?|Юр(?:идический)?\s+адрес\s*:\s*)(?P<value>.+?)(?=\s+(?:ИНН(?:/КПП)?|КПП|ОГРН|БИК|Единый казначейский|Казначейский счет|тел\.?|E-?mail)\s*:?)",
                    customer_scope,
                    re.IGNORECASE,
                )
                if address:
                    add("customer_address", address, block, document)

                tax_ids = re.search(r"ИНН/КПП\s*(?P<value>\d{10,12}\s*/\s*\d{9})", customer_scope, re.IGNORECASE)
                if tax_ids:
                    inn, kpp = re.split(r"\s*/\s*", tax_ids.group("value"))
                    add("customer_inn", re.match(r"(?P<value>\d+)", inn), block, document)
                    add("customer_kpp", re.search(r"(?P<value>\d+)$", kpp), block, document)

                ogrn = re.search(r"ОГРН(?:ИП)?\s*[:№]?\s*(?P<value>\d{13,15})", customer_scope, re.IGNORECASE)
                if ogrn:
                    add("customer_ogrn", ogrn, block, document)
                phone = re.search(r"(?:тел(?:ефон)?\.?\s*[, ]*факс|тел(?:ефон)?\.?|факс)\s*[:.]?\s*(?P<value>\+?[\d(][\d()\s.-]{5,}\d)", customer_scope, re.IGNORECASE)
                if phone:
                    add("customer_phone", phone, block, document)
                email = re.search(r"(?:E-?mail|электронная почта)\s*:\s*(?P<value>[\w.+-]+@[\w.-]+\.[A-Za-zА-Яа-я]{2,})", customer_scope, re.IGNORECASE)
                if email:
                    add("customer_email", email, block, document)

            # Вводная часть договора связывает представителя с конкретной стороной.
            representative = re.search(
                r"(?P<value>Заказчик.{0,100}?в лице\s+(?:директора|руководителя)\s+[А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+){1,2})",
                text,
                re.IGNORECASE,
            )
            if representative and "customer_contact_person" not in candidates:
                fragment = representative.group("value")
                person = re.search(r"(?:директора|руководителя)\s+(?P<value>[А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+){1,2})", fragment, re.IGNORECASE)
                if person:
                    add("customer_contact_person", person, block, document)

    return candidates
