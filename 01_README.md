# 01-incent.opex.check_conversion_rates

Мониторинг конверсий (Conversion Rate) для incent-партнёров с использованием статистических методов.

## Назначение

Выявляет **статистически значимые изменения** в конверсии (CR = users / installs) по сравнению с:
- **Previous week** — предыдущая неделя
- **Historical average** — среднее за 4 недели до текущей

Алерт срабатывает при значительном отклонении CR (как вверх, так и вниз).

## Структура проверок

Ноутбук обрабатывает **две независимые конфигурации**:

| Конфигурация | Reference тип | Описание |
|--------------|---------------|----------|
| `01-incent.cr_prev` | `previous_cr` | Сравнение с предыдущей неделей |
| `01-incent.cr_hist` | `historical_cr` | Сравнение со средним за 4 недели |

Каждая конфигурация может иметь:
- Свои threshold'ы (warning/critical)
- Свой критерий (ci/change)
- Свое значение n_sigmas

## Входные параметры

### Из Google Sheet (строки с `name = "01-incent.cr_prev"` и `"01-incent.cr_hist"`)

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
  "partners": {
    "0": "Organic",
    "1000023": "AdJoe"
  },
  "countries": ["US", "GB", "DE"],
  "check_countries": "TRUE",
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
| `partners` | Dict {partner_id: название} — несколько партнёров для одновременной проверки |
| `countries` | Список стран для анализа |
| `check_countries` | `"TRUE"` — анализировать отдельно по странам + ALL; `"FALSE"` — только ALL |
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

alert_category всегда `WARNING`.

#### criteria = change

**Алерт срабатывает только если выполнены ОБА условия:**

1. **Превышен threshold изменения:**
   ```
   abs(change_perc) >= threshold_warning
   ```

2. **Текущее значение НЕ в доверительном интервале:**
   ```
   (current_cr < reference_cr - reference_ci) OR
   (current_cr > reference_cr + reference_ci)
   ```

**Результат:**
```
is_alert = (abs(change_perc) >= threshold_warning) AND ci_condition

alert_category = CRITICAL  если abs(change_perc) >= threshold_crit AND ci_condition
                 WARNING   если abs(change_perc) >= threshold_warning AND ci_condition
                 NULL      иначе
```

**Эффект:** Отфильтровываются изменения, которые превышают threshold, но находятся в пределах статистической нормы (доверительного интервала).

## Выходные данные

Все результаты записываются в `ma_data.incent_opex_check_universal`:

| Поле | Значение |
|------|----------|
| `check_name` | `01-incent.cr` (общее для обеих проверок) |
| `metric` | `previous_cr` или `historical_cr` (различие по типу) |
| `partner_id` | ID партнёра (int) |
| `app_short` | Название приложения + суффикс магазина (_gp, _as) |
| `country` | Страна (`US`, `DE`, `ALL` и т.д.) |
| `slice1` | level (`1`, `7`, `30` и т.д.) |
| `slice2` | cw (`7`, `30`, `90`) |
| `cohort_date` | Дата начала анализируемой недели |
| `current_value` | Текущее CR |
| `reference_value` | Reference CR |
| `reference_value_ci` | Ширина CI |
| `change_perc` | Относительное изменение |
| `alert_category` | `WARNING` / `CRITICAL` / `NULL` |
| `is_alert` | `TRUE` / `FALSE` |

## Источник данных

```sql
SELECT * FROM ma_data.vinokurov_cr_data
WHERE partner_id IN (0, 1000023, ...)
  AND country IN ('US', 'DE', ...)
  AND cw = 7
  AND level IN (1, 2, 3, ...)
  AND cohort_date BETWEEN '2024-01-01' AND '2024-01-31'
```

## Примеры использования

### Пример 1: Разные критерии для prev и hist

**01-incent.cr_prev:**
- criteria = `change`
- threshold_warning = `0.15` (15%)
- threshold_crit = `0.30` (30%)

**01-incent.cr_hist:**
- criteria = `ci`
- n_sigmas = `3.0`

### Пример 2: Мониторинг нескольких партнёров

```json
{
  "partners": {
    "0": "Organic",
    "1000023": "AdJoe",
    "1000024": "Tapjoy"
  },
  "countries": ["US"],
  "check_countries": "FALSE"
}
```

Результат: одна проверка создаст записи для всех трёх партнёров.