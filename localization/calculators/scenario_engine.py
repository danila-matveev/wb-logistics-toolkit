"""Сценарный анализ экономики при разных уровнях локализации.

Считает: что было бы с логистикой и ИРП кабинета, если бы локализация
была 30%, 40%, ..., 90% — на реальных артикулах и ценах.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from shared.coeff_table import get_coeff_table, get_ktr_krp

DEFAULT_LEVELS: list[float] = [30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0]
RELOCATION_COMMISSION_PCT: float = 0.5
RELOCATION_LOCK_IN_DAYS: int = 90


def _round_rub(value: float) -> float:
    """Округление до копеек (Decimal для точности в деньгах)."""
    return float(
        Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def _scenario_color(level_pct: float, current_il_pct: float) -> str:
    """Цвет для строки сценария относительно текущего."""
    if level_pct < current_il_pct:
        return "red"
    if abs(level_pct - current_il_pct) < 0.01:
        return "yellow"
    return "green"


def _status_for_ktr(ktr: float) -> str:
    if ktr <= 0.90:
        return "🟢 Отличная"
    if ktr <= 1.05:
        return "🟡 Нейтральная"
    if ktr <= 1.30:
        return "🟠 Слабая"
    return "🔴 Критическая"


def _ktr_to_loc_pct(ktr_avg: float) -> float:
    """Обратное преобразование: взвешенный КТР → примерный % локализации."""
    for row in get_coeff_table():
        if ktr_avg <= row["ktr"]:
            return (row["min_loc"] + row["max_loc"]) / 2
    return 0.0


def _calc_scenario(
    level_pct: float,
    articles: list[dict[str, Any]],
    logistics_costs: dict[str, float],
    period_days: int,
) -> dict[str, Any]:
    """Считает метрики кабинета при заданной локализации level_pct."""
    monthly_factor = 30.0 / period_days if period_days > 0 else 1.0
    target_ktr, target_krp_pct = get_ktr_krp(level_pct)

    total_logistics = 0.0
    total_irp = 0.0

    for article in articles:
        raw_key = article["article"]
        article_key = raw_key.lower() if isinstance(raw_key, str) else raw_key
        actual_cost = logistics_costs.get(article_key)
        if actual_cost is None:
            continue

        current_ktr = article["ktr"]
        if current_ktr <= 0:
            continue

        # Обратная инверсия: сколько стоила бы логистика при КТР=1
        base_cost = actual_cost / current_ktr
        new_logistics_period = base_cost * target_ktr
        new_logistics_monthly = new_logistics_period * monthly_factor
        total_logistics += new_logistics_monthly

        price = article.get("price", 0)
        orders = article.get("wb_total", 0)
        if price > 0 and orders > 0:
            daily_orders = orders / period_days
            monthly_orders = daily_orders * 30.0
            new_irp_monthly = price * (target_krp_pct / 100.0) * monthly_orders
            total_irp += new_irp_monthly

    return {
        "logistics_monthly": _round_rub(total_logistics),
        "irp_monthly": _round_rub(total_irp),
        "total_monthly": _round_rub(total_logistics + total_irp),
        "ktr": target_ktr,
        "krp_pct": target_krp_pct,
    }


def _calc_current(
    articles: list[dict[str, Any]],
    logistics_costs: dict[str, float],
    period_days: int,
) -> dict[str, Any]:
    """Считает текущее состояние (per-article реальные КТР/КРП)."""
    monthly_factor = 30.0 / period_days if period_days > 0 else 1.0
    total_logistics = 0.0
    total_irp = 0.0

    for article in articles:
        raw_key = article["article"]
        article_key = raw_key.lower() if isinstance(raw_key, str) else raw_key
        actual_cost = logistics_costs.get(article_key)
        if actual_cost is None:
            continue
        total_logistics += actual_cost * monthly_factor
        total_irp += article.get("irp_per_month", 0.0)

    return {
        "logistics_monthly": _round_rub(total_logistics),
        "irp_monthly": _round_rub(total_irp),
        "total_monthly": _round_rub(total_logistics + total_irp),
    }


def _calc_top_articles(
    articles: list[dict[str, Any]],
    logistics_costs: dict[str, float],
    period_days: int,
    top_n: int = 15,
) -> list[dict[str, Any]]:
    """Топ-N артикулов по потенциалу экономии при переходе на 80% локализации."""
    monthly_factor = 30.0 / period_days if period_days > 0 else 1.0
    target_ktr_80, _target_krp_80 = get_ktr_krp(80.0)

    rows: list[dict[str, Any]] = []
    for article in articles:
        raw_key = article["article"]
        article_key = raw_key.lower() if isinstance(raw_key, str) else raw_key
        actual_cost = logistics_costs.get(article_key)
        if actual_cost is None:
            continue
        current_ktr = article["ktr"]
        if current_ktr <= 0:
            continue

        base_cost = actual_cost / current_ktr
        actual_monthly = actual_cost * monthly_factor
        current_irp_monthly = article.get("irp_per_month", 0.0)

        if article.get("loc_pct", 0) >= 80.0:
            opt_ktr = current_ktr
        else:
            opt_ktr = target_ktr_80
        opt_logistics_monthly = base_cost * opt_ktr * monthly_factor
        savings = (actual_monthly + current_irp_monthly) - opt_logistics_monthly

        # Вклад в ИЛ кабинета: (КТР_артикула - 1) × доля заказов
        contribution = (current_ktr - 1.0) * article.get("wb_total", 0)

        rows.append({
            "article": article["article"],
            "loc_pct": article.get("loc_pct", 0.0),
            "ktr": current_ktr,
            "krp_pct": article.get("krp_pct", 0.0),
            "orders_monthly": round(article.get("wb_total", 0) * monthly_factor),
            "logistics_fact_monthly": _round_rub(actual_monthly),
            "irp_current_monthly": _round_rub(current_irp_monthly),
            "contribution_to_il": round(contribution, 1),
            "savings_if_80_monthly": _round_rub(savings),
            "status": _status_for_ktr(current_ktr),
        })

    rows.sort(key=lambda r: r["savings_if_80_monthly"], reverse=True)
    return rows[:top_n]


def analyze_scenarios(
    il_irp: dict[str, Any],
    logistics_costs: dict[str, float],
    turnover_rub: float,
    period_days: int = 30,
    levels: list[float] | None = None,
) -> dict[str, Any]:
    """Считает сценарии экономики при градации уровней локализации.

    Args:
        il_irp: Результат analyze_il_irp() с ключами articles, summary.
        logistics_costs: {article_lower: ₽ за period_days}.
        turnover_rub: Оборот кабинета за period_days (₽).
        period_days: Длительность периода в днях.
        levels: Уровни локализации для сценариев. Дефолт [30, 40, 50, 60, 70, 80, 90].

    Returns:
        Словарь с ключами: period_days, current_il, current_loc_pct,
        current_scenario, scenarios, top_articles, relocation_economics.
    """
    if levels is None:
        levels = DEFAULT_LEVELS

    articles = il_irp.get("articles", [])
    summary = il_irp.get("summary", {})
    current_il = summary.get("overall_il", 1.0)

    # Конвертация текущего ИЛ (КТР-множитель) в примерную локализацию %
    current_loc_pct = _ktr_to_loc_pct(current_il)

    scenarios: list[dict[str, Any]] = []
    for level in levels:
        sc = _calc_scenario(level, articles, logistics_costs, period_days)
        sc["level_pct"] = level
        sc["color"] = _scenario_color(level, current_loc_pct)
        scenarios.append(sc)

    current_calc = _calc_current(articles, logistics_costs, period_days)
    current_total = current_calc["total_monthly"]

    # Дельты относительно текущего и худшего
    worst_total = max(s["total_monthly"] for s in scenarios) if scenarios else current_total
    for sc in scenarios:
        sc["delta_vs_current"] = _round_rub(sc["total_monthly"] - current_total)
        sc["delta_vs_worst"] = _round_rub(sc["total_monthly"] - worst_total)

    # Экономика перестановок
    monthly_factor = 30.0 / period_days if period_days > 0 else 1.0
    turnover_monthly = turnover_rub * monthly_factor
    commission_monthly = turnover_monthly * (RELOCATION_COMMISSION_PCT / 100.0)

    # Максимум экономии: текущий - сценарий 80%
    sc_80 = next((s for s in scenarios if s["level_pct"] == 80), None)
    max_savings = current_total - sc_80["total_monthly"] if sc_80 else 0.0
    net_benefit = max_savings - commission_monthly

    return {
        "period_days": period_days,
        "current_il": current_il,
        "current_loc_pct": current_loc_pct,
        "current_scenario": {
            "label": "Сейчас",
            **current_calc,
            "level_pct": current_loc_pct,
        },
        "scenarios": scenarios,
        "top_articles": _calc_top_articles(articles, logistics_costs, period_days),
        "relocation_economics": {
            "turnover_monthly": _round_rub(turnover_monthly),
            "commission_monthly": _round_rub(commission_monthly),
            "breakeven_monthly": _round_rub(commission_monthly),
            "max_savings_monthly": _round_rub(max_savings),
            "net_benefit_monthly": _round_rub(net_benefit),
            "lock_in_days": RELOCATION_LOCK_IN_DAYS,
        },
    }
