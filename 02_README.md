# 02-incent.opex.check_payers7

Мониторинг количества плательщиков (payers_7) для incent-партнёров с пороговыми алертами.

## Назначение

Проверяет **абсолютное количество плательщиков** за период и формирует алерты двух типов:
- **WARNING** — мало плательщиков за текущую неделю
- **CRITICAL** — мало плательщиков за 4 недели (устойчивый тренд)

## Входные параметры

### Из Google Sheet (строка с `name = "02-incent.p7"`)

| Параметр | Поле в Sheet | Описание |
|----------|--------------|----------|
| `ALERT_ACTIVE_FLAG` | `active_flag` | `Enabled` / `Disabled` — включение проверки |
| `THRESHOLD_WARNING` | `threshold_fixed` | Порог для WARNING (за 1 неделю) |
| `THRESHOLD_CRITICAL` | `threshold_fixed_crit` | Порог для CRITICAL (за 4 недели) |
| `ALERT_CATEGORY` | `metric_crit_category` | Категория алерта (например, `INFO`) |

### Из JSON (`config_json`)

```json
{
  "partners": {
    "1000023": "AdJoe",
    "69680625": "Mistplay",
    "15806": "TapJoy",
    "98667914": "Exmox",
    "71764608": "KashKick",
    "73925639": "Fluent"
  }
}
```

| Ключ | Описание |
|------|----------|
| `partners` | Словарь: `partner_id` → `partner_name` |

## Логика работы

### 1. Расчёт периодов

Неделя считается от **пятницы до четверга** (Fri-Thu).

**Лаг для созревания данных:** Проверяется последний четверг, для которого прошло **СТРОГО БОЛЬШЕ 7 дней** (т.е. >= 8 дней) — это гарантирует полное созревание метрики `payers_7`.

**Алгоритм:**
1. Находим последний четверг
2. Если между четвергом и сегодня прошло <= 8 дней → берем предыдущий четверг
3. period_end = этот четверг
4. period_start = четверг - 6 дней (пятница неделей ранее)
5. extended_start = period_start - 21 день (начало 4-недельного периода)

| Период | Дни | Использование |
|--------|-----|---------------|
| Текущая неделя (period_start → period_end) | 7 дней | WARNING |
| 4 недели (extended_start → period_end) | 28 дней | CRITICAL |

### 2. Определение типа алерта

```python
def get_alert_type(payers_1w, payers_4w):
    if payers_4w < THRESHOLD_CRITICAL:
        return 'CRITICAL'  # Приоритет выше
    elif payers_1w < THRESHOLD_WARNING:
        return 'WARNING'
    else:
        return None
```

**Приоритет:** CRITICAL > WARNING

## Выходные данные

Все результаты записываются в `ma_data.incent_opex_check_universal`:

| Поле | Значение |
|------|----------|
| `check_name` | `02-incent.p7` |
| `metric` | `payers_1w` (для WARNING и не-алертов) или `payers_4w` (для CRITICAL) |
| `partner_id` | ID партнёра (int) |
| `app_short` | Название приложения |
| `country` | `NULL` (не используется) |
| `segment` | `operation_segment_nm` |
| `slice1`, `slice2`, `slice3`, `slice4` | `NULL` (не используются) |
| `cohort_date` | `period_end` — дата окончания анализируемого периода (четверг) |
| `current_value` | Количество плательщиков (payers_count или payers_count_4w) |
| `reference_value` | Пороговое значение (THRESHOLD_WARNING или THRESHOLD_CRITICAL) |
| `reference_value_ci` | `NULL` (не применимо для threshold-based проверок) |
| `change_perc` | `(current - threshold) / threshold` |
| `is_alert` | `TRUE` / `FALSE` |
| `alert_category` | `WARNING` / `CRITICAL` / `NULL` |

## Условия алертов

| Тип | Условие | Период | Интерпретация |
|-----|---------|--------|---------------|
| **WARNING** | `payers_count < THRESHOLD_WARNING` | 1 неделя | Возможная просадка |
| **CRITICAL** | `payers_count_4w < THRESHOLD_CRITICAL` | 4 недели | Устойчивая проблема |

**Важно:** В БД записываются **ВСЕ** строки (и алерты, и не-алерты). Для не-алертов:
- `is_alert = FALSE`
- `alert_category = NULL`
- `metric = payers_1w` (используются 1-недельные данные)
- `current_value` = количество плательщиков за текущую неделю
- `reference_value` = THRESHOLD_WARNING

## Источник данных

### Активные сегменты оперирования

```sql
WITH active_segments AS (
    SELECT DISTINCT operation_segment
    FROM operation_segments.segments_parameters
    WHERE coverage_type = 'Рабочее'
      AND actual
      AND valid_to > CURRENT_DATE
      AND partner_id IN (1000023, 69680625, ...)
)
```

### Основной запрос

```sql
SELECT
    app_short,
    operation_segment_nm,
    partner_id,
    COUNT(DISTINCT CASE
        WHEN payers_7_cnt = 1 AND install_dt BETWEEN 'period_start' AND 'period_end'
        THEN plr_id
    END) as payers_count,
    COUNT(DISTINCT CASE
        WHEN payers_7_cnt = 1
        THEN plr_id
    END) as payers_count_4w
FROM core.base_metrics
WHERE
    install_dt BETWEEN 'extended_start' AND 'period_end'
    AND partner_id IN (1000023, 69680625, ...)
    AND operation_segment_nm IN (SELECT operation_segment FROM active_segments)
GROUP BY app_short, operation_segment_nm, partner_id
```

**Метрика:** `payers_7_cnt = 1` означает, что пользователь совершил платёж в течение 7 дней после установки.

## Примеры

### Пример 1: Сценарий с CRITICAL алертом

- payers_count (1 неделя) = 5
- payers_count_4w (4 недели) = 12
- THRESHOLD_WARNING = 10
- THRESHOLD_CRITICAL = 15

**Результат:**
- Алерт: `CRITICAL` (12 < 15)
- Записывается: `metric = payers_4w`, `current_value = 12`, `reference_value = 15`

### Пример 2: Сценарий с WARNING алертом

- payers_count (1 неделя) = 8
- payers_count_4w (4 недели) = 40
- THRESHOLD_WARNING = 10
- THRESHOLD_CRITICAL = 15

**Результат:**
- Алерт: `WARNING` (8 < 10, но 40 >= 15)
- Записывается: `metric = payers_1w`, `current_value = 8`, `reference_value = 10`

### Пример 3: Без алерта

- payers_count (1 неделя) = 12
- payers_count_4w (4 недели) = 50
- THRESHOLD_WARNING = 10
- THRESHOLD_CRITICAL = 15

**Результат:**
- Алерт: отсутствует
- Записывается: `metric = payers_1w`, `current_value = 12`, `reference_value = 10`, `is_alert = FALSE`