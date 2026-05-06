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

# 5. Запустить анализ
python localization/run_analysis.py --cabinet ooo --days 90
```

## Документация

- [Установка](docs/setup.md)
- [Ключевые понятия](docs/concepts.md)
- [Как работать с инструментом](docs/workflow-localization.md)
- [Справочник складов](docs/warehouses.md)
- [Аудит переплат](docs/tool-audit.md)
- [Supabase и тарифы](docs/tariffs-db.md)

## Требования

- Python 3.11+
- WB API токен (из WB Partners)
- Google Service Account с доступом к Sheets
- Supabase проект (для истории тарифов и таблицы КТР/КРП)
