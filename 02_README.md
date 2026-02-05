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
| `THRESHOLD_WARNING` | `threshold_conv` | Порог для WARNING (за 1 неделю) |
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

**Лаг для созревания данных:** минимум 8 дней после окончания периода (чтобы `payers_7` успели "созреть").

| Период | Дни | Использование |
|--------|-----|---------------|
| Текущая неделя | 7 дней | WARNING |
| 4 недели | 28 дней | CRITICAL |

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
| `metric` | `payers_1w` (WARNING) или `payers_4w` (CRITICAL) |
| `slice1` | `partner_id` |
| `slice2` | `operation_segment_nm` |
| `slice3` | `partner_name` |
| `current_value` | Количество плательщиков |
| `reference_value` | Пороговое значение (threshold) |
| `reference_value_ci` | `NULL` (не применимо) |
| `change_perc` | `(current - threshold) / threshold` |
| `is_alert` | `TRUE` / `FALSE` |
| `alert_category` | `WARNING` / `CRITICAL` / `NULL` |

## Условия алертов

| Тип | Условие | Период | Интерпретация |
|-----|---------|--------|---------------|
| **WARNING** | `payers_count < THRESHOLD_WARNING` | 1 неделя | Возможная просадка |
| **CRITICAL** | `payers_count_4w < THRESHOLD_CRITICAL` | 4 недели | Устойчивая проблема |

## Источник данных

```sql
SELECT * FROM core.base_metrics
WHERE partner_id IN (...)
  AND install_dt BETWEEN '...' AND '...'
  AND operation_segment_nm IN (SELECT ... FROM operation_segments.segments_parameters WHERE ...)
```

Метрика `payers_7_cnt = 1` означает, что пользователь совершил платёж в течение 7 дней после установки.