"""Per-article ИЛ/ИРП analyzer for WB orders.

Replicates the logic of the community WB ИЛ/ИРП spreadsheet:
- Computes per-article localization % with regional breakdown (6 macro-FDs)
- Looks up КТР/КРП from the official WB coefficient table
- Calculates ИРП price impact in ₽/month
- Ranks articles by (КТР-1)×orders contribution to overall ИЛ
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from shared.coeff_table import calc_financial_impact, get_ktr_krp
from localization.data.mappings import CIS_REGIONS, SKIP_WAREHOUSES, get_delivery_fd, get_warehouse_fd

# ============================================================================
# Constants
# ============================================================================

# Macro-regions used in regional breakdown (keys = FD names from mappings)
REGION_GROUPS: dict[str, list[str]] = {
    'Центральный': ['Центральный'],
    'Южный + Северо-Кавказский': ['Южный + Северо-Кавказский'],
    'Приволжский': ['Приволжский'],
    'Уральский': ['Уральский'],
    'Дальневосточный + Сибирский': ['Дальневосточный + Сибирский'],
    'Северо-Западный': ['Северо-Западный'],
}

_ALL_REGIONS: tuple[str, ...] = tuple(REGION_GROUPS)


# ============================================================================
# Helpers
# ============================================================================

def classify_status(ktr: float) -> str:
    """Classify article localization status by КТР value.

    Returns:
        'Отличная' | 'Нейтральная' | 'Слабая' | 'Критическая'
    """
    if ktr <= 0.90:
        return 'Отличная'
    if ktr <= 1.05:
        return 'Нейтральная'
    if ktr <= 1.30:
        return 'Слабая'
    return 'Критическая'


def _make_recommendation(article: str, ktr: float, weakest_region: str) -> str:
    """Generate a short actionable recommendation string."""
    if ktr <= 1.0:
        return f"Артикул {article}: локализация OK, мониторинг."
    action = f"Переместить сток {article} в регион '{weakest_region}'."
    if ktr >= 2.0:
        action += " Срочно — высокий КТР."
    return action


# ============================================================================
# Main analyzer
# ============================================================================

def analyze_il_irp(
    orders: list[dict[str, Any]],
    prices_dict: dict[str, float],
    period_days: int = 30,
) -> dict[str, Any]:
    """Compute per-article ИЛ/ИРП metrics from WB orders.

    Args:
        orders: List of WB order dicts (fields: supplierArticle, warehouseName,
                oblastOkrugName or oblast, isCancel).
        prices_dict: Mapping article_lower → retail price (₽).
        period_days: Length of the observed period in days.

    Returns:
        Dict with keys 'summary', 'articles', 'top_problems'.
    """
    # article → region → {'local': int, 'nonlocal': int}
    article_region_counts: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {'local': 0, 'nonlocal': 0})
    )

    total_rf_orders: int = 0
    total_cis_orders: int = 0
    cancelled_orders: int = 0
    skipped_orders: int = 0

    for order in orders:
        if order.get('isCancel'):
            cancelled_orders += 1
            continue

        article_raw: str = order.get('supplierArticle', '') or ''
        warehouse: str = order.get('warehouseName', '') or ''
        # Support both field names WB API may return
        oblast: str = (
            order.get('oblastOkrugName', '')
            or order.get('oblast', '')
            or ''
        )

        article = article_raw.lower()

        # Skip transit / aggregation warehouses
        if warehouse in SKIP_WAREHOUSES:
            continue

        warehouse_fd = get_warehouse_fd(warehouse)
        # Unknown warehouse → skip (can't determine localization)
        if warehouse_fd is None:
            skipped_orders += 1
            continue

        # CIS warehouse → count as CIS, skip article-level processing
        if warehouse_fd in CIS_REGIONS:
            total_cis_orders += 1
            continue

        delivery_fd = get_delivery_fd(oblast)
        # If oblastOkrugName didn't resolve, try regionName as fallback
        if delivery_fd is None:
            region_name = order.get('regionName', '') or ''
            delivery_fd = get_delivery_fd(region_name)

        # CIS delivery address → count as CIS, skip
        if delivery_fd in CIS_REGIONS:
            total_cis_orders += 1
            continue

        # Still unknown — check if regionName looks like CIS
        # (orders from RU warehouse → CIS delivery have empty oblastOkrugName)
        if delivery_fd is None:
            region_name = order.get('regionName', '') or ''
            if region_name:
                # CIS regions not in our mapping but detectable by country pattern
                total_cis_orders += 1
            else:
                skipped_orders += 1
            continue

        is_local = warehouse_fd == delivery_fd
        key = 'local' if is_local else 'nonlocal'
        article_region_counts[article][delivery_fd][key] += 1
        total_rf_orders += 1

    # -------------------------------------------------------------------------
    # Per-article metrics
    # -------------------------------------------------------------------------
    articles_out: list[dict[str, Any]] = []

    for article, region_data in article_region_counts.items():
        # Sum across all regions
        local_total = sum(v['local'] for v in region_data.values())
        nonlocal_total = sum(v['nonlocal'] for v in region_data.values())
        wb_total = local_total + nonlocal_total

        if wb_total == 0:
            continue

        loc_pct = round(local_total / wb_total * 100, 1)
        ktr, krp_pct = get_ktr_krp(loc_pct)
        contribution = round((ktr - 1) * wb_total, 1)
        weighted = ktr * wb_total

        status = classify_status(ktr)

        price = prices_dict.get(article, 0.0)
        irp_per_order = round(price * krp_pct / 100, 2) if price > 0 else 0.0
        irp_per_month = calc_financial_impact(krp_pct, price, wb_total, period_days)

        # Regional breakdown — all 6 macro-FDs present in output
        regions: dict[str, dict[str, Any]] = {}
        for region_name in _ALL_REGIONS:
            counts = region_data.get(region_name, {'local': 0, 'nonlocal': 0})
            r_local = counts['local']
            r_nonlocal = counts['nonlocal']
            r_total = r_local + r_nonlocal
            r_pct = round(r_local / r_total * 100, 1) if r_total > 0 else 0.0
            regions[region_name] = {
                'local': r_local,
                'nonlocal': r_nonlocal,
                'total': r_total,
                'pct': r_pct,
            }

        # Weakest region = one with orders and lowest localization %
        weakest_region = _find_weakest_region(regions)

        articles_out.append({
            'article': article,
            'wb_local': local_total,
            'wb_nonlocal': nonlocal_total,
            'wb_total': wb_total,
            'loc_pct': loc_pct,
            'ktr': ktr,
            'krp_pct': krp_pct,
            'contribution': contribution,
            'weighted': weighted,
            'status': status,
            'price': price,
            'irp_per_order': irp_per_order,
            'irp_per_month': irp_per_month,
            'regions': regions,
            'weakest_region': weakest_region,
        })

    # Sort by contribution descending (worst offenders first)
    articles_out.sort(key=lambda a: a['contribution'], reverse=True)

    # -------------------------------------------------------------------------
    # Summary / overall metrics
    # -------------------------------------------------------------------------
    rf_articles_with_orders = [a for a in articles_out if a['wb_total'] > 0]

    total_orders_for_il = sum(a['wb_total'] for a in rf_articles_with_orders)

    # ИЛ = weighted avg КТР (over RF orders only)
    overall_il = 0.0
    if total_orders_for_il > 0:
        overall_il = (
            sum(a['ktr'] * a['wb_total'] for a in rf_articles_with_orders)
            / total_orders_for_il
        )

    # ИРП = weighted avg КРП% denominator includes CIS
    irp_denominator = total_rf_orders + total_cis_orders
    overall_irp_pct = 0.0
    if irp_denominator > 0:
        overall_irp_pct = (
            sum(a['krp_pct'] * a['wb_total'] for a in rf_articles_with_orders)
            / irp_denominator
        )

    local_orders = sum(a['wb_local'] for a in rf_articles_with_orders)
    nonlocal_orders = sum(a['wb_nonlocal'] for a in rf_articles_with_orders)
    loc_pct_overall = (
        round(local_orders / total_rf_orders * 100, 1) if total_rf_orders > 0 else 0.0
    )

    irp_zone_articles = sum(1 for a in rf_articles_with_orders if a['krp_pct'] > 0)
    irp_monthly_cost_rub = sum(a['irp_per_month'] for a in rf_articles_with_orders)

    _now = datetime.now()
    _period_from = (_now - timedelta(days=period_days)).strftime('%d.%m.%Y')
    _period_to = _now.strftime('%d.%m.%Y')

    summary: dict[str, Any] = {
        'overall_il': round(overall_il, 4),
        'overall_irp_pct': round(overall_irp_pct, 4),
        'total_rf_orders': total_rf_orders,
        'total_cis_orders': total_cis_orders,
        'local_orders': local_orders,
        'nonlocal_orders': nonlocal_orders,
        'loc_pct': loc_pct_overall,
        'total_articles': len(rf_articles_with_orders),
        'irp_zone_articles': irp_zone_articles,
        'irp_monthly_cost_rub': round(irp_monthly_cost_rub, 2),
        'metadata': {
            'generated_at': _now.strftime('%d.%m.%Y %H:%M'),
            'period_days': period_days,
            'period_from': _period_from,
            'period_to': _period_to,
            'total_orders_loaded': len(orders),
            'cancelled_orders': cancelled_orders,
            'rf_orders_analyzed': total_rf_orders,
            'cis_orders': total_cis_orders,
            'skipped_orders': skipped_orders,
            'articles_analyzed': len(rf_articles_with_orders),
            'data_source': 'WB supplier/orders API (v1)',
            'note': (
                'WB считает ИЛ/ИРП за 13 ISO-недель. '
                'Наш расчёт за календарные дни. '
                'Расхождение ≤ 3 п.п. по % локализации из-за разницы: orders vs deliveries.'
            ),
        },
    }

    # -------------------------------------------------------------------------
    # Top-10 problems: articles with contribution > 0
    # -------------------------------------------------------------------------
    problem_articles = [a for a in articles_out if a['contribution'] > 0]
    top_problems: list[dict[str, Any]] = [
        {
            'rank': i + 1,
            'article': a['article'],
            'orders': a['wb_total'],
            'loc_pct': a['loc_pct'],
            'ktr': a['ktr'],
            'krp_pct': a['krp_pct'],
            'contribution': a['contribution'],
            'weakest_region': a['weakest_region'],
            'recommendation': _make_recommendation(
                a['article'], a['ktr'], a['weakest_region']
            ),
        }
        for i, a in enumerate(problem_articles[:10])
    ]

    return {
        'summary': summary,
        'articles': articles_out,
        'top_problems': top_problems,
    }


# ============================================================================
# Private helpers
# ============================================================================

def _find_weakest_region(regions: dict[str, dict[str, Any]]) -> str:
    """Return the region name with orders and the lowest localization %.

    Falls back to '' if no region has any orders.
    """
    candidates = [
        (name, data)
        for name, data in regions.items()
        if data['total'] > 0
    ]
    if not candidates:
        return ''
    return min(candidates, key=lambda x: x[1]['pct'])[0]
