"""
Fase 2 - Limpieza de datos de calidad del aire (SISAIRE / datos.gov.co)
Pipeline completo: fechas -> duplicados -> rangos fisicos -> texto -> guardado.

DuckDB procesa la deduplicacion usando disco temporal cuando es necesario,
para que el estado de una tabla de varios GB no tenga que caber en la RAM.

Instalar: pip install duckdb
"""
import os
from pathlib import Path

import duckdb

RAW_PATH = Path("data/raw/calidad_aire_completo.csv")
OUT_PATH = Path("data/processed/calidad_aire_limpio.parquet")
LOG_DESCARTES = Path("data/interim/registros_descartados.parquet")

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_DESCARTES.parent.mkdir(parents=True, exist_ok=True)

# NOTA: sin "AS limites(...)" aqui -- el alias se pone una sola vez en el JOIN
limites_sql = """
    VALUES
        ('CO', 0, 40000), ('NO', 0, 1000), ('NO2', 0, 500),
        ('O3', 0, 400), ('SO2', 0, 3000), ('PM10', 0, 1200),
        ('PM2.5', 0, 1000), ('PST', 0, 1500), ('TAire2', -10, 45),
        ('TAire10', -10, 45), ('HAire2', 0, 100), ('HAire10', 0, 100),
        ('VViento', 0, 35), ('DViento', 0, 360), ('P', 500, 1050),
        ('PLiquida', 0, 300), ('RGlobal', 0, 1500), ('RUVb', 0, 5000)
"""

csv_path = str(RAW_PATH).replace("'", "''")
temp_dir = str(LOG_DESCARTES.parent / "duckdb_tmp").replace("'", "''")
memory_limit = os.environ.get("AIR_MEMORY_LIMIT", "4GB")
SO2_P99 = 59.86
SO2_MAX = 3000

tipos_columnas = """
    types = {
        'MED_CONCENTRACION_ESTANDAR': 'DOUBLE',
        'ESTACION_ID': 'INTEGER',
        'LATITUD': 'DOUBLE',
        'LONGITUD': 'DOUBLE',
        'MED_FECHA_INICIO': 'VARCHAR',
        'MED_FECHA_FINAL': 'VARCHAR',
        'CODIGO_MUNICIPIO': 'VARCHAR',
        'CODIGO_DEPARTAMENTO': 'VARCHAR'
    }
"""

base_query = f"""
    WITH origen AS (
        SELECT *, row_number() OVER () AS orden_origen
        FROM read_csv_auto(
            '{csv_path}',
            header = true,
            quote = '"',
            escape = '"',
            delim = ',',
            encoding = 'UTF-8',
            sample_size = 100000,
            ignore_errors = false,
            {tipos_columnas}
        )
    ), normalizado AS (
        SELECT * REPLACE (
            trim(NOMBRE_EST) AS NOMBRE_EST,
            trim(DEPARTAMENTO) AS DEPARTAMENTO,
            trim(MUNICIPIO) AS MUNICIPIO,
            trim(MSFL_CODE) AS MSFL_CODE,
            trim(SIGLA_UNIDAD) AS SIGLA_UNIDAD
        )
        FROM origen
    ), parseado AS (
        SELECT *,
            try_strptime(MED_FECHA_INICIO, '%m/%d/%Y %I:%M:%S %p') AS fecha_inicio,
            try_strptime(MED_FECHA_FINAL, '%m/%d/%Y %I:%M:%S %p') AS fecha_final
        FROM normalizado
    ), clasificado AS (
        SELECT p.*, l.lim_min, l.lim_max,
            CASE
                WHEN MSFL_CODE <> 'SO2' THEN 'valido'
                WHEN MED_CONCENTRACION_ESTANDAR <= {SO2_P99} THEN 'valido'
                WHEN MED_CONCENTRACION_ESTANDAR <= {SO2_MAX} THEN 'extremo_revisar'
                ELSE 'invalido'
            END AS calidad_so2,
            date_diff('minute', fecha_inicio, fecha_final) BETWEEN 55 AND 65 AS es_horario
        FROM parseado p
        LEFT JOIN ({limites_sql}) AS l(MSFL_CODE, lim_min, lim_max) USING (MSFL_CODE)
    ), motivo AS (
        SELECT *,
            CASE
                WHEN fecha_inicio IS NULL THEN 'fecha_inicio_invalida'
                WHEN fecha_final IS NULL THEN 'fecha_final_invalida'
                WHEN fecha_final < fecha_inicio THEN 'fecha_final_anterior_inicio'
                WHEN MED_CONCENTRACION_ESTANDAR IS NULL THEN 'concentracion_nula'
                WHEN calidad_so2 = 'invalido' THEN 'so2_invalido'
                WHEN lim_min IS NULL THEN 'variable_sin_limites'
                WHEN MED_CONCENTRACION_ESTANDAR NOT BETWEEN lim_min AND lim_max THEN 'fuera_de_rango'
                ELSE NULL
            END AS motivo_descarte
        FROM clasificado
    ), validado AS (
        SELECT *, motivo_descarte IS NULL AS es_valido
        FROM motivo
    )
    SELECT * FROM validado
"""

# Conexión optimizada para bajo consumo de memoria
connection = duckdb.connect()
connection.execute(f"SET memory_limit = '{memory_limit}'")
connection.execute("SET preserve_insertion_order = false")  # Permite liberar RAM hacia el disco temporal
connection.execute("SET threads = 2")                        # Reduce la memoria usada por hilos en paralelo
connection.execute(f"SET temp_directory = '{temp_dir}'")

print("Paso 1: Procesando base y guardando tabla temporal en disco...")
connection.execute(f"""
    CREATE TEMP TABLE datos_clasificados AS
    {base_query}
""")

print("Paso 2: Exportando registros descartados...")
connection.execute(f"""
    COPY (
        SELECT * EXCLUDE (lim_min, lim_max, es_valido, orden_origen)
        FROM datos_clasificados
        WHERE NOT es_valido
    ) TO '{str(LOG_DESCARTES).replace("'", "''")}'
    (FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE true)
""")

print("Paso 3: Deduplicando y guardando datos limpios...")
connection.execute(f"""
    COPY (
        WITH numerados AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY ESTACION_ID, MSFL_CODE, fecha_inicio, fecha_final
                ORDER BY orden_origen
            ) AS numero_duplicado
            FROM datos_clasificados
            WHERE es_valido
        )
        SELECT * EXCLUDE (lim_min, lim_max, es_valido, numero_duplicado, orden_origen)
        FROM numerados
        WHERE numero_duplicado = 1
    ) TO '{str(OUT_PATH).replace("'", "''")}'
    (FORMAT PARQUET, COMPRESSION ZSTD, OVERWRITE_OR_IGNORE true)
""")

connection.execute("DROP TABLE datos_clasificados")
connection.close()

print(f"Listo. Datos limpios en: {OUT_PATH}")
print(f"Registros descartados en: {LOG_DESCARTES}")