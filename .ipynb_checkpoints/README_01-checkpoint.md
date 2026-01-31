# 01-incent.opex.check_conversion_rates

Мониторинг конверсий (Conversion Rate) для incent-партнёров с использованием статистических методов.

---

## Назначение

Скрипт выявляет **статистически значимые изменения** в конверсии (CR = users / installs) по сравнению с:
- **Previous week** — предыдущая неделя
- **Historical average** — среднее за 4 недели до текущей

Алерт срабатывает при значительном отклонении CR (как вверх, так и вниз).

---

## Входные параметры

### Из Google Sheet (строка с `name = "01-incent.cr"`)

| Параметр | Поле в Sheet | Описание |
|----------|--------------|----------|
| `ALERT_ACTIVE_FLAG` | `active_flag` | `Enabled` / `Disabled` — включение нотификаций |
| `N_SIGMAS` | `n_sigmas` | Количество сигм для доверительного интервала (например, 3.0) |
| `MIN_INSTALLS` | `threshold_installs` | Минимум инсталлов для включения в анализ |
| `MIN_USERS` | `threshold_fixed` | Минимум юзеров для включения в анализ |
| `ALERT_CATEGORY` | `metric_crit_category` | Категория алерта (например, `info`) |

### Из JSON (`config_json`)

```json
{
  "partner_id": "1000023",
  "countries": ["US", "GB", "DE"],
  "check_countries": true,
  "method": "INTERVALS",
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
| `method` | Метод проверки: `Z_TEST` или `INTERVALS` |
| `cw` | Настройки по Conversion Windows (7, 30, 90 дней) |
| `cw.{N}.default` | Уровни (levels) по умолчанию для CW=N |
| `cw.{N}.exceptions` | Исключения: для конкретных приложений свои levels |

---

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

### 2. SQL-запрос

Данные берутся из `ma_data.vinokurov_cr_data`:
- Фильтрация по `partner_id`, `countries`, `cw`, `levels`
- Агрегация: `SUM(unique_user_count)`, `SUM(installs)`
- Расчёт CR для каждого периода

### 3. Фильтрация по порогам

Строки исключаются, если:
```
curr_installs < MIN_INSTALLS OR prev_installs < MIN_INSTALLS
curr_users < MIN_USERS OR prev_users < MIN_USERS
```

### 4. Статистические методы

#### Метод Z_TEST

Рассчитывается Z-score:
```
Z = (CR_current - CR_baseline) / SE
SE = sqrt(CR_baseline * (1 - CR_baseline) / n_current)
```

**Алерт срабатывает если:** `|Z| > N_SIGMAS`

#### Метод INTERVALS

Рассчитываются доверительные интервалы (CI):
```
CI = CR ± Z * SE
```

**Алерт срабатывает если:** интервалы не пересекаются
```
curr_ci_high < baseline_ci_low  OR  curr_ci_low > baseline_ci_high
```

### 5. Типы алертов

| Флаг | Сравнение | Описание |
|------|-----------|----------|
| `is_alert_prev` | Current vs Previous | Изменение относительно прошлой недели |
| `is_alert_hist` | Current vs Historical | Изменение относительно 4-недельного среднего |
| `is_alert_any` | Любой из выше | Объединённый флаг |

---

## Выходные метрики

### Таблица `ma_data.incent_opex_check_cr`

| Колонка | Тип | Описание |
|---------|-----|----------|
| `date` | TIMESTAMP | Дата/время запуска проверки |
| `check_name` | VARCHAR | `"01-incent.cr"` |
| `check_method` | VARCHAR | `"Z_TEST"` или `"INTERVALS"` |
| `metric_crit_category` | VARCHAR | Категория алерта |
| `app` | VARCHAR | Название приложения |
| `store` | VARCHAR | Магазин (ios/android) |
| `country` | VARCHAR | Страна или `"ALL"` |
| `level` | INTEGER | Уровень в воронке |
| `cw` | INTEGER | Conversion Window (7/30/90) |
| `cohort_date` | DATE | Дата когорты |
| `current_cr` | FLOAT | CR за текущую неделю |
| `curr_ci_low` | FLOAT | Нижняя граница CI для current |
| `curr_ci_high` | FLOAT | Верхняя граница CI для current |
| `is_alert_prev` | BOOLEAN | Алерт vs previous week |
| `previous_cr` | FLOAT | CR за предыдущую неделю |
| `prev_ci_low` | FLOAT | Нижняя граница CI для previous |
| `prev_ci_high` | FLOAT | Верхняя граница CI для previous |
| `z_score_prev` | FLOAT | Z-score vs previous |
| `is_alert_hist` | BOOLEAN | Алерт vs historical |
| `historical_cr` | FLOAT | CR за 4 недели (среднее) |
| `hist_ci_low` | FLOAT | Нижняя граница CI для historical |
| `hist_ci_high` | FLOAT | Верхняя граница CI для historical |
| `z_score_hist` | FLOAT | Z-score vs historical |

---

## Slack-нотификации

**Группировка:** по `app` + `store`

**Формат основного сообщения:**
```
INCENT.OpEx - 01-incent.cr (info): *SOLITAIRE (ios)*:
 ⬆️ Lvl 1 (cw 7) | CR: 12.34% | Prev (+5.2%), Hist (+3.1%)
 ⬇️ Lvl 2 (cw 30) | CR: 8.45% | Hist (-4.8%)
```

**Thread:** детализация по странам (если `check_countries = true`)

---

## Источник данных

```sql
SELECT * FROM ma_data.vinokurov_cr_data
WHERE partner_id = '...'
  AND country IN (...)
  AND cw = ...
  AND level IN (...)
  AND cohort_date BETWEEN '...' AND '...'
```
