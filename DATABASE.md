# Универсальная таблица проверок

## ma_data.incent_opex_check_universal

Универсальная таблица для хранения результатов всех проверок OpEx. Каждая строка представляет одну проверку (алерт) для конкретной комбинации измерений.
Таблица располагается в базе данных Amazon RedShift.

### Структура таблицы

| Поле | Тип данных | Описание |
|------|------------|----------|
| `date` | TIMESTAMP | Дата и время выполнения проверки |
| `check_name` | VARCHAR(100) | Идентификатор проверки (например, `01-incent.cr`, `02-incent.p7`) |
| `metric` | VARCHAR(100) | Название проверяемой метрики (например, `previous_cr`, `historical_cr`, `payers_1w`) |
| `partner_id` | INTEGER | ID партнёра |
| `app_short` | VARCHAR(50) | Название приложения с суффиксом store (`fd_gp`, `fd_as`) |
| `country` | VARCHAR(10) | Страна (`US`, `DE`, `ALL` и т.д.). `NULL` если не используется |
| `segment` | VARCHAR(255) | Сегмент оперирования. `NULL` если не используется |
| `slice1` | VARCHAR(255) | Первый срез данных. Значение зависит от типа проверки |
| `slice2` | VARCHAR(255) | Второй срез данных. Значение зависит от типа проверки |
| `slice3` | VARCHAR(255) | Третий срез данных (резерв). `NULL` если не используется |
| `slice4` | VARCHAR(255) | Четвёртый срез данных (резерв). `NULL` если не используется |
| `cohort_date` | DATE | Дата когорты или периода, к которому относится проверка |
| `metric_crit_category` | VARCHAR(50) | Категория критичности (`INFO`, `WARNING`, `CRITICAL`) |
| `current_value` | FLOAT | Текущее значение метрики |
| `reference_value` | FLOAT | Эталонное (reference) значение для сравнения |
| `reference_value_ci` | FLOAT | Ширина доверительного интервала для reference-значения |
| `change_perc` | FLOAT | Относительное изменение: `(current_value - reference_value) / reference_value` |
| `is_alert` | BOOLEAN | Флаг срабатывания алерта (`TRUE` если current_value вне диапазона reference ± ci) |
| `alert_category` | VARCHAR(50) | Категория алерта (`WARNING`, `CRITICAL`, `NULL` если не применимо) |

### Использование полей для разных проверок

#### 01-incent.cr (Conversion Rate)
| Поле | Значение |
|------|----------|
| `metric` | `previous_cr` или `historical_cr` |
| `partner_id` | ID партнёра из конфигурации |
| `app_short` | Название приложения + суффикс store (`fd_gp`, `fd_as`) |
| `country` | Страна (`US`, `DE`, `ALL` и т.д.) |
| `segment` | `NULL` (не используется) |
| `slice1` | `level` — уровень конверсии (`1`, `7`, `30` и т.д.) |
| `slice2` | `cw` — calendar week (`7`, `30`, `90`) |
| `slice3` | `NULL` |
| `slice4` | `NULL` |

#### 02-incent.p7 (Payers 7 days)
| Поле | Значение |
|------|----------|
| `metric` | `payers_1w` (WARNING) или `payers_4w` (CRITICAL) |
| `partner_id` | ID партнёра |
| `app_short` | Название приложения |
| `country` | `NULL` (не используется) |
| `segment` | Название сегмента оперирования (`operation_segment_nm`) |
| `slice1` | `NULL` |
| `slice2` | `NULL` |
| `slice3` | `NULL` |
| `slice4` | `NULL` |
| `alert_category` | `WARNING` или `CRITICAL` |

**Примечание для 02-incent.p7:**
- `current_value` — количество плательщиков (за 1 или 4 недели)
- `reference_value` — пороговое значение (threshold)
- `reference_value_ci` — `NULL` (не применимо для threshold-based проверок)
- `change_perc` — насколько ниже порога: `(current - threshold) / threshold`

#### Шаблон для новых проверок
| Проверка | partner_id | app_short | country | segment | slice1 | slice2 |
|----------|------------|-----------|---------|---------|--------|--------|
| 03-incent.ltv | ID партнёра | app + store | country | - | cohort_week | - |

### Логика алертов

Алерт срабатывает (`is_alert = TRUE`), если текущее значение выходит за пределы доверительного интервала reference-значения:

```
is_alert = (current_value < reference_value - reference_value_ci) OR
           (current_value > reference_value + reference_value_ci)
```

Где `reference_value_ci = N_SIGMAS * sqrt(reference_value * (1 - reference_value) / n)`

### SQL для создания таблицы

```sql
CREATE TABLE ma_data.incent_opex_check_universal (
    date                    TIMESTAMP,
    check_name              VARCHAR(100),
    metric                  VARCHAR(100),
    partner_id              INTEGER,
    app_short               VARCHAR(50),
    country                 VARCHAR(10),
    segment                 VARCHAR(255),
    slice1                  VARCHAR(255),
    slice2                  VARCHAR(255),
    slice3                  VARCHAR(255),
    slice4                  VARCHAR(255),
    cohort_date             DATE,
    metric_crit_category    VARCHAR(50),
    current_value           FLOAT,
    reference_value         FLOAT,
    reference_value_ci      FLOAT,
    change_perc             FLOAT,
    is_alert                BOOLEAN,
    alert_category          VARCHAR(50)
)
DISTSTYLE AUTO
SORTKEY (date, check_name, app_short);

GRANT SELECT, INSERT, UPDATE, DELETE ON ma_data.incent_opex_check_universal TO PUBLIC;
```

### Примеры записей

#### 01-incent.cr
```
date                 | 2026-02-04 10:30:00
check_name           | 01-incent.cr
metric               | previous_cr
partner_id           | 1000023
app_short            | fd_gp
country              | US
segment              | NULL
slice1               | 7
slice2               | 30
slice3               | NULL
slice4               | NULL
cohort_date          | 2026-01-20
metric_crit_category | INFO
current_value        | 0.42
reference_value      | 0.50
reference_value_ci   | 0.03
change_perc          | -0.16
is_alert             | TRUE
alert_category       | WARNING
```

#### 02-incent.p7
```
date                 | 2026-02-04 11:00:00
check_name           | 02-incent.p7
metric               | payers_1w
partner_id           | 1000023
app_short            | fd
country              | NULL
segment              | MySegment_US
slice1               | NULL
slice2               | NULL
slice3               | NULL
slice4               | NULL
cohort_date          | 2026-01-30
metric_crit_category | WARNING
current_value        | 3
reference_value      | 5
reference_value_ci   | NULL
change_perc          | -0.40
is_alert             | TRUE
alert_category       | WARNING
```

### Полезные запросы

```sql
-- Все алерты за последние 7 дней
SELECT * FROM ma_data.incent_opex_check_universal
WHERE date >= CURRENT_DATE - 7 AND is_alert = TRUE
ORDER BY date DESC;

-- Алерты по конкретной проверке
SELECT * FROM ma_data.incent_opex_check_universal
WHERE check_name = '01-incent.cr' AND is_alert = TRUE
ORDER BY date DESC;

-- Статистика алертов по приложениям
SELECT app_short, partner_id, COUNT(*) as alert_count
FROM ma_data.incent_opex_check_universal
WHERE is_alert = TRUE AND date >= CURRENT_DATE - 30
GROUP BY app_short, partner_id
ORDER BY alert_count DESC;

-- Алерты по партнёру
SELECT * FROM ma_data.incent_opex_check_universal
WHERE partner_id = 1000023 AND is_alert = TRUE
ORDER BY date DESC;
```
