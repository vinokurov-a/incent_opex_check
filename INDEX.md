# INCENT OpEx Check

Система мониторинга операционных метрик для incent-партнёров.

---

## Структура проекта

| Ноутбук | Назначение | Документация |
|---------|------------|--------------|
| `00-incent.opex.check_main.ipynb` | Оркестратор: запуск проверок по расписанию | [00_README.md](00_README.md) |
| `01-incent.opex.check_conversion_rates.ipynb` | Проверка конверсий (CR) | [01_README.md](01_README.md) |
| `02-incent.opex.check_payers7.ipynb` | Проверка плательщиков (payers_7) | [02_README.md](02_README.md) |
| `99-incent.opex.slack_notify.ipynb` | Отправка Slack-нотификаций | [99_README.md](99_README.md) |
| `env.py` | Модуль для работы с Google Sheets, Redshift и Slack | [env_README.md](env_README.md) |

**Универсальная таблица результатов:** `ma_data.incent_opex_check_universal` (см. [DATABASE.md](DATABASE.md))

# Требования

- Python 3.9+
- `papermill` — для запуска ноутбуков

---

# Добавление новой проверки

1. Создайте ноутбук `XX-incent.opex.check_<name>.ipynb`
2. Добавьте строку в Google Sheets с `name` = `XX-incent.<short_name>`
3. Добавьте маппинг в `NOTEBOOK_MAP` в `00-incent.opex.check_main.ipynb`
4. Записывайте результаты в `ma_data.incent_opex_check_universal` (см. [DATABASE.md](DATABASE.md))
5. Добавьте функцию отправки нотификаций в `99-incent.opex.slack_notify.ipynb`