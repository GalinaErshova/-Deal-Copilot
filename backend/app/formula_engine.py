"""Безопасный расчёт по арифметическим формулам из пользовательских настроек."""
from __future__ import annotations

import ast
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FormulaDefinition:
    key: str
    label: str
    description: str
    expression: str
    variables: tuple[str, ...]


FORMULAS: tuple[FormulaDefinition, ...] = (
    FormulaDefinition("labor_hours_month", "Трудозатраты в месяц", "Часы работы по площади, выработке и сменам.", "area_m2 / productivity_m2_per_shift * hours_per_shift * working_days_per_month", ("area_m2", "productivity_m2_per_shift", "hours_per_shift", "working_days_per_month")),
    FormulaDefinition("line_labor_hours_month", "Трудозатраты строки", "Часы работы с учётом смен именно этой услуги.", "area_m2 / productivity_m2_per_shift * hours_per_shift * shifts_per_month", ("area_m2", "productivity_m2_per_shift", "hours_per_shift", "shifts_per_month")),
    FormulaDefinition("revenue_with_vat", "Цена услуг с НДС", "Начисленная стоимость услуг за месяц.", "area_m2 * service_price_per_m2_month", ("area_m2", "service_price_per_m2_month")),
    FormulaDefinition("revenue_net", "Выручка без НДС", "Цена услуг за вычетом НДС.", "revenue_with_vat / (1 + vat_rate)", ("revenue_with_vat", "vat_rate")),
    FormulaDefinition("labor_cost", "Затраты на персонал", "Трудозатраты с учётом стоимости часа и замещения.", "labor_hours_month * hourly_staff_cost * replacement_coefficient", ("labor_hours_month", "hourly_staff_cost", "replacement_coefficient")),
    FormulaDefinition("materials_cost", "Материалы", "Месячная стоимость материалов и инвентаря.", "area_m2 * materials_per_m2_month", ("area_m2", "materials_per_m2_month")),
    FormulaDefinition("equipment_cost", "Техника", "Месячная стоимость оборудования.", "area_m2 * equipment_per_m2_month", ("area_m2", "equipment_per_m2_month")),
    FormulaDefinition("direct_cost", "Прямые затраты", "Персонал, управление, материалы, техника и логистика.", "labor_cost + manager_monthly_cost + materials_cost + equipment_cost + logistics_monthly", ("labor_cost", "manager_monthly_cost", "materials_cost", "equipment_cost", "logistics_monthly")),
    FormulaDefinition("contingency_cost", "Резерв на непредвиденные расходы", "Резерв как доля прямых затрат.", "direct_cost * contingency_rate", ("direct_cost", "contingency_rate")),
    FormulaDefinition("overhead_cost", "Накладные расходы", "Накладные расходы как доля выручки без НДС.", "revenue_net * overhead_rate", ("revenue_net", "overhead_rate")),
    FormulaDefinition("full_cost", "Полная себестоимость", "Прямые затраты, резерв и накладные расходы.", "direct_cost + contingency_cost + overhead_cost", ("direct_cost", "contingency_cost", "overhead_cost")),
    FormulaDefinition("profit", "Прибыль", "Выручка без НДС за вычетом полной себестоимости.", "revenue_net - full_cost", ("revenue_net", "full_cost")),
    FormulaDefinition("margin", "Маржинальность", "Доля прибыли в выручке без НДС. Значение 0.2 соответствует 20%.", "profit / revenue_net", ("profit", "revenue_net")),
    FormulaDefinition("break_even_price_per_m2", "Тариф безубыточности", "Тариф за м², при котором покрываются затраты.", "(direct_cost + contingency_cost) / (1 - overhead_rate) * (1 + vat_rate) / area_m2", ("direct_cost", "contingency_cost", "overhead_rate", "vat_rate", "area_m2")),
    FormulaDefinition("target_price_per_m2", "Тариф для целевой маржи", "Тариф за м² с заданной целевой маржой.", "(direct_cost + contingency_cost) / (1 - overhead_rate - target_margin) * (1 + vat_rate) / area_m2", ("direct_cost", "contingency_cost", "overhead_rate", "target_margin", "vat_rate", "area_m2")),
    FormulaDefinition("line_monthly_price", "Стоимость строки услуг в месяц", "Площадь строки, умноженная на месячный тариф за м².", "area_m2 * service_price_per_m2_month", ("area_m2", "service_price_per_m2_month")),
    FormulaDefinition("contract_total_price", "Цена строки за срок контракта", "Месячная стоимость строки, умноженная на срок контракта.", "monthly_price * contract_months", ("monthly_price", "contract_months")),
)

FORMULA_BY_KEY = {formula.key: formula for formula in FORMULAS}
DEFAULT_FORMULAS = {formula.key: formula.expression for formula in FORMULAS}


class FormulaError(ValueError):
    """Некорректная или небезопасная формула."""


MAX_FORMULA_VALUE = 1e100


def _finite_value(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise FormulaError("Формула вернула недопустимое числовое значение") from exc
    if not math.isfinite(number) or abs(number) > MAX_FORMULA_VALUE:
        raise FormulaError("Формула вернула недопустимое числовое значение")
    return number


def _validated_tree(expression: str, allowed_variables: set[str]) -> ast.Expression:
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 240:
        raise FormulaError("Формула должна содержать от 1 до 240 символов")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FormulaError("Проверьте синтаксис формулы") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > 48:
        raise FormulaError("Формула слишком сложная")
    supported = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.UAdd, ast.USub, ast.Name, ast.Load, ast.Constant)
    for node in nodes:
        if not isinstance(node, supported):
            raise FormulaError("Разрешены только числа, переменные, скобки и операции +, -, *, /")
        if isinstance(node, ast.Name) and node.id not in allowed_variables:
            raise FormulaError(f"Неизвестная переменная: {node.id}")
        if isinstance(node, ast.Constant) and (isinstance(node.value, bool) or not isinstance(node.value, (int, float))):
            raise FormulaError("В формуле допустимы только числовые константы")
        if isinstance(node, ast.Constant):
            _finite_value(node.value)
    return tree


def validate_formula(expression: str, variables: tuple[str, ...] | list[str]) -> str:
    _validated_tree(expression, set(variables))
    return expression.strip()


def evaluate_formula(expression: str, variables: tuple[str, ...] | list[str], values: dict[str, float]) -> float:
    tree = _validated_tree(expression, set(variables))

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _finite_value(evaluate(node.body))
        if isinstance(node, ast.Constant):
            return _finite_value(node.value)
        if isinstance(node, ast.Name):
            if node.id not in values:
                raise FormulaError(f"Нет значения переменной: {node.id}")
            return _finite_value(values[node.id])
        if isinstance(node, ast.UnaryOp):
            value = evaluate(node.operand)
            return _finite_value(value if isinstance(node.op, ast.UAdd) else -value)
        if isinstance(node, ast.BinOp):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            else:
                if right == 0:
                    raise FormulaError("Деление на ноль: проверьте исходные данные и формулу")
                result = left / right
            return _finite_value(result)
        raise FormulaError("Неподдерживаемая операция")

    try:
        return evaluate(tree)
    except (OverflowError, ArithmeticError) as exc:
        raise FormulaError("Формула вернула недопустимое числовое значение") from exc
