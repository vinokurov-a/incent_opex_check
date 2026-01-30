import pickle
import os
import boto3
from googleapiclient.discovery import build
#from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pandas as pd
import numpy as np
import datetime
from datetime import datetime, timedelta
import awswrangler as wr

import requests
import json

from IPython.display import display, HTML

# slack
import logging
from typing import Optional
import requests

# Sheet-Config
SHEET_ID = "1WuK3ixnfnemA8N5RT8AZCYsuPaxekOrIBcsek7GOltc"
SHEET_NAME = "config"

# Authentification google
SECRET_ID_GOOGLE = 'jupyterhub/{}/airflow/google-doc-api.json'.format('vinokurov-a')

_CACHED_GSERVICE = None

def get_gservice():
    """
    Создает подключение к Google Sheets только тогда, когда это действительно нужно.
    """
    global _CACHED_GSERVICE
    
    if _CACHED_GSERVICE is not None:
        return _CACHED_GSERVICE

    try:
        # 1. Получаем пользователя (чтобы не хардкодить vinokurov-a)
        jupyter_user = os.environ.get("JUPYTERHUB_USER", "vinokurov-a")
        
        # 2. Получаем секреты из AWS
        secret_id = f'jupyterhub/{jupyter_user}/airflow/google-doc-api.json'
        client = boto3.client('secretsmanager')
        secret_value = client.get_secret_value(SecretId=secret_id)['SecretString']
        aws_creds = json.loads(secret_value)
        
        # 3. Авторизуемся в Google
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        _CACHED_GSERVICE = get_google_service(aws_creds, scopes)
        
        print("Google Service успешно инициализирован.")
        return _CACHED_GSERVICE
        
    except Exception as e:
        print(f"Ошибка при создании Google Service: {e}")
        return None

# Authentification RS
secret_id = 'jupyterhub/{}/airflow/rs_credentials.json'.format('vinokurov-a')
# secret_id = "jupyterhub/{}/rs_credentials.json".format(os.environ["JUPYTERHUB_USER"])

# -- GOOGLE --
def get_google_service(creds_json, scopes):
    # Аутентификация с использованием JSON-credentials
    credentials = service_account.Credentials.from_service_account_info(creds_json, scopes=scopes)
    if credentials.expired:
        credentials.refresh(Request())
    service = build('sheets', 'v4', credentials=credentials)
    return service

def read_spreadsheet(service, spreadsheet_id, sheet_name):
    return (
        service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=sheet_name
        ).execute()
    )
    
def write_spreadsheet(service, spreadsheet_id, sheet_name, value_range_body):
    return (
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=sheet_name, body=value_range_body,
            valueInputOption='USER_ENTERED',
            includeValuesInResponse = True
        ).execute()
    )

def read_df_from_spreadsheet(
    service,
    spreadsheet_id,
    sheet_name,
    skip_rows=1,
    columns_range=None,
    column_names=None,
):
    response = read_spreadsheet(service, spreadsheet_id, sheet_name)

    if column_names:
        columns = column_names
    else:
        columns = response['values'][0]

    return pd.DataFrame(
        (
            row[:len(columns)]
            for row in response['values'][skip_rows:]
        ),
        columns=columns
    )

def clear_spreadsheet(service, spreadsheet_id, sheet_name):
    clear_values_request_body = {}
    
    request = service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,
        body=clear_values_request_body
    )
    response = request.execute()
    return response

def read_spreadsheet_metadata(service, spreadsheet_id, sheet_name):
    return service.spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=sheet_name).execute()

# -- REDSHIFT --
def execute_sql(query):
    with wr.redshift.connect(secret_id=secret_id) as conn:
        df = wr.redshift.read_sql_query(query, con=conn)
    return df

def execute_pg(query):
    con = wr.redshift.connect(secret_id=secret_id)
    with con.cursor() as cursor:
        cursor.execute(query)
    con.commit()  
    con.close()
    #print('Success')

def insert_rows_into_rs(df,table_name,schema_name):
    con = wr.redshift.connect(secret_id=secret_id)
    wr.redshift.to_sql(
    df=df,
    table=table_name,
    schema=schema_name,
    con=con
    )
    con.close()

# Функция, генерирующая запрос insert into и вставляющая данные в Redshift
def insert_table_into_rs(df,table_name,schema_name, batch_size):
    st = datetime.now()
    for i in range(int(len(df)/batch_size)+1):
        if (i+1)*batch_size<len(df):
            insert_rows_into_rs(df.iloc[i*batch_size:(i+1)*batch_size], table_name, schema_name)
            print('Rows ', str(i*batch_size+1), '-', str((i+1)*batch_size), ' are inserted')
        else:
            insert_rows_into_rs(df.iloc[i*batch_size:len(df)], table_name, schema_name)
            print(str(len(df)), ' rows are inserted')
    print('Time taken to insert data into Redshift table ', str(table_name), ' = ', str(datetime.now() - st).split(".")[0])

def reduce_mem_usage(df):
    """ iterate through all the columns of a dataframe and modify the data type
        to reduce memory usage.
    """
    start_mem = df.memory_usage().sum() / 1024**2
    print('Memory usage of dataframe is {:.2f} MB'.format(start_mem))

    for col in df.columns:
        
        col_type = df[col].dtype.name

        if col_type not in ['object', 'category', 'datetime64[ns, UTC]', 'datetime64[ns]', 'boolean', 'string']:            
            c_min = df[col].min()
            c_max = df[col].max()
            if str(col_type)[:3] == 'Int':                
                if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:                    
                    df[col] = df[col].astype(np.int8)
                elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                    df[col] = df[col].astype(np.int16)
                elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                    df[col] = df[col].astype(np.int32)
                elif c_min > np.iinfo(np.int64).min and c_max < np.iinfo(np.int64).max:
                    df[col] = df[col].astype(np.int64)
            else:
                if c_min > np.finfo(np.float16).min and c_max < np.finfo(np.float16).max:
                    df[col] = df[col].astype(np.float16)
                elif c_min > np.finfo(np.float32).min and c_max < np.finfo(np.float32).max:
                    df[col] = df[col].astype(np.float32)
                else:
                    df[col] = df[col].astype(np.float64)

    end_mem = df.memory_usage().sum() / 1024**2
    print('Memory usage after optimization is: {:.2f} MB'.format(end_mem))
    print('Decreased by {:.1f}%'.format(100 * (start_mem - end_mem) / start_mem))

    return df    

pd.set_option('display.max_columns', 200)
pd.set_option('display.max_rows', 200)

# -- SLACK --
class SlackNotifier:
    def __init__(
        self,
        channel_name: str,
        slack_server_url: str = "https://slackproxy.local.playrix.com/",
    ) -> None:
        self._channel_name = channel_name
        self._slack_server_url = slack_server_url
  
    def send_message(self, text: str, thread_ts: Optional[str] = None) -> Optional[str]:
        url = f"{self._slack_server_url}send-message"
        try:
            response = requests.post(
                url,
                json=dict(text=text, channel=self._channel_name, thread_ts=thread_ts),
            )
            response.raise_for_status()
        except requests.RequestException as ex:
            response_text = getattr(ex.response, "text", "")
            if response_text:
                logging.error(response_text)
            return None
        else:
            response_json = response.json()
            return response_json.get("ts")