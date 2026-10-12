"""Приведение числовых полей ответа модели к виду, который понимает расчёт."""

import math
import re
from dataclasses import dataclass

# Поля, которые расчёт читает как числа; срок и количества — только целые.
INTEGER_FIELD_KEYS = frozenset({"contract_months", "payment_delay_days", "required_staff"})
NUMERIC_FIELD_KEYS = frozenset({"area_m2"}) | INTEGER_FIELD_KEYS

NEEDS_REVIEW_STATUS = "needs_review"

_NUMBER_PATTERN = re.compile(r"[+-]?\d+(?:\.\d+)?")
# Обычный, неразрывный, узкий неразрывный и тонкий пробелы между разрядами.
_DIGIT_GROUP_SPACES = re.compile("[ \u00a0\u202f\u2009]")


@dataclass(frozen=True)
class NormalizedValue:
    """Значение для сохранения и признак того, что его нужно проверить вручную."""

    value: str | None
    needs_review: bool = False


def normalize_field_value(key: str, value: str | None) -> NormalizedValue:
    """Приводит «1 200» и «1200,5» к числу; нечисловое оставляет как есть с пометкой."""
    if key not in NUMERIC_FIELD_KEYS or value is None:
        return NormalizedValue(value)
    compact = _DIGIT_GROUP_SPACES.sub("", value.strip()).replace(",", ".")
    if not _NUMBER_PATTERN.fullmatch(compact):
        return NormalizedValue(value, needs_review=True)
    number = float(compact)
    if not math.isfinite(number) or number <= 0:
        return NormalizedValue(value, needs_review=True)
    if key in INTEGER_FIELD_KEYS:
        if not number.is_integer():
            return NormalizedValue(value, needs_review=True)
        return NormalizedValue(str(int(number)))
    return NormalizedValue(str(int(number)) if number.is_integer() else str(number))
