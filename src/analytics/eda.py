"""
Fase 3 - EDA sobre datos de calidad del aire
Estrategia: DuckDB agrega sobre los 32M de filas; Python solo grafica resultados pequeños.
"""
import duckdb
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

PARQUET_LIMPIO = "data/processed/calidad_aire_limpio.parquet"
OUT_DIR = "reports/figures"
import os
os.makedirs(OUT_DIR, exist_ok=True)

con = duckdb.connect()
con.execute(f"CREATE VIEW datos AS SELECT * FROM '{PARQUET_LIMPIO}'")
con.execute("CREATE VIEW datos_horarios AS SELECT * FROM datos WHERE es_horario")
con.execute("CREATE VIEW datos_confiables AS SELECT * FROM datos_horarios WHERE calidad_so2 = 'valido'")

# ---------------------------------------------------------------
# 1. Registros por variable
# ---------------------------------------------------------------
df_conteo = con.execute("""
    SELECT MSFL_CODE, COUNT(*) AS registros
    FROM datos_confiables GROUP BY MSFL_CODE ORDER BY registros DESC
""").df()
print("== 1. Registros por variable ==")
print(df_conteo)

plt.figure(figsize=(10, 5))
plt.bar(df_conteo["MSFL_CODE"], df_conteo["registros"])
plt.xticks(rotation=45)
plt.title("Registros por variable")
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/01_registros_por_variable.png")
plt.close()

# ---------------------------------------------------------------
# 2. Registros por estación (top 20)
# ---------------------------------------------------------------
df_estaciones = con.execute("""
    SELECT NOMBRE_EST, DEPARTAMENTO, COUNT(*) AS registros
    FROM datos_confiables GROUP BY NOMBRE_EST, DEPARTAMENTO
    ORDER BY registros DESC LIMIT 20
""").df()
print("\n== 2. Top 20 estaciones con más registros ==")
print(df_estaciones)

plt.figure(figsize=(10, 6))
plt.barh(df_estaciones["NOMBRE_EST"], df_estaciones["registros"])
plt.title("Top 20 estaciones por volumen de registros")
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/02_registros_por_estacion.png")
plt.close()

# ---------------------------------------------------------------
# 3. Cobertura temporal por variable (desde / hasta / dias con datos)
# ---------------------------------------------------------------
df_cobertura = con.execute("""
    SELECT MSFL_CODE,
        MIN(fecha_inicio) AS desde,
        MAX(fecha_inicio) AS hasta,
        COUNT(DISTINCT DATE_TRUNC('day', fecha_inicio)) AS dias_con_datos
    FROM datos_confiables GROUP BY MSFL_CODE ORDER BY MSFL_CODE
""").df()
print("\n== 3. Cobertura temporal por variable ==")
print(df_cobertura)

# ---------------------------------------------------------------
# 4. % de faltantes por variable y estación (huecos esperados vs reales)
#    Aproximación: para variables horarias, horas totales del periodo vs registros reales
# ---------------------------------------------------------------
df_faltantes = con.execute("""
    WITH por_estacion AS (
        SELECT ESTACION_ID, MSFL_CODE,
            MIN(fecha_inicio) AS desde,
            MAX(fecha_inicio) AS hasta,
            COUNT(*) AS registros
        FROM datos_confiables
        GROUP BY ESTACION_ID, MSFL_CODE
    ),
    con_horas AS (
        SELECT *,
            DATEDIFF('hour', desde, hasta) + 1 AS horas_esperadas
        FROM por_estacion
    )
    SELECT
        MSFL_CODE,
        COUNT(DISTINCT ESTACION_ID) AS n_estaciones,
        SUM(registros) AS registros_reales,
        SUM(horas_esperadas) AS horas_esperadas_totales,
        ROUND(100 - SUM(registros) * 100.0 / SUM(horas_esperadas), 2) AS pct_faltante
    FROM con_horas
    GROUP BY MSFL_CODE
    ORDER BY pct_faltante DESC
""").df()
print("\n== 4. % de datos faltantes (calculado por estación individual) ==")
print(df_faltantes)

# ---------------------------------------------------------------
# 5. Boxplots de contaminantes (percentiles calculados en DuckDB)
# ---------------------------------------------------------------
CONTAMINANTES = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]
stats_box = []
for cod in CONTAMINANTES:
    q = con.execute(f"""
        SELECT
            MIN(MED_CONCENTRACION_ESTANDAR) AS whislo,
            approx_quantile(MED_CONCENTRACION_ESTANDAR, 0.25) AS q1,
            approx_quantile(MED_CONCENTRACION_ESTANDAR, 0.50) AS med,
            approx_quantile(MED_CONCENTRACION_ESTANDAR, 0.75) AS q3,
            approx_quantile(MED_CONCENTRACION_ESTANDAR, 0.95) AS whishi
        FROM datos_confiables WHERE MSFL_CODE = '{cod}'
    """).fetchone()
    stats_box.append({"label": cod, "whislo": q[0], "q1": q[1], "med": q[2],
                       "q3": q[3], "whishi": q[4], "fliers": []})

