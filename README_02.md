# 02-incent.opex.check_payers7

Мониторинг количества плательщиков (payers_7) для incent-партнёров с пороговыми алертами.

---

## Назначение

Скрипт проверяет **абсолютное количество плательщиков** за период и формирует алерты двух типов:
- **WARNING** — мало плательщиков за текущую неделю
- **CRITICAL** — мало плательщиков за 4 недели (устойчивый тренд)

---

## Входные параметры

### Из Google Sheet (строка с `name = "02-incent.p7"`)

| Параметр | Поле в Sheet | Описание |
|----------|--------------|----------|
| `ALERT_ACTIVE_FLAG` | `active_flag` | `Enabled` / `Disabled` — включение нотификаций |
| `THRESHOLD_WARNING` | `threshold_fixed` | Порог для WARNING (за 1 неделю) |
| `THRESHOLD_CRITICAL` | `threshold_fixed_crit` | Порог для CRITICAL (за 4 недели) |
| `ALERT_CATEGORY` | `metric_crit_category` | Категория алерта (например, `info`) |

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

---

## Логика работы

### 1. Расчёт периодов

Неделя считается от **пятницы до четверга** (Fri-Thu).

**Лаг для созревания данных:** минимум 8 дней после окончания периода (чтобы `payers_7` успели "созреть").

```
Сегодня: 2024-01-31 (среда)
↓
Последний четверг: 2024-01-25
Дней прошло: 6 (< 8) → берём предыдущий четверг
↓
period_end: 2024-01-18 (четверг)
period_start: 2024-01-12 (пятница)
extended_start: 2023-12-22 (пятница, -21 день)
```

**Периоды:**
| Период | Дни | Использование |
|--------|-----|---------------|
| Текущая неделя | `period_start` — `period_end` (7 дней) | WARNING |
| 4 недели | `extended_start` — `period_end` (28 дней) | CRITICAL |

### 2. SQL-запрос

Данные берутся из `core.base_metrics`:

```sql
SELECT
    app_short,
    operation_segment_nm,
    partner_id,
    -- Плательщики за текущую неделю (для WARNING)
    COUNT(DISTINCT CASE
        WHEN payers_7_cnt = 1
        AND install_dt BETWEEN '{period_start}' AND '{period_end}'
        THEN plr_id
    END) as payers_count,
    -- Плательщики за 4 недели (для CRITICAL)
    COUNT(DISTINCT CASE
        WHEN payers_7_cnt = 1
        THEN plr_id
    END) as payers_count_4w,
    -- Инсталлы за текущую неделю
    SUM(CASE
        WHEN install_dt BETWEEN '{period_start}' AND '{period_end}'
        THEN installs_cnt ELSE 0
    END) as total_installs,
    -- Инсталлы за 4 недели
    SUM(installs_cnt) as total_installs_4w
FROM core.base_metrics
WHERE
    install_dt BETWEEN '{extended_start}' AND '{period_end}'
    AND partner_id IN (...)
GROUP BY app_short, operation_segment_nm, partner_id
```

### 3. Определение типа алерта

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

Если строка попадает под оба условия, присваивается CRITICAL.

### 4. Агрегация

Группировка по:
- `app_short` — приложение
- `operation_segment_nm` — операционный сегмент
- `partner_id` — партнёр

---

## Выходные метрики

### Таблица `ma_data.incent_opex_check_p7`

| Колонка | Тип | Описание |
|---------|-----|----------|
| `date` | TIMESTAMP | Дата/время запуска проверки |
| `check_name` | VARCHAR | `"02-incent.p7"` |
| `metric_crit_category` | VARCHAR | Категория алерта |
| `app_short` | VARCHAR | Название приложения |
| `operation_segment_nm` | VARCHAR | Операционный сегмент |
| `partner_id` | VARCHAR | ID партнёра |
| `partner_name` | VARCHAR | Название партнёра |
| `payers_count` | INTEGER | Плательщики за 1 неделю |
| `payers_count_4w` | INTEGER | Плательщики за 4 недели |
| `total_installs` | INTEGER | Инсталлы за 1 неделю |
| `total_installs_4w` | INTEGER | Инсталлы за 4 недели |
| `threshold_warning` | INTEGER | Порог WARNING |
| `threshold_critical` | INTEGER | Порог CRITICAL |
| `alert_type` | VARCHAR | `"WARNING"` или `"CRITICAL"` |
| `is_alert` | BOOLEAN | Флаг алерта |
| `period_start` | DATE | Начало текущей недели |
| `period_end` | DATE | Конец текущей недели |
| `extended_start` | DATE | Начало 4-недельного периода |

---

## Slack-нотификации

**Группировка:** по `partner_id` (одно сообщение на партнёра)

**Формат основного сообщения:**
```
🔴 INCENT.OpEx - 02-incent.p7 (info): *AdJoe*
```

**Thread (детали по app и сегментам):**
```
🔴 [CRITICAL] SOLITAIRE / Segment_A: 15 payers (4 нед., threshold: 50)
🟡 [WARNING] SOLITAIRE / Segment_B: 8 payers (1 нед., threshold: 10)
🟡 [WARNING] WORDS / Segment_A: 5 payers (1 нед., threshold: 10)
```

**Иконки:**
| Тип | Иконка | Описание |
|-----|--------|----------|
| CRITICAL | 🔴 `:red_circle:` | Мало payers за 4 недели |
| WARNING | 🟡 `:large_yellow_circle:` | Мало payers за 1 неделю |

**Сортировка в thread:** по `app_short`, затем по `alert_type` (CRITICAL первым)

---

## Условия алертов

| Тип | Условие | Период | Интерпретация |
|-----|---------|--------|---------------|
| **WARNING** | `payers_count < THRESHOLD_WARNING` | 1 неделя | Возможная просадка |
| **CRITICAL** | `payers_count_4w < THRESHOLD_CRITICAL` | 4 недели | Устойчивая проблема |

---

## Источник данных

```sql
SELECT * FROM core.base_metrics
WHERE partner_id IN (...)
  AND install_dt BETWEEN '...' AND '...'
```

Метрика `payers_7_cnt = 1` означает, что пользователь совершил платёж в течение 7 дней после установки.

---

## Пример сценария

```
THRESHOLD_WARNING = 10 (за 1 неделю)
THRESHOLD_CRITICAL = 50 (за 4 недели)

Данные:
- app: SOLITAIRE, segment: Premium, partner: AdJoe
- payers_count (1 нед): 8
- payers_count_4w (4 нед): 45

Результат:
→ payers_4w (45) < THRESHOLD_CRITICAL (50) → CRITICAL
```
