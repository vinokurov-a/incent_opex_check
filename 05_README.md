
# 05-incent.ret

Мониторинг Retention для incent-партнёров.

## Назначение

| Ноутбук | Конфиг (name) | Метрики |
|---------|---------------|---------|
| `05-incent.opex.check_ret.ipynb` | `05-incent.ret` | ret3, ret7 |

| Метрика | Описание | Формула |
|---------|----------|---------|
| **ret3** | Retention (3 дня) | active_users_3 / installs |
| **ret7** | Retention (7 дней) | active_users_7 / installs |

Алерт срабатывает при статистически значимом отклонении от reference-периода.

## Источник данных

```sql
SELECT app_short, partner_id, operation_segment_nm, country_cd, install_dt,
       installs_cnt, user_activity_3_cnt, user_activity_7_cnt
FROM core.base_metrics
WHERE partner_id IN (...)
  AND install_dt BETWEEN '...' AND '...'
```

## Входные параметры

### Из Google Sheet (строка с `name = "05-incent.ret"`)

| Параметр | Поле в Sheet | Описание |
|----------|--------------|----------|
| Активность | `active_flag` | `Enabled` / `Disabled` |
| Кол-во сигм | `n_sigmas` | Количество сигм для CI (рекомендуется 2.5) |
| Мин. инсталлов | `threshold_installs` | Минимум инсталлов для анализа |
| Мин. active_users | `threshold_conv` | Минимум active_users в обоих периодах |
| Категория | `metric_crit_category` | Категория алерта (`INFO`, `WARNING`, `CRITICAL`) |
| Критерий | `criteria` | Критерий алерта: `ci` (по CI) или `change` (по % изменения) |
| Порог WARNING | `threshold_warning` | Порог WARNING для criteria=change (доля, напр. 0.1 = 10%) |
| Порог CRITICAL | `threshold_crit` | Порог CRITICAL для criteria=change (доля, напр. 0.2 = 20%) |
| Нотификации | `notification_flag` | Включить Slack-нотификации |

### Из JSON (`config_json`)

```json
{
  "partners": {
    "1000023": "AdJoe",
    "69680625": "Mistplay"
  }
}
```

## Логика работы

### 1. Расчёт периодов

| Окно | Current (когорты) | Reference (когорты) |
|------|-------------------|---------------------|
| 3d (ret3) | 3 дня, закрытые 4+ дней назад | 14 дней до current |
| 7d (ret7) | 3 дня, закрытые 8+ дней назад | 14 дней до current |

### 2. Расчёт CI

| Метрика | Тип | Формула CI |
|---------|-----|------------|
| ret3, ret7 | binomial | `z × sqrt(p × (1-p) / n)` |

Где:
- `z` — количество сигм (n_sigmas из конфига)
- `p` — reference значение retention
- `n` — количество installs в reference периоде

### 3. Логика алертов

Поддерживаются два критерия (параметр `criteria`):

**criteria = ci** (по умолчанию):
```
is_alert = (current_value < reference_value - ci) OR
           (current_value > reference_value + ci)
alert_category = WARNING
```

**criteria = change**:

**Алерт срабатывает только если выполнены ОБА условия:**

1. **Превышен threshold изменения:**
   ```
   abs(change_perc) >= threshold_warning
   ```

2. **Текущее значение НЕ в доверительном интервале:**
   ```
   (current_value < reference_value - ci) OR
   (current_value > reference_value + ci)
   ```

**Результат:**
```
is_alert = (abs(change_perc) >= threshold_warning) AND ci_condition

alert_category = CRITICAL  если (abs(change_perc) >= threshold_crit) AND ci_condition
                 WARNING   если (abs(change_perc) >= threshold_warning) AND ci_condition
                 NULL      иначе
```

**Эффект:** Отфильтровываются изменения, которые превышают threshold, но находятся в пределах статистической нормы (доверительного интервала).

### 4. Фильтрация по threshold

Срезы игнорируются, если **в любом из периодов** (current ИЛИ reference) не выполняются условия:

| Параметр | Условие |
|----------|---------|
| `threshold_installs` | installs >= threshold в обоих периодах |
| `threshold_conv` | active_users >= threshold в обоих периодах |

### 5. Срезы данных

Данные агрегируются по: `app_short`, `partner_id`, `operation_segment_nm`, `country_cd` + `ALL`

## Выходные данные

Записываются в `ma_data.incent_opex_check_universal`:

| Поле | Значение |
|------|----------|
| `check_name` | `05-incent.ret` |
| `metric` | `ret3`, `ret7` |
| `current_value` | Текущее значение Retention (доля) |
| `reference_value` | Reference значение Retention |
| `reference_value_ci` | Ширина CI |
| `change_perc` | Относительное изменение |
| `is_alert` | `TRUE` если выход за CI |
| `alert_category` | `WARNING` если алерт, иначе `NULL` |

## Slack-нотификации

```
INCENT.OpEx - 05-incent.ret (INFO), Retention: 🔴 *AdJoe*

Тред:
🔺 FD | ALL | Segment_US | ret3: 45.20% (+3.1%)
🔻 FD | US | Segment_US | ret7: 32.80% (-6.5%)
```
