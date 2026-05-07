# Установка

Пошаговая инструкция от нуля до первого запуска.

## Требования

- Python 3.11 или новее
- Аккаунт WB Partners с доступом к API
- Google-аккаунт (для Service Account)
- Supabase-проект (бесплатный tier достаточен)

---

## Шаг 1. Клонировать репозиторий

```bash
git clone https://github.com/your-org/wb-logistics-toolkit.git
cd wb-logistics-toolkit
```

## Шаг 2. Создать виртуальное окружение и установить зависимости

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Шаг 3. Получить WB API токен

1. Откройте [WB Partners](https://partners.wildberries.ru/) → **Настройки** → **Доступ к API**
2. Нажмите **Создать новый токен**
3. Укажите имя, выберите тип — **Контент и аналитика** (нужны эндпоинты: orders, reportDetailByPeriod, tariffs/box, content, warehouse-remains)
4. Скопируйте токен — он показывается один раз

Если у вас несколько кабинетов (ООО + ИП), получите токен для каждого.

## Шаг 4. Создать Google Service Account

Нужен для записи результатов в Google Sheets.

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте проект (или выберите существующий)
3. Включите **Google Sheets API** и **Google Drive API**:
   - Меню → APIs & Services → Enable APIs → найдите и включите оба
4. Создайте Service Account:
   - APIs & Services → Credentials → Create Credentials → Service Account
   - Дайте имя, роль — **Editor**
5. Скачайте ключ:
   - Откройте созданный Service Account → вкладка **Keys** → Add Key → JSON
   - Сохраните скачанный файл как `credentials.json` в корне репозитория
6. Запомните email Service Account (вида `name@project.iam.gserviceaccount.com`)

> `credentials.json` добавлен в `.gitignore`. Никогда не коммитьте его.

## Шаг 5. Создать Google Sheet и выдать доступ

1. Создайте новую Google Таблицу (или используйте существующую)
2. Поделитесь ею с email Service Account (из шага 4, пункт 6):
   - Кнопка **Поделиться** → вставьте email → роль **Редактор**
3. Скопируйте ID таблицы из URL:
   - `https://docs.google.com/spreadsheets/d/`**`1TMadxTX...`**`/edit`

## Шаг 6. Настроить cabinets.yaml

Откройте `cabinets.yaml` и добавьте кабинеты:

```yaml
cabinets:
  - name: ooo        # имя в нижнем регистре, только латиница
    sheet_id: "1TMadxTX..."   # ID из шага 5
  - name: ip
    sheet_id: "1AbCde..."
```

`name` — произвольный идентификатор. По нему строится имя переменной окружения для токена: `WB_TOKEN_OOO`, `WB_TOKEN_IP`.

## Шаг 7. Заполнить .env

```bash
cp .env.example .env
```

Откройте `.env` и заполните:

```bash
# Токены WB — имя совпадает с name из cabinets.yaml в uppercase
WB_TOKEN_OOO=eyJ...ваш токен...
WB_TOKEN_IP=eyJ...токен второго кабинета...

# Путь к credentials.json (обычно оставить как есть)
GOOGLE_CREDENTIALS_PATH=credentials.json

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...anon key...
```

## Шаг 8. Настроить Supabase

1. Создайте проект на [supabase.com](https://supabase.com) (Free tier)
2. Скопируйте **Project URL** и **anon public key** из Settings → API
3. Примените миграцию для создания таблиц:
   - Откройте Supabase → SQL Editor
   - Выполните SQL из `database/migrations/001_create_tariffs.sql` (если файл есть)
   - Или создайте таблицы вручную по схеме из [tariffs-db.md](tariffs-db.md)
4. Загрузите начальную таблицу КТР/КРП:

```bash
python audit/etl/import_coeff_table.py
```

## Шаг 9. Проверить настройку

```bash
python check_setup.py
```

Скрипт проверит:
- наличие `.env` и всех нужных переменных
- доступность WB API (тестовый запрос к каждому кабинету)
- наличие `credentials.json` (и что он не в git staging)
- подключение к Supabase и наличие таблиц

Если всё зелёное — можно запускать.

## Первый запуск

```bash
# Оптимизатор локализации — полный анализ за 90 дней
python localization/run_analysis.py --cabinet ooo --days 90

# Аудит переплат за квартал
python audit/run_audit.py ooo 2026-01-01 2026-03-31
```

Подробнее о каждом инструменте:
- [Оптимизатор локализации — воркфлоу](workflow-localization.md)
- [Аудит переплат — гайд](tool-audit.md)
