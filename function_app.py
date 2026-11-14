import csv
import io
import logging
import os
from datetime import datetime, timezone
import re

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
    extract_tables_storage("categoria")
    extract_tables_storage("analista")
    extract_tables_storage("chamado")
    
    
    



@app.timer_trigger(
    schedule="0 15 * * * *", arg_name="myTimer", run_on_startup=False
)
def load_tables(myTimer: func.TimerRequest) -> None:
    logging.info("Iniciando...")
    
    SCHEMA = "itsm"
    CONTAINER = "bronze"

    ORDEM_CARGA = [
        "categoria",
        "cliente_organizacao",
        "fila",
        "sla",
        "analista",                  # -> fila
        "solicitante",               # -> cliente_organizacao
        "chamado",                   # -> analista, categoria, cliente_organizacao, fila, solicitante
        "chamado_sla",               # -> chamado, sla
        "chamado_status_historico",  # -> chamado, analista, fila
        "csat_avaliacao",            # -> chamado, analista
    ]

    COLUNAS_UPPER = {"ds_tipo_chamado", "ds_status_chamado", "ds_prioridade", "ds_nivel"}
    COLUNAS_LOWER = {"ds_email"}

    TIPOS_TEXTO = {"nvarchar", "varchar", "nchar", "char"}

    SQL_METADADOS = """
    SELECT c.name,
        t.name                                           AS tipo,
        CASE WHEN c.max_length = -1 THEN 1 ELSE 0 END    AS is_max,
        c.is_nullable,
        c.is_identity,
        CASE WHEN ic.column_id IS NULL THEN 0 ELSE 1 END AS is_pk
    FROM sys.columns c
    JOIN sys.types t
        ON t.user_type_id = c.user_type_id
    LEFT JOIN sys.indexes i
        ON i.object_id = c.object_id AND i.is_primary_key = 1
    LEFT JOIN sys.index_columns ic
        ON ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.column_id = c.column_id
    WHERE c.object_id = OBJECT_ID(?)
    ORDER BY c.column_id
    """


    def get_conn_str():
        return (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={os.getenv('HOST')};"
            f"DATABASE={os.getenv('DATABASE')};"
            f"UID={os.getenv('USER')};"
            f"PWD={os.getenv('PASSWORD')};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30;"
        )


    def obter_mais_recente(fs, tabela):
        arquivos = [
            p.name
            for p in fs.get_paths(path=tabela, recursive=True)
            if not p.is_directory and p.name.endswith(".csv")
        ]
        return max(arquivos) if arquivos else None


    def ler_csv(fs, caminho):
        conteudo = fs.get_file_client(caminho).download_file().readall().decode("utf-8")
        if not conteudo.strip():
            raise ValueError(f"{caminho} está vazio")
        reader = csv.reader(io.StringIO(conteudo, newline=""))
        colunas = next(reader)
        return colunas, list(reader)


    def obter_metadados(cursor, tabela):
        cursor.execute(SQL_METADADOS, f"{SCHEMA}.{tabela}")
        meta = {
            nome: {
                "tipo": tipo,
                "max": bool(is_max),
                "nullable": bool(is_nullable),
                "identity": bool(is_identity),
                "pk": bool(is_pk),
            }
            for nome, tipo, is_max, is_nullable, is_identity, is_pk in cursor.fetchall()
        }
        if not meta:
            raise ValueError(f"Tabela {SCHEMA}.{tabela} não existe no banco de destino")
        return meta


    def tratar_valor(coluna, valor, info):
        valor = valor.strip()
        if valor == "":
            if info["tipo"] in TIPOS_TEXTO and not info["nullable"]:
                return ""
            return None
        if info["tipo"] == "bit":
            return "1" if valor.lower() in ("true", "1") else "0"
        if coluna in COLUNAS_UPPER:
            return valor.upper()
        if coluna in COLUNAS_LOWER:
            return valor.lower()
        if coluna in COLUNAS_SO_DIGITOS:
            return re.sub(r"\D", "", valor)
        return valor


    def tratar(colunas_csv, linhas, meta, arquivo):
        pk = [c for c, info in meta.items() if info["pk"]]
        faltando = [c for c in pk if c not in colunas_csv]
        if faltando:
            raise ValueError(f"{arquivo}: CSV sem a(s) coluna(s) de PK {faltando}")

        extras = [c for c in colunas_csv if c not in meta]
        if extras:
            logging.warning(f"{arquivo}: colunas ignoradas (não existem no destino): {extras}")

        colunas = [c for c in colunas_csv if c in meta]
        idx = [colunas_csv.index(c) for c in colunas]
        idx_pk = [colunas.index(c) for c in pk]

        unicos = {}
        for n, linha in enumerate(linhas, start=2):
            if len(linha) != len(colunas_csv):
                raise ValueError(
                    f"{arquivo}: linha {n} com {len(linha)} colunas, esperado {len(colunas_csv)}"
                )
            registro = [tratar_valor(c, linha[i], meta[c]) for c, i in zip(colunas, idx)]
            chave = tuple(registro[i] for i in idx_pk)
            if any(k is None for k in chave):
                raise ValueError(f"{arquivo}: linha {n} sem valor na PK {pk}")
            unicos[chave] = registro

        if len(unicos) < len(linhas):
            logging.warning(f"{arquivo}: {len(linhas) - len(unicos)} linha(s) com ID repetido removida(s)")
        return colunas, pk, list(unicos.values())


    def montar_merge(tabela_sql, colunas, pk):
        nao_pk = [c for c in colunas if c not in pk]
        on = " AND ".join(f"t.[{c}] = s.[{c}]" for c in pk)
        cols = ", ".join(f"[{c}]" for c in colunas)
        vals = ", ".join(f"s.[{c}]" for c in colunas)

        update = ""
        if nao_pk:
            s_cols = ", ".join(f"s.[{c}]" for c in nao_pk)
            t_cols = ", ".join(f"t.[{c}]" for c in nao_pk)
            sets = ", ".join(f"t.[{c}] = s.[{c}]" for c in nao_pk)
            update = (
                f"WHEN MATCHED AND EXISTS (SELECT {s_cols} EXCEPT SELECT {t_cols}) "
                f"THEN UPDATE SET {sets}"
            )

        return f"""
            MERGE {tabela_sql} WITH (HOLDLOCK) AS t
            USING #stg AS s
            ON {on}
            {update}
            WHEN NOT MATCHED BY TARGET THEN
                INSERT ({cols}) VALUES ({vals});
        """


    def carregar_tabela(conn, fs, tabela):
        arquivo = obter_mais_recente(fs, tabela)
        if not arquivo:
            logging.warning(f"{tabela}: nenhum CSV encontrado em {CONTAINER}/{tabela}")
            return

        cursor = conn.cursor()
        meta = obter_metadados(cursor, tabela)

        colunas_csv, linhas = ler_csv(fs, arquivo)
        colunas, pk, linhas = tratar(colunas_csv, linhas, meta, arquivo)

        tabela_sql = f"[{SCHEMA}].[{tabela}]"
        cols = ", ".join(f"[{c}]" for c in colunas)

        cursor.execute("DROP TABLE IF EXISTS #stg")
        cursor.execute(
            "CREATE TABLE #stg ("
            + ", ".join(f"[{c}] NVARCHAR({'MAX' if meta[c]['max'] else 4000}) NULL" for c in colunas)
            + ")"
        )
        if linhas:
            cursor.fast_executemany = True
            cursor.setinputsizes(
                [(pyodbc.SQL_WVARCHAR, 0 if meta[c]["max"] else 4000, 0) for c in colunas]
            )
            cursor.executemany(
                f"INSERT INTO #stg ({cols}) VALUES ({', '.join('?' * len(colunas))})", linhas
            )

        tem_identity = any(meta[c]["identity"] for c in colunas)
        if tem_identity:
            cursor.execute(f"SET IDENTITY_INSERT {tabela_sql} ON")
        try:
            cursor.execute(montar_merge(tabela_sql, colunas, pk))
            afetadas = cursor.rowcount
        finally:
            if tem_identity:
                cursor.execute(f"SET IDENTITY_INSERT {tabela_sql} OFF")

        conn.commit()
        logging.info(
            f"{tabela}: {arquivo} -> {len(linhas)} linhas lidas, {afetadas} inseridas/atualizadas"
        )
        
    datalake = DataLakeServiceClient.from_connection_string(
        os.getenv("DATALAKE_CONNECTION_STRING")
    )
    logging.info("Iniciar datalake.get_file...")
    fs = datalake.get_file_system_client(CONTAINER)

    logging.info("Inicia conexão...")
    conn = pyodbc.connect(get_conn_str(), autocommit=False)
    logging.info("Aqui começa o try")
    try:
        for tabela in ORDEM_CARGA:
            try:
                carregar_tabela(conn, fs, tabela)
            except Exception:
                conn.rollback()
                logging.exception(f"Erro ao carregar {SCHEMA}.{tabela}")
                raise
    finally:
        conn.close()
