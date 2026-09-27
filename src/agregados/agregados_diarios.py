"""
Genera la tabla de agregados diarios (medias_diarias) a partir del Parquet limpio.
Procesa UN codigo (MSFL_CODE) a la vez para mantener el uso de memoria bajo control,
en vez de agrupar los 32M de filas de una sola vez.
"""
import duckdb
from pathlib import Path

PARQUET_LIMPIO = "data/processed/calidad_aire_limpio.parquet"
OUT_PATH = Path("data/processed/medias_diarias.parquet")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
TEMP_DIR = Path("data/interim/duckdb_tmp_agregados")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Ajusta este numero segun la RAM real de tu PC (2GB es conservador)
MEMORY_LIMIT = "2GB"
THREADS = 2

con = duckdb.connect()
con.execute(f"SET memory_limit = '{MEMORY_LIMIT}'")
con.execute(f"SET threads = {THREADS}")
con.execute(f"SET temp_directory = '{TEMP_DIR}'")
con.execute("SET preserve_insertion_order = false")

CODIGOS = con.execute(f"""
    SELECT DISTINCT MSFL_CODE
    FROM read_parquet('{PARQUET_LIMPIO}')
""").fetchdf()["MSFL_CODE"].tolist()

print(f"Procesando {len(CODIGOS)} codigos, uno a la vez...")

primero = True
for cod in CODIGOS:
    print(f"\n=== {cod} ===")

    cod_escapado = cod.replace("'", "''")
    consulta = f"""
        SELECT
            ESTACION_ID AS estacion_id,
            MSFL_CODE AS msfl_code,
            CAST(fecha_inicio AS DATE) AS fecha,
            COUNT(*) AS registros,
            ROUND(AVG(MED_CONCENTRACION_ESTANDAR), 3) AS promedio,
            ROUND(approx_quantile(MED_CONCENTRACION_ESTANDAR, 0.95), 3) AS p95,
            ROUND(MIN(MED_CONCENTRACION_ESTANDAR), 3) AS minimo,
            ROUND(MAX(MED_CONCENTRACION_ESTANDAR), 3) AS maximo,
            COUNT(*) FILTER (
                WHERE MSFL_CODE <> 'SO2' OR calidad_so2 <> 'extremo_revisar'
            ) AS registros_sin_extremos,
            ROUND(AVG(MED_CONCENTRACION_ESTANDAR) FILTER (
                WHERE MSFL_CODE <> 'SO2' OR calidad_so2 <> 'extremo_revisar'
            ), 3) AS promedio_sin_extremos
        FROM read_parquet('{PARQUET_LIMPIO}')
        WHERE es_horario = true AND MSFL_CODE = '{cod_escapado}'
        GROUP BY ESTACION_ID, MSFL_CODE, CAST(fecha_inicio AS DATE)
    """

    if primero:
        con.execute(f"""
            COPY ({consulta}) TO '{OUT_PATH}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        primero = False
    else:
        # Parquet no soporta "append" nativo; guardamos por partes y unimos al final
        parcial = OUT_PATH.parent / f"_parcial_{cod.replace('.', '').replace(' ', '_')}.parquet"
        con.execute(f"COPY ({consulta}) TO '{parcial}' (FORMAT PARQUET, COMPRESSION ZSTD)")

    conteo = con.execute(f"SELECT COUNT(*) FROM ({consulta})").fetchone()[0]
    print(f"Filas agregadas para {cod}: {conteo:,}")

# --- Unir todas las partes en el archivo final ---
print("\nUniendo resultados parciales...")
partes = list(OUT_PATH.parent.glob("_parcial_*.parquet"))
if partes:
    lista_archivos = ", ".join(f"'{p}'" for p in [str(OUT_PATH)] + [str(p) for p in partes])
    con.execute(f"""
        COPY (
            SELECT * FROM read_parquet([{lista_archivos}])
        ) TO '{OUT_PATH}.final' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    OUT_PATH.unlink()
    (OUT_PATH.parent / f"{OUT_PATH.name}.final").rename(OUT_PATH)
    for p in partes:
        p.unlink()

resultado = con.execute(f"SELECT COUNT(*) AS filas FROM read_parquet('{OUT_PATH}')").fetchone()
print(f"\nAgregados diarios generados: {resultado[0]:,} filas")
print(f"Guardado en: {OUT_PATH}")

con.close()