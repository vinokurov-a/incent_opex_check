# env.py

Утилитный модуль проекта **incent_opex_check**. Содержит функции для работы с Google Sheets, Amazon Redshift и Slack.

## Зависимости

| Пакет | Назначение |
|-------|-----------|
| `boto3` | Доступ к AWS Secrets Manager |
| `google-api-python-client` | Google Sheets API |
| `google-auth` | Авторизация через service account |
| `pandas`, `numpy` | Работа с данными |
| `awswrangler` | Подключение и запись в Redshift |
| `requests` | HTTP-запросы (Slack) |
| `IPython` | Отображение HTML в Jupyter |

## Конфигурация

| Константа | Значение | Описание |
|-----------|----------|----------|
| `SHEET_ID` | `1WuK3ixn...` | ID Google-таблицы с конфигурацией |
| `SHEET_NAME` | `config` | Имя листа конфигурации |
| `SECRET_ID_GOOGLE` | `jupyterhub/.../google-doc-api.json` | Путь к секрету Google в AWS Secrets Manager |
| `secret_id` (Redshift) | `jupyterhub/.../rs_credentials.json` | Путь к секрету Redshift в AWS Secrets Manager |

## Функции

### Google Sheets

| Функция | Описание |
|---------|----------|
| `get_gservice()` | Создает и кэширует подключение к Google Sheets. Получает credentials из AWS Secrets Manager по `JUPYTERHUB_USER`. |
| `get_google_service(creds_json, scopes)` | Низкоуровневая авторизация: принимает JSON credentials и scopes, возвращает объект `service`. |
| `read_spreadsheet(service, spreadsheet_id, sheet_name)` | Читает данные из указанного листа таблицы. Возвращает сырой ответ API. |
| `write_spreadsheet(service, spreadsheet_id, sheet_name, value_range_body)` | Записывает данные в указанный лист. Использует `USER_ENTERED` для автоформатирования значений. |
| `read_df_from_spreadsheet(service, spreadsheet_id, sheet_name, skip_rows, columns_range, column_names)` | Читает лист и возвращает `pd.DataFrame`. Первая строка по умолчанию используется как заголовки (`skip_rows=1`). |
| `clear_spreadsheet(service, spreadsheet_id, sheet_name)` | Очищает все данные в указанном листе. |
| `read_spreadsheet_metadata(service, spreadsheet_id, sheet_name)` | Возвращает метаданные таблицы (структура листов, свойства). |

### Redshift

| Функция | Описание |
|---------|----------|
| `execute_sql(query)` | Выполняет SELECT-запрос и возвращает результат как `pd.DataFrame`. |
| `execute_pg(query)` | Выполняет запрос без возврата данных (INSERT, UPDATE, DELETE, DDL) с автоматическим `commit`. |
| `insert_rows_into_rs(df, table_name, schema_name)` | Вставляет DataFrame в таблицу Redshift через `wr.redshift.to_sql`. |
| `insert_table_into_rs(df, table_name, schema_name, batch_size)` | Вставляет DataFrame батчами указанного размера. Выводит прогресс и время выполнения. |

### Утилиты

| Функция | Описание |
|---------|----------|
| `reduce_mem_usage(df)` | Оптимизирует типы данных колонок DataFrame для снижения потребления памяти. Приводит int/float к минимально достаточному типу. |

### Slack

| Класс / Метод | Описание |
|----------------|----------|
| `SlackNotifier(channel_name, slack_server_url)` | Клиент для отправки сообщений в Slack через прокси `slackproxy.local.playrix.com`. |
| `SlackNotifier.send_message(text, thread_ts)` | Отправляет сообщение в канал. Параметр `thread_ts` позволяет отвечать в тред. Возвращает `ts` сообщения или `None` при ошибке. |
