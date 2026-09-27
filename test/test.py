import duckdb

"""
Diagnostico paso a paso para encontrar donde se pierden los episodios de SO2.
SO2 es el caso mas simple (ventana=1, sin promedio real que calcular),
asi que si aqui tambien da 0, el bug esta en una etapa temprana comun a todos.
"""
import duckdb

PARQUET_LIMPIO = "data/processed/calidad_aire_limpio.parquet"
con = duckdb.connect()

print("== Paso 0: cuantos registros de SO2 horarios hay en total? ==")
print(con.execute(f"""
    SELECT COUNT(*) AS total
    FROM read_parquet('{PARQUET_LIMPIO}')
    WHERE MSFL_CODE = 'SO2' AND es_horario = true
""").df())

print("\n== Paso 1: cuantos SUPERAN 99.6 ug/m3 sin ningun procesamiento adicional? ==")
print(con.execute(f"""
    SELECT COUNT(*) AS total_sobre_limite
    FROM read_parquet('{PARQUET_LIMPIO}')
    WHERE MSFL_CODE = 'SO2' AND es_horario = true
      AND MED_CONCENTRACION_ESTANDAR > 99.6
""").df())

print("\n== Paso 2: replicando el CTE 'rolling' para SO2 (ventana=1, interval '0 hours') ==")
print(con.execute(f"""
    WITH datos AS (
        SELECT ESTACION_ID, fecha_inicio, MED_CONCENTRACION_ESTANDAR AS valor
        FROM read_parquet('{PARQUET_LIMPIO}')
        WHERE MSFL_CODE = 'SO2' AND es_horario = true
    ), rolling AS (
        SELECT *,
            AVG(valor) OVER ventana AS valor_rolling,
            COUNT(valor) OVER ventana AS observaciones_ventana
        FROM datos
        WINDOW ventana AS (
            PARTITION BY ESTACION_ID
            ORDER BY fecha_inicio
            RANGE BETWEEN INTERVAL '0 hours' PRECEDING AND CURRENT ROW
        )
    )
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE valor_rolling > 99.6) AS sobre_limite_rolling,
           COUNT(*) FILTER (WHERE valor_rolling IS NULL) AS rolling_nulos,
           AVG(observaciones_ventana) AS promedio_observaciones_ventana,
           MAX(valor_rolling) AS max_rolling,
           MAX(valor) AS max_valor_crudo
    FROM rolling
""").df())

con.close()