# 01-incent.opex.check_conversion_rates

Мониторинг конверсий (Conversion Rate) для incent-партнёров с использованием статистических методов.

## Назначение

Выявляет **статистически значимые изменения** в конверсии (CR = users / installs) по сравнению с:
- **Previous week** — предыдущая неделя
- **Historical average** — среднее за 4 недели до текущей

Алерт срабатывает при значительном отклонении CR (как вверх, так и вниз).

## Входные параметры

### Из Google Sheet (строка с `name = "01-incent.cr"`)

| Параметр | Поле в Sheet | Описание |
|----------|--------------|----------|
| `ALERT_ACTIVE_FLAG` | `active_flag` | `Enabled` / `Disabled` — включение проверки |
| `N_SIGMAS` | `n_sigmas` | Количество сигм для доверительного интервала (например, 3.0) |
| `MIN_INSTALLS` | `threshold_installs` | Минимум инсталлов для включения в анализ |
| `MIN_USERS` | `threshold_conv` | Минимум юзеров для включения в анализ |
| `ALERT_CATEGORY` | `metric_crit_category` | Категория алерта (например, `INFO`) |
| `CRITERIA` | `criteria` | Критерий алерта: `ci` (по CI) или `change` (по % изменения) |
| `THRESHOLD_WARNING_PCT` | `threshold_warning` | Порог WARNING для criteria=change (доля, напр. 0.1 = 10%) |
| `THRESHOLD_CRIT_PCT` | `threshold_crit` | Порог CRITICAL для criteria=change (доля, напр. 0.2 = 20%) |

### Из JSON (`config_json`)

```json
{
  "partner_id": "1000023",
  "countries": ["US", "GB", "DE"],
  "check_countries": true,
  "cw": {
    "7": {
      "default": [1, 2, 3],
      "exceptions": {
        "solitaire": [1, 2]
      }
    },
    "30": {
      "default": [1, 2, 3]
    },
    "90": {
      "default": [1, 2]
    }
  }
}
```

| Ключ | Описание |
|------|----------|
| `partner_id` | ID партнёра для фильтрации |
| `countries` | Список стран для анализа |
| `check_countries` | `true` — анализировать отдельно по странам + ALL; `false` — только ALL |
| `cw` | Настройки по Conversion Windows (7, 30, 90 дней) |
| `cw.{N}.default` | Уровни (levels) по умолчанию для CW=N |
| `cw.{N}.exceptions` | Исключения: для конкретных приложений свои levels |

## Логика работы

### 1. Расчёт периодов

Для каждого CW применяется свой лаг (время на "созревание" данных):

| CW | Lag (недель) | Описание |
|----|--------------|----------|
| 7  | 2 | Данные 2-недельной давности |
| 30 | 5 | Данные 5-недельной давности |
| 90 | 14 | Данные 14-недельной давности |

**Периоды:**
- `current_week` — текущая анализируемая неделя (Пн-Вс)
- `previous_week` — неделя перед current
- `historical` — 4 недели перед current (для расчёта среднего)

### 2. Логика алертов

Поддерживаются два критерия формирования алертов (параметр `criteria`):

#### criteria = ci (по умолчанию)

Рассчитывается доверительный интервал для reference-значения:
```
reference_ci = Z * sqrt(reference_cr * (1 - reference_cr) / n_reference)
```

**Алерт срабатывает если** `current_cr` выходит за пределы `[reference - ci, reference + ci]`:
```
is_alert = (current_cr < reference_cr - reference_ci) OR
           (current_cr > reference_cr + reference_ci)
```

| Метрика | alert_category | Описание |
|---------|----------------|----------|
| `previous_cr` | `WARNING` | Изменение относительно прошлой недели |
| `historical_cr` | `CRITICAL` | Изменение относительно 4-недельного среднего |

#### criteria = change

Алерт срабатывает если абсолютное значение `change_perc` превышает заданный порог:
```
is_alert = abs(change_perc) >= threshold_warning
alert_category = CRITICAL  если abs(change_perc) >= threshold_crit
                 WARNING   если abs(change_perc) >= threshold_warning
```

CI рассчитывается и записывается в БД, но не влияет на формирование алерта.

## Выходные данные

Все результаты записываются в `ma_data.incent_opex_check_universal`:

| Поле | Значение |
|------|----------|
| `check_name` | `01-incent.cr` |
| `metric` | `previous_cr` или `historical_cr` |
| `slice1` | country (`US`, `DE`, `ALL` и т.д.) |
| `slice2` | level (`1`, `7`, `30` и т.д.) |
| `slice3` | cw (`7`, `30`, `90`) |
| `current_value` | Текущее CR |
| `reference_value` | Reference CR |
| `reference_value_ci` | Ширина CI |
| `change_perc` | Относительное изменение |
| `alert_category` | `WARNING` / `CRITICAL` / `NULL` |
| `is_alert` | `TRUE` / `FALSE` |

## Источник данных

```sql
SELECT * FROM ma_data.vinokurov_cr_data
WHERE partner_id = '...'
  AND country IN (...)
  AND cw = ...
  AND level IN (...)
  AND cohort_date BETWEEN '...' AND '...'
```