fig, ax = plt.subplots(figsize=(10, 6))
ax.bxp(stats_box, showfliers=False)
ax.set_title("Distribución de contaminantes (percentiles 25-75, bigotes en P5-P95)")
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/05_boxplots_contaminantes.png")
plt.close()
print("\n== 5. Boxplots guardados ==")

# ---------------------------------------------------------------
# 6-8. PM2.5 por año / mes / hora
# ---------------------------------------------------------------
df_pm25_anual = con.execute("""
    SELECT EXTRACT(year FROM fecha_inicio) AS anio,
           AVG(MED_CONCENTRACION_ESTANDAR) AS promedio
    FROM datos_confiables WHERE MSFL_CODE = 'PM2.5'
    GROUP BY anio ORDER BY anio
""").df()

df_pm25_mensual = con.execute("""
    SELECT EXTRACT(month FROM fecha_inicio) AS mes,
           AVG(MED_CONCENTRACION_ESTANDAR) AS promedio
    FROM datos_confiables WHERE MSFL_CODE = 'PM2.5'
    GROUP BY mes ORDER BY mes
""").df()

df_pm25_horaria = con.execute("""
    SELECT EXTRACT(hour FROM fecha_inicio) AS hora,
           AVG(MED_CONCENTRACION_ESTANDAR) AS promedio
    FROM datos_confiables WHERE MSFL_CODE = 'PM2.5'
    GROUP BY hora ORDER BY hora
""").df()

fig, axes = plt.subplots(1, 3, figsize=(16, 4))
axes[0].plot(df_pm25_anual["anio"], df_pm25_anual["promedio"], marker="o")
axes[0].set_title("PM2.5 promedio por año")
axes[1].plot(df_pm25_mensual["mes"], df_pm25_mensual["promedio"], marker="o")
axes[1].set_title("PM2.5 promedio por mes")
axes[2].plot(df_pm25_horaria["hora"], df_pm25_horaria["promedio"], marker="o")
axes[2].set_title("PM2.5 promedio por hora del día")
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/06_08_pm25_temporal.png")
plt.close()
print("\n== 6-8. Series temporales de PM2.5 guardadas ==")

# ---------------------------------------------------------------
# 0 (previo a 9-12). Aplanar formato largo -> ancho por estacion+hora
# Necesario para cruzar PM2.5 con lluvia/viento/temperatura
# ---------------------------------------------------------------
con.execute("""
    CREATE OR REPLACE TEMP VIEW datos_ancho AS
    SELECT
        ESTACION_ID,
        DATE_TRUNC('hour', fecha_inicio) AS hora,
        MAX(CASE WHEN MSFL_CODE = 'PM2.5' THEN MED_CONCENTRACION_ESTANDAR END) AS pm25,
        MAX(CASE WHEN MSFL_CODE = 'PLiquida' THEN MED_CONCENTRACION_ESTANDAR END) AS lluvia,
        MAX(CASE WHEN MSFL_CODE = 'VViento' THEN MED_CONCENTRACION_ESTANDAR END) AS viento,
        MAX(CASE WHEN MSFL_CODE = 'TAire2' THEN MED_CONCENTRACION_ESTANDAR END) AS temperatura,
        MAX(CASE WHEN MSFL_CODE = 'HAire2' THEN MED_CONCENTRACION_ESTANDAR END) AS humedad,
        MAX(CASE WHEN MSFL_CODE = 'PM10' THEN MED_CONCENTRACION_ESTANDAR END) AS pm10,
        MAX(CASE WHEN MSFL_CODE = 'NO2' THEN MED_CONCENTRACION_ESTANDAR END) AS no2,
        MAX(CASE WHEN MSFL_CODE = 'O3' THEN MED_CONCENTRACION_ESTANDAR END) AS o3
    FROM datos_confiables
    GROUP BY ESTACION_ID, DATE_TRUNC('hour', fecha_inicio)
""")

# ---------------------------------------------------------------
# 9. PM2.5 según lluvia (con vs sin precipitación)
# ---------------------------------------------------------------
df_lluvia = con.execute("""
    SELECT
        CASE WHEN lluvia > 0 THEN 'Con lluvia' ELSE 'Sin lluvia' END AS condicion,
        AVG(pm25) AS pm25_promedio,
        COUNT(*) AS n
    FROM datos_ancho
    WHERE pm25 IS NOT NULL AND lluvia IS NOT NULL
    GROUP BY condicion
""").df()
print("\n== 9. PM2.5 según lluvia ==")
print(df_lluvia)

# ---------------------------------------------------------------
# 10. PM2.5 vs velocidad del viento (por bins)
# ---------------------------------------------------------------
df_viento = con.execute("""
    SELECT
        CAST(FLOOR(viento / 2) AS INTEGER) AS bin_viento,
        AVG(viento) AS viento_promedio,
        AVG(pm25) AS pm25_promedio,
        COUNT(*) AS n
    FROM datos_ancho
    WHERE pm25 IS NOT NULL AND viento IS NOT NULL
    GROUP BY bin_viento ORDER BY bin_viento
""").df()
print("\n== 10. PM2.5 vs viento (por bins) ==")
print(df_viento)

