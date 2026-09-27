"""
Carga los Parquet generados (estaciones, medias_diarias, anomalias, alertas)
a las tablas de Postgres (Supabase/Neon).

Requiere: pip install sqlalchemy psycopg2-binary python-dotenv duckdb pandas
Y un archivo .env en la raiz del proyecto con:
    DATABASE_URL=postgresql://usuario:password@host:puerto/postgres
(lo encuentras en Supabase: Settings -> Database -> Connection string -> URI)
"""
import os
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
PARQUET_LIMPIO = "data/processed/calidad_aire_limpio.parquet"
MEDIAS_DIARIAS = "data/processed/medias_diarias.parquet"
ANOMALIAS_DIR = Path("data/processed/anomalias")
ALERTAS_DIR = Path("data/processed/alertas")

CONTAMINANTES = ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO"]

engine = create_engine(DATABASE_URL)
con_duck = duckdb.connect()


def cargar_estaciones():
    print("=== Cargando estaciones ===")
    df = con_duck.execute(f"""
        SELECT
            ESTACION_ID AS estacion_id,
            ANY_VALUE(NOMBRE_EST) AS nombre,
            ANY_VALUE(DEPARTAMENTO) AS departamento,
            ANY_VALUE(MUNICIPIO) AS municipio,
            ANY_VALUE(TIPO_ESTACION) AS tipo_estacion,
            ROUND(AVG(LATITUD), 6) AS latitud,
            ROUND(AVG(LONGITUD), 6) AS longitud
        FROM read_parquet('{PARQUET_LIMPIO}')
        WHERE LATITUD IS NOT NULL AND LONGITUD IS NOT NULL
        GROUP BY ESTACION_ID
    """).df()

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE anomalias, alertas_episodios, medias_diarias RESTART IDENTITY"))
        conn.execute(text("TRUNCATE TABLE estaciones CASCADE"))

    df.to_sql("estaciones", engine, if_exists="append", index=False, method="multi", chunksize=500)
    print(f"Estaciones cargadas: {len(df):,}")


def cargar_medias_diarias():
    print("\n=== Cargando medias_diarias ===")
    df = pd.read_parquet(MEDIAS_DIARIAS)
    df = df.rename(columns={"msfl_code": "msfl_code"})  # ya coincide, dejar explicito por claridad

    total = len(df)
    tamano_lote = 50_000
    for inicio in range(0, total, tamano_lote):
        lote = df.iloc[inicio:inicio + tamano_lote]
        lote.to_sql("medias_diarias", engine, if_exists="append", index=False, method="multi", chunksize=5000)
        print(f"  Cargadas {min(inicio + tamano_lote, total):,} / {total:,}")

    print(f"Medias diarias cargadas: {total:,}")


def cargar_anomalias():
    print("\n=== Cargando anomalias ===")
    total = 0
    for cod in CONTAMINANTES:
        archivo = ANOMALIAS_DIR / f"anomalias_{cod.replace('.', '')}.parquet"
        if not archivo.exists():
            print(f"  Aviso: no existe {archivo}, se omite {cod}")
            continue
        df = con_duck.execute(f"""
            SELECT ESTACION_ID AS estacion_id, '{cod}' AS msfl_code,
                   fecha_inicio AS fecha_hora, valor
            FROM read_parquet('{archivo}')
            WHERE es_anomalia = true
        """).df()
        df.to_sql("anomalias", engine, if_exists="append", index=False, method="multi", chunksize=5000)
        total += len(df)
        print(f"  {cod}: {len(df):,} anomalias cargadas")
    print(f"Total anomalias cargadas: {total:,}")


def cargar_alertas():
    print("\n=== Cargando alertas_episodios ===")
    total = 0
    for cod in CONTAMINANTES:
        archivo = ALERTAS_DIR / f"episodios_{cod.replace('.', '')}.parquet"
        if not archivo.exists():
            print(f"  Aviso: no existe {archivo}, se omite {cod}")
            continue
        df = con_duck.execute(f"""
            SELECT ESTACION_ID AS estacion_id, contaminante AS msfl_code,
                   inicio, fin, horas_excedencia, pico_maximo,
                   promedio_episodio, limite_normativo, descripcion_periodo
            FROM read_parquet('{archivo}')
        """).df()
        df.to_sql("alertas_episodios", engine, if_exists="append", index=False, method="multi", chunksize=5000)
        total += len(df)
        print(f"  {cod}: {len(df):,} episodios cargados")
    print(f"Total episodios cargados: {total:,}")


def cargar_metadata():
    print("\n=== Registrando metadata del pipeline ===")
    resumen = con_duck.execute(f"""
        SELECT COUNT(*) AS total_registros,
               COUNT(DISTINCT ESTACION_ID) AS total_estaciones,
               MIN(fecha_inicio)::DATE AS fecha_min,
               MAX(fecha_inicio)::DATE AS fecha_max
        FROM read_parquet('{PARQUET_LIMPIO}')
        WHERE es_horario = true
    """).df().iloc[0]

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO pipeline_metadata
                    (total_registros, total_estaciones, fecha_min, fecha_max)
                VALUES (:tr, :te, :fmin, :fmax)
            """),
            {
                "tr": int(resumen["total_registros"]),
                "te": int(resumen["total_estaciones"]),
                "fmin": resumen["fecha_min"],
                "fmax": resumen["fecha_max"],
            },
        )
    print("Metadata registrada.")


if __name__ == "__main__":
    cargar_estaciones()
    cargar_medias_diarias()
    cargar_anomalias()
    cargar_alertas()
    cargar_metadata()
    print("\n¡Carga completa!")

con_duck.close()