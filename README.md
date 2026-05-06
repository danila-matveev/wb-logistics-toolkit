# WB Logistics Toolkit

Два инструмента для Wildberries-продавца, который хочет перестать переплачивать за логистику.

## Инструменты

### 1. Оптимизатор локализации
Показывает текущий Индекс Локализации (ИЛ), рассчитывает переплату из-за него и строит план перемещений товаров для снижения расходов.

### 2. Аудит переплат
Пересчитывает историческую логистику по официальным тарифам WB. Используется для выявления расхождений и возврата переплат.

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/your-org/wb-logistics-toolkit.git
cd wb-logistics-toolkit

# 2. Установить зависимости
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Настроить
cp .env.example .env
# Отредактировать .env и cabinets.yaml

# 4. Проверить настройку
python check_setup.py

# 5. Запустить анализ (появится в рамках Plan 2)
# python localization/run_analysis.py --cabinet ooo --days 90
```

## Документация

> **Примечание:** Документация создаётся в рамках Plan 4. Файлы появятся в директории `docs/`.

- [Установка](docs/setup.md) _(coming soon)_
- [Ключевые понятия](docs/concepts.md) _(coming soon)_
- [Как работать с инструментом](docs/workflow-localization.md) _(coming soon)_
- [Справочник складов](docs/warehouses.md) _(coming soon)_
- [Аудит переплат](docs/tool-audit.md) _(coming soon)_
- [Supabase и тарифы](docs/tariffs-db.md) _(coming soon)_

## Требования

- Python 3.11+
- WB API токен (из WB Partners)
- Google Service Account с доступом к Sheets
- Supabase проект (для истории тарифов и таблицы КТР/КРП)
