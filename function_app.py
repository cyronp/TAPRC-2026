import csv
import io
import logging
import os
from datetime import datetime, timezone

import pyodbc
import azure.functions as func
from azure.storage.filedatalake import DataLakeServiceClient

app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 * * * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False
)
def extract_tables(myTimer: func.TimerRequest) -> None:
    
    def extract_tables_storage(table):
        
        logging.info(f"tabela {table}")

        sql_server = os.getenv("HOST_PROF")
        sql_database = os.getenv("DATABASE_PROF")
        sql_user = os.getenv("USER_PROF")
        sql_pass = os.getenv("PASSWORD_PROF")

        logging.info(
            f"servidor={sql_server}, banco de dados={sql_database}, usuario={sql_user}, senha={sql_pass} "
        )

        # Configura a string de conexão para o banco de dados SQL Server
        conn_str = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={sql_server};"
            f"DATABASE={sql_database};"
            f"UID={sql_user};"
            f"PWD={sql_pass};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30;"
        )

        try:
            with pyodbc.connect(conn_str) as conn:
                cursor = conn.cursor()
                query = f"select * from [itsm].[{table}]"
                cursor.execute(query)
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                logging.info(f"{len(rows)} linhas lidas de itsm.{table}")
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(columns)
            writer.writerows(rows)
            now = datetime.now(timezone.utc)
            file_path = f"{table}/{now:%Y/%m/%d}/{table}_{now:%Y%m%d_%H%M%S}.csv"
            datalake = DataLakeServiceClient.from_connection_string(
                os.getenv("DATALAKE_CONNECTION_STRING")
            )
            file_client = datalake.get_file_system_client("bronze").get_file_client(
                file_path
            )
            file_client.upload_data(buffer.getvalue().encode("utf-8"), overwrite=True)
            logging.info(f"Arquivo gravado em bronze/{file_path}")
        except Exception as e:
            logging.error(f"Erro ao ler itsm.{table}: {str(e)}")
            raise
        
    extract_tables_storage("chamado_sla")
    extract_tables_storage("chamado_status_historico")
    extract_tables_storage("cliente_organizacao")
    extract_tables_storage("csat_avaliacao")
    extract_tables_storage("fila")
    extract_tables_storage("sla")
    extract_tables_storage("solicitante")
    
    