# ---------------------------------------------------------------
# 11. PM2.5 vs temperatura (por bins)
# ---------------------------------------------------------------
df_temp = con.execute("""
    SELECT
        CAST(FLOOR(temperatura / 3.5) AS INTEGER) AS bin_temp,
        AVG(temperatura) AS temp_promedio,
        AVG(pm25) AS pm25_promedio,
        COUNT(*) AS n
    FROM datos_ancho
    WHERE pm25 IS NOT NULL AND temperatura IS NOT NULL
    GROUP BY bin_temp ORDER BY bin_temp
""").df()
print("\n== 11. PM2.5 vs temperatura (por bins) ==")
print(df_temp)

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].plot(df_viento["viento_promedio"], df_viento["pm25_promedio"], marker="o")
axes[0].set_title("PM2.5 vs velocidad del viento")
axes[0].set_xlabel("Viento (m/s)")
axes[1].plot(df_temp["temp_promedio"], df_temp["pm25_promedio"], marker="o", color="orange")
axes[1].set_title("PM2.5 vs temperatura")
axes[1].set_xlabel("Temperatura (°C)")
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/10_11_pm25_vs_meteorologia.png")
plt.close()

# ---------------------------------------------------------------
# 12. Matriz de correlación (calculada directo en SQL con corr())
# ---------------------------------------------------------------
variables_corr = ["pm25", "pm10", "no2", "o3", "lluvia", "viento", "temperatura", "humedad"]
matriz = pd.DataFrame(index=variables_corr, columns=variables_corr, dtype=float)
for v1 in variables_corr:
    for v2 in variables_corr:
        r = con.execute(f"SELECT corr({v1}, {v2}) FROM datos_ancho").fetchone()[0]
        matriz.loc[v1, v2] = r

print("\n== 12. Matriz de correlación ==")
print(matriz.round(2))

fig, ax = plt.subplots(figsize=(8, 7))
im = ax.imshow(matriz.astype(float), cmap="coolwarm", vmin=-1, vmax=1)
ax.set_xticks(range(len(variables_corr))); ax.set_xticklabels(variables_corr, rotation=45)
ax.set_yticks(range(len(variables_corr))); ax.set_yticklabels(variables_corr)
for i in range(len(variables_corr)):
    for j in range(len(variables_corr)):
        val = matriz.iloc[i, j]
        if pd.notna(val):
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8)
plt.colorbar(im)
plt.title("Matriz de correlación")
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/12_matriz_correlacion.png")
plt.close()

# ---------------------------------------------------------------
# 13-14. Distribución espacial de estaciones + PM2.5 promedio por estación
# ---------------------------------------------------------------
df_espacial = con.execute("""
    SELECT NOMBRE_EST, LATITUD, LONGITUD,
        AVG(CASE WHEN MSFL_CODE = 'PM2.5' THEN MED_CONCENTRACION_ESTANDAR END) AS pm25_promedio
    FROM datos_horarios
    GROUP BY NOMBRE_EST, LATITUD, LONGITUD
    HAVING pm25_promedio IS NOT NULL
""").df()

plt.figure(figsize=(8, 10))
sc = plt.scatter(df_espacial["LONGITUD"], df_espacial["LATITUD"],
                  c=df_espacial["pm25_promedio"], cmap="YlOrRd", s=60, edgecolor="k")
plt.colorbar(sc, label="PM2.5 promedio (µg/m³)")
plt.title("PM2.5 promedio por estación (distribución espacial)")
plt.xlabel("Longitud"); plt.ylabel("Latitud")
plt.tight_layout()
plt.savefig(f"{OUT_DIR}/13_14_mapa_pm25_estaciones.png")
plt.close()
print("\n== 13-14. Mapa de estaciones guardado ==")
print(df_espacial.sort_values("pm25_promedio", ascending=False).head(10))

# ---------------------------------------------------------------
# 15. Análisis de valores extremos (top 1% por contaminante)
# ---------------------------------------------------------------
for cod in CONTAMINANTES:
    df_extremos = con.execute(f"""
        WITH umbral AS (
            SELECT approx_quantile(MED_CONCENTRACION_ESTANDAR, 0.99) AS p99
            FROM datos_confiables WHERE MSFL_CODE = '{cod}'
        )
        SELECT d.NOMBRE_EST, d.DEPARTAMENTO, d.fecha_inicio, d.MED_CONCENTRACION_ESTANDAR
                FROM datos_horarios d, umbral u
                WHERE d.MSFL_CODE = '{cod}'
                    AND (
                            (d.MSFL_CODE = 'SO2' AND d.calidad_so2 = 'extremo_revisar')
                            OR (d.MSFL_CODE <> 'SO2' AND d.MED_CONCENTRACION_ESTANDAR > u.p99)
                    )
        ORDER BY d.MED_CONCENTRACION_ESTANDAR DESC
        LIMIT 5
    """).df()
    print(f"\n== 15. Top 5 valores extremos de {cod} (por encima del p99) ==")
    print(df_extremos)

con.close()
print(f"\nTodas las figuras se guardaron en: {OUT_DIR}/")