"""Симуляция понедельного прогноза улучшения ИЛ после перестановок.

Ключевая идея: индекс локализации считается за скользящие 13 недель,
поэтому эффект перестановок виден не сразу. На неделе t после старта
эффективная локализация артикула = ((13-t)×loc_before + t×loc_after) / 13.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from shared.coeff_table import get_coeff_table, get_ktr_krp


DEFAULT_TARGET_LOCALIZATION: float = 85.0  # % локализации артикула после переноса
THRESHOLD_60: float = 60.0
THRESHOLD_80: float = 80.0


def _round_rub(value: float) -> float:
    """Округление до копеек (Decimal для точности в деньгах)."""
    return float(
        Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def _ktr_to_loc_pct(ktr_avg: float) -> float:
    """Обратное преобразование взвешенного КТР → % локализации.

    COEFF_TABLE отсортирована по убыванию min_loc (95→0). Возвращаем
    середину диапазона, в котором КТР ≥ ktr_avg.
    """
    for row in get_coeff_table():
        if ktr_avg <= row["ktr"] + 0.001:
            return (row["min_loc"] + row["max_loc"]) / 2
    return 0.0


def schedule_movements_by_week(
    movements: list[dict[str, Any]],
    redistribution_limits: dict[str, int],
    realistic_limit_pct: float = 0.3,
) -> dict[int, list[dict[str, Any]]]:
    """Распределяет перемещения по неделям с учётом capacity складов.

    Жадный алгоритм: сортирует движения по impact_rub DESC, раскладывает
    по неделям (0..13) пока не исчерпается capacity склада-получателя.
    Склады без лимита в словаре считаются безлимитными — весь объём
    уходит в неделю 0.

    Args:
        movements: Список движений с полями article, qty, to_warehouse, impact_rub.
        redistribution_limits: {warehouse: units_per_day}.
        realistic_limit_pct: Доля реально доступных слотов (0.0–1.0).

    Returns:
        {week_num: [movement_dict, ...]}
    """
    weekly_capacity: dict[str, int] = {
        wh: int(limit * 7 * realistic_limit_pct)
        for wh, limit in redistribution_limits.items()
    }

    sorted_movements = sorted(
        movements,
        key=lambda m: m.get("impact_rub", 0),
        reverse=True,
    )

    schedule: dict[int, list[dict[str, Any]]] = defaultdict(list)
    remaining_capacity: dict[str, dict[int, int]] = {
        wh: {w: cap for w in range(14)}
        for wh, cap in weekly_capacity.items()
    }

    for movement in sorted_movements:
        wh = movement.get("to_warehouse")
        qty = movement.get("qty", 0)
        remaining = qty

        if wh not in remaining_capacity:
            # Склад без лимита — считаем безлимитным, весь объём в неделю 0
            if remaining > 0:
                schedule[0].append({**movement, "qty": remaining})
            continue

        for week in range(14):
            if remaining <= 0:
                break
            cap = remaining_capacity[wh].get(week, 0)
            if cap <= 0:
                continue
            take = min(remaining, cap)
            schedule[week].append({**movement, "qty": take})
            remaining_capacity[wh][week] = cap - take
            remaining -= take

    return dict(schedule)


def _moved_to_date(
    schedule: dict[int, list[dict[str, Any]]],
    article: str,
    up_to_week: int,
) -> int:
    """Сумма перенесённых юнитов по артикулу за недели 0..up_to_week включительно."""
    total = 0
    for week in range(up_to_week + 1):
        for mv in schedule.get(week, []):
            if mv.get("article") == article:
                total += mv.get("qty", 0)
    return total


def _blended_loc(
    week_num: int,
    loc_before: float,
    loc_after: float,
    move_fraction: float,
) -> float:
    """Формула инерции 13-недельного окна.

    На неделе t:
      effective_new = loc_before × (1 - move_fraction) + loc_after × move_fraction
      blended = ((13 - t) × loc_before + t × effective_new) / 13
    """
    if week_num == 0:
        return loc_before
    effective_new = loc_before * (1 - move_fraction) + loc_after * move_fraction
    old_weeks = 13 - week_num
    new_weeks = week_num
    return (old_weeks * loc_before + new_weeks * effective_new) / 13


def _detect_first_crossing(
    roadmap: list[dict[str, Any]],
    threshold: float,
) -> int | None:
    """Находит номер первой недели, где il_forecast >= threshold."""
    for week in roadmap:
        if week["il_forecast"] >= threshold:
            return week["week"]
    return None


def simulate_roadmap(
    articles: list[dict[str, Any]],
    movements: list[dict[str, Any]],
    logistics_costs: dict[str, float],
    weekly_orders_history: list[dict[str, Any]],
    redistribution_limits: dict[str, int],
    realistic_limit_pct: float = 0.3,
    target_localization: float = DEFAULT_TARGET_LOCALIZATION,
    period_days: int = 30,
    start_date: date | None = None,
) -> dict[str, Any]:
    """Понедельный прогноз ИЛ на 13 недель вперёд.

    Учитывает инерцию скользящего 13-недельного окна WB: эффект от
    перестановок виден не сразу, а линейно нарастает до полного
    выветривания старых данных к 13-й неделе.

    Args:
        articles: Артикулы из analyze_il_irp (article, loc_pct, ktr, krp_pct,
            wb_total, price, stock_total).
        movements: Рекомендованные перестановки из generate_movements_v3.
        logistics_costs: {article_lower: ₽ за period_days}.
        weekly_orders_history: Исторические снапшоты (пока не используется,
            зарезервировано для будущего учёта сезонности).
        redistribution_limits: Дневные лимиты складов WB.
        realistic_limit_pct: Доля реально доступных слотов (0.0–1.0).
        target_localization: Локализация артикула после полного переноса (%).
        period_days: Текущий период в днях для перевода в ₽/мес.
        start_date: Дата старта прогноза (для календарных недель).

    Returns:
        {
            "params": {...},
            "roadmap": [14 записей — неделя 0 + 13 прогноза],
            "schedule": {week_num_str: [movements]},
            "milestones": {"week_60pct": int|None, "week_80pct": int|None},
        }
    """
    if start_date is None:
        start_date = date.today()
    monthly_factor = 30.0 / period_days if period_days > 0 else 1.0

    schedule = schedule_movements_by_week(
        movements, redistribution_limits, realistic_limit_pct
    )

    # Базовая стоимость логистики при КТР=1 для каждого артикула
    article_map = {a["article"].lower(): a for a in articles}
    base_costs: dict[str, float] = {}
    for art_lower, art in article_map.items():
        actual = logistics_costs.get(art_lower)
        if actual is not None and art.get("ktr", 0) > 0:
            base_costs[art_lower] = actual / art["ktr"]

    # Базовая (текущая) общая цифра для дельт
    current_logistics_monthly = sum(
        logistics_costs.get(a["article"].lower(), 0.0) * monthly_factor
        for a in articles
    )
    current_irp_monthly = 0.0
    for a in articles:
        price = a.get("price", 0.0)
        orders = a.get("wb_total", 0)
        krp = a.get("krp_pct", 0.0)
        if price > 0 and orders > 0 and period_days > 0:
            monthly_orders = orders / period_days * 30.0
            current_irp_monthly += price * (krp / 100.0) * monthly_orders
    current_total_monthly = current_logistics_monthly + current_irp_monthly

    total_plan_qty = sum(m.get("qty", 0) for m in movements)

    roadmap: list[dict[str, Any]] = []
    for week_num in range(14):
        week_logistics = 0.0
        week_irp = 0.0
        weighted_ktr_num = 0.0
        weighted_loc_num = 0.0
        weighted_orders_den = 0

        for art in articles:
            art_lower = art["article"].lower()
            stock = max(art.get("stock_total", 1), 1)
            # Неделя 0 — старт (ничего ещё не перенесено). Начиная с недели 1
            # в прогноз попадают движения, выполненные за предыдущие недели.
            if week_num == 0:
                moved = 0
            else:
                moved = _moved_to_date(schedule, art["article"], week_num - 1)
            move_fraction = min(moved / stock, 1.0) if stock > 0 else 0.0

            loc_before = art.get("loc_pct", 0.0)
            loc_after = target_localization
            effective_loc = _blended_loc(
                week_num, loc_before, loc_after, move_fraction
            )

            new_ktr, new_krp = get_ktr_krp(effective_loc)

            orders = art.get("wb_total", 0)
            weighted_ktr_num += new_ktr * orders
            weighted_loc_num += effective_loc * orders
            weighted_orders_den += orders

            base = base_costs.get(art_lower, 0.0)
            week_logistics += base * new_ktr * monthly_factor

            price = art.get("price", 0.0)
            if price > 0 and orders > 0 and period_days > 0:
                monthly_orders = orders / period_days * 30.0
                week_irp += price * (new_krp / 100.0) * monthly_orders

        if weighted_orders_den > 0:
            avg_ktr = weighted_ktr_num / weighted_orders_den
            # Используем прямой weighted-avg loc% вместо обратного маппинга
            # через КТР-бакет — чтобы траектория была плавной, а не ступеньками
            # по границам таблицы COEFF_TABLE.
            il_forecast_pct = weighted_loc_num / weighted_orders_den
        else:
            avg_ktr = 1.0
            il_forecast_pct = 0.0

        # Кумулятивный объём согласован с окном move_fraction: неделя 0 = 0,
        # на неделе t учитываем движения, завершённые за предыдущие недели.
        if week_num == 0:
            cumulative_moved = 0
        else:
            cumulative_moved = sum(
                mv.get("qty", 0)
                for w in range(week_num)
                for mv in schedule.get(w, [])
            )
        plan_pct = (
            (cumulative_moved / total_plan_qty * 100)
            if total_plan_qty > 0 else 0.0
        )

        total_new = week_logistics + week_irp
        savings = current_total_monthly - total_new

        roadmap.append({
            "week": week_num,
            "date": (start_date + timedelta(weeks=week_num)).isoformat(),
            "moved_units_cumulative": cumulative_moved,
            "plan_pct": round(plan_pct, 1),
            "il_forecast": round(il_forecast_pct, 1),
            "ktr_weighted": round(avg_ktr, 3),
            "logistics_monthly": _round_rub(week_logistics),
            "irp_monthly": _round_rub(week_irp),
            "total_monthly": _round_rub(total_new),
            "savings_vs_current": _round_rub(savings),
        })

    # Нормализуем неделю 0: никакие перестановки ещё не начались
    if roadmap:
        roadmap[0]["savings_vs_current"] = 0.0

    milestones = {
        "week_60pct": _detect_first_crossing(roadmap, THRESHOLD_60),
        "week_80pct": _detect_first_crossing(roadmap, THRESHOLD_80),
    }

    return {
        "params": {
            "realistic_limit_pct": realistic_limit_pct,
            "target_localization": target_localization,
            "period_days": period_days,
            "total_plan_qty": total_plan_qty,
            "articles_with_movements": len({m["article"] for m in movements}),
        },
        "roadmap": roadmap,
        "schedule": {str(k): v for k, v in schedule.items()},
        "milestones": milestones,
    }
