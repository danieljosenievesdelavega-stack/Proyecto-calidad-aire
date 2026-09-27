import duckdb

print("== 1. Distribución de DURACIÓN (¿cuánto se desvía de 60 minutos?) ==")
duckdb.query("""
    SELECT "DURACIÓN", COUNT(*) AS registros
    FROM 'data/processed/calidad_aire_limpio.parquet'
    GROUP BY "DURACIÓN"
    ORDER BY registros DESC
    LIMIT 20
""").show()

print("\n== 2. Duración por variable (¿todas asumen 60 min o varía por código?) ==")
duckdb.query("""
    SELECT MSFL_CODE,
        MIN("DURACIÓN") AS dur_min,
        approx_quantile("DURACIÓN", 0.5) AS dur_mediana,
        MAX("DURACIÓN") AS dur_max,
        COUNT(*) FILTER (WHERE "DURACIÓN" != 60) AS registros_no_60min
    FROM 'data/processed/calidad_aire_limpio.parquet'
    GROUP BY MSFL_CODE
    ORDER BY registros_no_60min DESC
""").show()

print("\n== 3. Distribución REAL y completa de SO2 (válidos + descartados) ==")
duckdb.query("""
    SELECT
        MIN(MED_CONCENTRACION_ESTANDAR) AS minimo,
        approx_quantile(MED_CONCENTRACION_ESTANDAR, 0.01) AS p1,
        approx_quantile(MED_CONCENTRACION_ESTANDAR, 0.50) AS mediana,
        approx_quantile(MED_CONCENTRACION_ESTANDAR, 0.99) AS p99,
        approx_quantile(MED_CONCENTRACION_ESTANDAR, 0.999) AS p999,
        MAX(MED_CONCENTRACION_ESTANDAR) AS maximo,
        COUNT(*) AS total
    FROM (
        SELECT MED_CONCENTRACION_ESTANDAR, MSFL_CODE FROM 'data/processed/calidad_aire_limpio.parquet'
        UNION ALL
        SELECT MED_CONCENTRACION_ESTANDAR, MSFL_CODE FROM 'data/interim/registros_descartados.parquet'
    )
    WHERE MSFL_CODE = 'SO2'
""").show()

print("\n== 4. Top 15 valores de SO2 descartados (para ver si son error de sensor o corte artificial) ==")
duckdb.query("""
    SELECT MED_CONCENTRACION_ESTANDAR, SIGLA_UNIDAD, NOMBRE_EST, fecha_inicio
    FROM 'data/interim/registros_descartados.parquet'
    WHERE MSFL_CODE = 'SO2'
    ORDER BY MED_CONCENTRACION_ESTANDAR DESC
    LIMIT 15
""").show()

print("\n== 5. Unidad real reportada para P (presión) -- ¿de verdad dice mmHg? ==")
duckdb.query("""
    SELECT DISTINCT SIGLA_UNIDAD, NOMBRE_UNIDAD
    FROM 'data/processed/calidad_aire_limpio.parquet'
    WHERE MSFL_CODE = 'P'
""").show()

print("\n== 6. Duplicados detectados por la regla actual (mismo estacion+codigo+fecha_inicio+fecha_final) ==")
duckdb.query("""
    SELECT COUNT(*) AS grupos_con_duplicados, SUM(cnt) AS filas_involucradas
    FROM (
        SELECT ESTACION_ID, MSFL_CODE, MED_FECHA_INICIO, MED_FECHA_FINAL, COUNT(*) AS cnt
        FROM read_csv_auto(
            'data/raw/calidad_aire_completo.csv',
            header = true,
            delim = ',',
            quote = '"',
            escape = '"',
            sample_size = 100000,
            ignore_errors = false
        )
        GROUP BY ESTACION_ID, MSFL_CODE, MED_FECHA_INICIO, MED_FECHA_FINAL
        HAVING COUNT(*) > 1
    )
""").show()
print("\n== 7. Distribución de valores de SO2 ==")
duckdb.query("""
    SELECT calidad_so2, COUNT(*) FROM 'data/processed/calidad_aire_limpio.parquet'
    WHERE MSFL_CODE = 'SO2' GROUP BY calidad_so2;

    SELECT es_horario, COUNT(*) FROM 'data/processed/calidad_aire_limpio.parquet'
    GROUP BY es_horario;
""").show()
print("\n== 8. Distribución de valores de horarios ==")
duckdb.query("""

    SELECT es_horario, COUNT(*) FROM 'data/processed/calidad_aire_limpio.parquet'
    GROUP BY es_horario;
""").show()
print("\n== 9. número de estaciones ==")
duckdb.query("""

    SELECT COUNT(DISTINCT ESTACION_ID) AS numero_estaciones
    FROM 'data/processed/calidad_aire_limpio.parquet'
""").show()
