# Универсальная таблица проверок

## ma_data.incent_opex_check_universal

Универсальная таблица для хранения результатов всех проверок OpEx. Каждая строка представляет одну проверку (алерт) для конкретной комбинации измерений.

### Структура таблицы

| Поле | Тип данных | Описание |
|------|------------|----------|
| `date` | TIMESTAMP | Дата и время выполнения проверки |
| `check_name` | VARCHAR(100) | Идентификатор проверки (например, `01-incent.cr`, `02-incent.p7`) |
| `metric` | VARCHAR(50) | Название проверяемой метрики (например, `previous_cr`, `historical_cr`, `payers_7d`) |
| `app` | VARCHAR(100) | Название приложения |
| `store` | VARCHAR(50) | Магазин (`gp`, `ios`, `huawei` и т.д.) |
| `slice1` | VARCHAR(100) | Первый срез данных. Значение зависит от типа проверки |
| `slice2` | VARCHAR(100) | Второй срез данных. Значение зависит от типа проверки |
| `slice3` | VARCHAR(100) | Третий срез данных. Значение зависит от типа проверки |
| `slice4` | VARCHAR(100) | Четвёртый срез данных (резерв). `NULL` если не используется |
| `cohort_date` | DATE | Дата когорты или периода, к которому относится проверка |
| `metric_crit_category` | VARCHAR(50) | Категория критичности (`INFO`, `WARNING`, `CRITICAL`) |
| `current_value` | FLOAT | Текущее значение метрики |
| `reference_value` | FLOAT | Эталонное (reference) значение для сравнения |
| `reference_value_ci` | FLOAT | Ширина доверительного интервала для reference-значения |
| `change_perc` | FLOAT | Относительное изменение: `(current_value - reference_value) / reference_value` |
| `alert_category` | VARCHAR(50) | Категория алерта (`WARNING`, `CRITICAL`, `NULL` если не применимо) |
| `is_alert` | BOOLEAN | Флаг срабатывания алерта (`TRUE` если current_value вне диапазона reference ± ci) |

### Использование полей slice1-slice4

Поля `slice1`-`slice4` используются для хранения измерений, специфичных для каждого типа проверки:

#### 01-incent.cr (Conversion Rate)
| Поле | Значение |
|------|----------|
| `metric` | `previous_cr` или `historical_cr` |
| `slice1` | `country` — страна (`US`, `DE`, `ALL` и т.д.) |
| `slice2` | `level` — уровень конверсии (`1`, `7`, `30` и т.д.) |
| `slice3` | `cw` — calendar week (`7`, `30`, `90`) |
| `slice4` | Не используется (`NULL`) |

#### 02-incent.p7 (Payers 7 days)
| Поле | Значение |
|------|----------|
| `metric` | `payers_1w` (WARNING) или `payers_4w` (CRITICAL) |
| `slice1` | `partner_id` — ID партнёра |
| `slice2` | `operation_segment_nm` — название сегмента оперирования |
| `slice3` | `partner_name` — название партнёра |
| `slice4` | Не используется (`NULL`) |
| `alert_category` | `WARNING` или `CRITICAL` |

**Примечание для 02-incent.p7:**
- `current_value` — количество плательщиков (за 1 или 4 недели)
- `reference_value` — пороговое значение (threshold)
- `reference_value_ci` — `NULL` (не применимо для threshold-based проверок)
- `change_perc` — насколько ниже порога: `(current - threshold) / threshold`

#### Шаблон для новых проверок
| Проверка | slice1 | slice2 | slice3 | slice4 |
|----------|--------|--------|--------|--------|
| 03-incent.ltv | country | cohort_week | - | - |

### Логика алертов

Алерт срабатывает (`is_alert = TRUE`), если текущее значение выходит за пределы доверительного интервала reference-значения:

```
is_alert = (current_value < reference_value - reference_value_ci) OR
           (current_value > reference_value + reference_value_ci)
```

Где `reference_value_ci = N_SIGMAS * sqrt(reference_value * (1 - reference_value) / n)`

### SQL для создания таблицы

```sql
CREATE TABLE IF NOT EXISTS ma_data.incent_opex_check_universal (
    date TIMESTAMP,
    check_name VARCHAR(100),
    metric VARCHAR(50),
    app VARCHAR(100),
    store VARCHAR(50),
    slice1 VARCHAR(100),
    slice2 VARCHAR(100),
    slice3 VARCHAR(100),
    slice4 VARCHAR(100),
    cohort_date DATE,
    metric_crit_category VARCHAR(50),
    current_value FLOAT,
    reference_value FLOAT,
    reference_value_ci FLOAT,
    change_perc FLOAT,
    alert_category VARCHAR(50),
    is_alert BOOLEAN
);

GRANT SELECT, INSERT, UPDATE, DELETE ON ma_data.incent_opex_check_universal TO PUBLIC;
```

### Примеры записей

#### 01-incent.cr
```
date                 | 2026-02-04 10:30:00
check_name           | 01-incent.cr
metric               | previous_cr
app                  | myapp
store                | gp
slice1               | US
slice2               | 7
slice3               | 30
slice4               | NULL
cohort_date          | 2026-01-20
metric_crit_category | INFO
current_value        | 0.42
reference_value      | 0.50
reference_value_ci   | 0.03
change_perc          | -0.16
alert_category       | NULL
is_alert             | TRUE
```

#### 02-incent.p7
```
date                 | 2026-02-04 11:00:00
check_name           | 02-incent.p7
metric               | payers_1w
app                  | myapp
store                | NULL
slice1               | 1000023
slice2               | MySegment_US
slice3               | AdJoe
slice4               | NULL
cohort_date          | 2026-01-30
metric_crit_category | WARNING
current_value        | 3
reference_value      | 5
reference_value_ci   | NULL
change_perc          | -0.40
alert_category       | WARNING
is_alert             | TRUE
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
SELECT app, store, COUNT(*) as alert_count
FROM ma_data.incent_opex_check_universal
WHERE is_alert = TRUE AND date >= CURRENT_DATE - 30
GROUP BY app, store
ORDER BY alert_count DESC;
```
