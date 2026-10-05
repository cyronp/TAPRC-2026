import logging
import os

import azure.functions as func
import pyodbc

app = func.FunctionApp()

@app.timer_trigger(schedule="0 * * * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=False) 
def timer_trigger_tipo1(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('O temporizador está atrasado!')

    logging.info('Função de temporizador executada.')

@app.timer_trigger(schedule="0 * * * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=False) 
def timer_trigger_tipo2(myTimer: func.TimerRequest) -> None:
    
    if myTimer.past_due:
        logging.info('O temporizador está atrasado!')

    logging.info('Função de temporizador executada.')


@app.timer_trigger(schedule="0 * * * * *", arg_name="myTimer", run_on_startup=False,
                   use_monitor=True)
def timer_trigger_chamado(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('O temporizador de chamados está atrasado!')

    database = os.getenv("DATABASE")
    host = os.getenv("HOST")
    password = os.getenv("PASSWORD")
    user = os.getenv("USER")

    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={host};DATABASE={database};"
        f"UID={user};PWD={password};"
        "Encrypt=yes;TrustServerCertificate=no;"
    )

    connection = None
    try:
        connection = pyodbc.connect(connection_string, timeout=30)
        cursor = connection.cursor()
        cursor.execute("SELECT TOP (3) * FROM [itsm].[chamado]")
        colunas = [coluna[0] for coluna in cursor.description]
        chamados = cursor.fetchall()
        logging.info('Consulta retornou %s chamado(s).', len(chamados))
        for chamado in chamados:
            logging.info('Chamado: %s', dict(zip(colunas, chamado)))
    except Exception:
        logging.exception('Erro ao consultar os chamados.')
        raise
    finally:
        if connection is not None:
            connection.close()
