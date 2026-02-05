# 03-incent.opex.check_metrics

Мониторинг операционных метрик для incent-партнёров с использованием CI-based алертов.

## Назначение

Проверяет 6 метрик эффективности incent-кампаний:

| Метрика | Описание | Формула |
|---------|----------|---------|
| **cpb3** | Стоимость привлечения плательщика (3 дня) | spend / payers_3 |
| **cpb7** | Стоимость привлечения плательщика (7 дней) | spend / payers_7 |
| **c2p3** | Конверсия в плательщика (3 дня) | payers_3 / installs |
| **c2p7** | Конверсия в плательщика (7 дней) | payers_7 / installs |
| **ret3** | Retention (3 дня) | active_users_3 / installs |
| **ret7** | Retention (7 дней) | active_users_7 / installs |

Алерт срабатывает при статистически значимом отклонении от reference-периода.

## Источник данных

```sql
SELECT * FROM core.base_metrics
WHERE partner_id IN (...)
  AND install_dt BETWEEN '...' AND '...'
```

**Используемые поля:**
- `app_short` — название приложения
- `partner_id` — ID партнёра
- `operation_segment_nm` — сегмент оперирования
- `country_cd` — код страны
- `install_dt` — дата установки
- `spend_discounted_usd_amt` — расходы (USD)
- `payers_3_cnt`, `payers_7_cnt` — флаги плательщика
- `installs_cnt` — количество инсталлов
- `user_activity_3_cnt`, `user_activity_7_cnt` — флаги активности

## Входные параметры

### Из Google Sheet (строка с `name = "03-incent.metrics"`)

| Параметр | Поле в Sheet | Описание |
|----------|--------------|----------|
| Активность | `active_flag` | `Enabled` / `Disabled` |
| Кол-во сигм | `n_sigmas` | Количество сигм для CI (рекомендуется 2.5) |
| Мин. инсталлов | `threshold_installs` | Минимум инсталлов для анализа |
| Мин. событий | `threshold_fixed` | Минимум payers (для cpb, c2p) или active_users (для ret) |
| Категория | `metric_crit_category` | Категория алерта (`INFO`, `WARNING`, `CRITICAL`) |
| Нотификации | `notification_flag` | Включить Slack-нотификации |

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

## Логика работы

### 1. Расчёт периодов

| Окно | Current (когорты) | Reference (когорты) |
|------|-------------------|---------------------|
| 3d | 3 дня, закрытые 3+ дней назад | 14 дней до current |
| 7d | 3 дня, закрытые 7+ дней назад | 14 дней до current |

**Пример для today = 2026-02-05:**

**Метрики 3d:**
- Current: 2026-01-31 — 2026-02-02 (3 дня)
- Reference: 2026-01-17 — 2026-01-30 (14 дней)

**Метрики 7d:**
- Current: 2026-01-27 — 2026-01-29 (3 дня)
- Reference: 2026-01-13 — 2026-01-26 (14 дней)

### 2. Расчёт CI

| Метрика | Тип | Формула CI |
|---------|-----|------------|
| cpb3, cpb7 | ratio | `z × value × sqrt((1 + cv²) / n)` |
| c2p3, c2p7 | binomial | `z × sqrt(p × (1-p) / n)` |
| ret3, ret7 | binomial | `z × sqrt(p × (1-p) / n)` |

Где:
- `z` — количество сигм (n_sigmas из конфига)
- `cv` — коэффициент вариации (по умолчанию 0.5)
- `n` — размер выборки (installs для binomial, payers для ratio)

### 3. Логика алертов

```
is_alert = (current_value < reference_value - ci) OR
           (current_value > reference_value + ci)
```

### 4. Фильтрация по threshold

Срезы игнорируются, если **в любом из периодов** (current ИЛИ reference) не выполняются условия:

| Параметр | Условие |
|----------|---------|
| `threshold_installs` | installs >= threshold в обоих периодах |
| `threshold_fixed` | payers >= threshold (cpb, c2p) или active_users >= threshold (ret) в обоих периодах |

### 5. Срезы данных

Данные агрегируются по:
- `app_short` — приложение
- `partner_id` — партнёр
- `operation_segment_nm` — сегмент
- `country_cd` — страна + `ALL` (агрегация по всем странам)

## Выходные данные

Записываются в `ma_data.incent_opex_check_universal`:

| Поле | Значение |
|------|----------|
| `check_name` | `03-incent.metrics` |
| `metric` | `cpb3`, `cpb7`, `c2p3`, `c2p7`, `ret3`, `ret7` |
| `partner_id` | ID партнёра |
| `app_short` | Название приложения |
| `country` | `country_cd` или `ALL` |
| `segment` | `operation_segment_nm` |
| `slice1-4` | `NULL` (не используются) |
| `cohort_date` | Дата окончания current периода |
| `current_value` | Текущее значение метрики |
| `reference_value` | Reference значение |
| `reference_value_ci` | Ширина CI |
| `change_perc` | Относительное изменение |
| `is_alert` | `TRUE` если выход за CI |
| `alert_category` | `WARNING` если алерт, иначе `NULL` |

## Slack-нотификации

Формат сообщения:
```
INCENT.OpEx - 03-incent.metrics (INFO): *AdJoe*

Тред:
↑ FD | ALL | Segment_US | cpb3: $12.50 (+15.2%)
↓ FD | US | Segment_US | c2p7: 2.35% (-8.1%)
```

## Пример конфигурации в Google Sheets

| Поле | Значение |
|------|----------|
| name | `03-incent.metrics` |
| active_flag | `Enabled` |
| run | `daily` |
| n_sigmas | `2.5` |
| threshold_installs | `100` |
| threshold_fixed | `0` |
| threshold_fixed_crit | `0` |
| metric_crit_category | `INFO` |
| notification_flag | `Enabled` |
| config_json | `{"partners": {"1000023": "AdJoe", ...}}` |
