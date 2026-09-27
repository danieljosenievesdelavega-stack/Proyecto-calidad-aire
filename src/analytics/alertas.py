"""Calcula episodios de excedencia de contaminantes criterio.

Las ventanas se calculan por tiempo real y solo se evalua una ventana cuando
alcanza la cobertura minima configurada. El calculo permanece en DuckDB para
evitar cargar millones de mediciones en pandas.
"""
import math
from pathlib import Path

import duckdb
import pandas as pd

PARQUET_LIMPIO = "data/processed/calidad_aire_limpio.parquet"
OUT_DIR = Path("data/processed/alertas")
COBERTURA_MINIMA = 0.75

# Limites oficiales convertidos a ug/m3 (condiciones de referencia 25C, 760 mmHg)
# Fuente: Resolucion 2254 de 2017, Ministerio de Ambiente y Desarrollo Sostenible
LIMITES = {
    # codigo: (ventana_horas, limite_ug_m3, descripcion_periodo)
    "PM2.5": (24, 37.0, "promedio movil 24h"),
    "PM10":  (24, 75.0, "promedio movil 24h"),
    "O3":    (8,  100.0, "promedio movil 8h"),
    "CO":    (8,  5038.0, "promedio movil 8h"),
    "SO2":   (1,  99.6, "valor horario (limite 1h)"),
    "NO2":   (1,  199.3, "valor horario (limite 1h)"),
}

def calcular_alertas(con, cod, ventana, limite, descripcion, parquet_path=PARQUET_LIMPIO):
    """Calcula y devuelve episodios para un contaminante sin materializar datos horarios."""
    min_observaciones = math.ceil(ventana * COBERTURA_MINIMA)
    query = f"""
        WITH datos AS (
            SELECT ESTACION_ID, NOMBRE_EST, DEPARTAMENTO, MUNICIPIO,
                   fecha_inicio, MED_CONCENTRACION_ESTANDAR AS valor
            FROM read_parquet(?)
            WHERE MSFL_CODE = ? AND es_horario = true
        ), rolling AS (
            SELECT *,
                AVG(valor) OVER ventana AS valor_rolling,
                COUNT(valor) OVER ventana AS observaciones_ventana
            FROM datos
            WINDOW ventana AS (
                PARTITION BY ESTACION_ID
                ORDER BY fecha_inicio
                RANGE BETWEEN INTERVAL '{ventana - 1} hours' PRECEDING AND CURRENT ROW
            )
        ), marcado AS (
            SELECT *,
                valor_rolling IS NOT NULL
                AND observaciones_ventana >= ?
                AND valor_rolling > ? AS excede
            FROM rolling
        ), continuidad AS (
            SELECT *,
                LAG(fecha_inicio) OVER estacion AS fecha_anterior,
                LAG(excede) OVER estacion AS excede_anterior
            FROM marcado
            WINDOW estacion AS (PARTITION BY ESTACION_ID ORDER BY fecha_inicio)
        ), numerado AS (
            SELECT *,
                SUM(CASE WHEN excede AND COALESCE(excede_anterior, false)
                              AND date_diff('minute', fecha_anterior, fecha_inicio) <= 90
                         THEN 0 ELSE 1 END)
                    OVER (PARTITION BY ESTACION_ID ORDER BY fecha_inicio) AS episodio_id
            FROM continuidad
        )
        SELECT ESTACION_ID, NOMBRE_EST, DEPARTAMENTO, MUNICIPIO,
               MIN(fecha_inicio) AS inicio,
               MAX(fecha_inicio) AS fin,
               COUNT(*) AS horas_excedencia,
               MAX(valor_rolling) AS pico_maximo,
               AVG(valor_rolling) AS promedio_episodio,
               ? AS contaminante,
               ? AS limite_normativo,
               ? AS descripcion_periodo
        FROM numerado
        WHERE excede
        GROUP BY ESTACION_ID, NOMBRE_EST, DEPARTAMENTO, MUNICIPIO, episodio_id
        ORDER BY ESTACION_ID, inicio
    """
    return con.execute(
        query,
        [str(parquet_path), cod, min_observaciones, limite, cod, limite, descripcion],
    ).df()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resumen = []

    with duckdb.connect() as con:
        for cod, (ventana, limite, descripcion) in LIMITES.items():
            print(f"\n=== {cod}: {descripcion}, limite {limite} ug/m3 ===")
            episodios = calcular_alertas(con, cod, ventana, limite, descripcion)
            salida = OUT_DIR / f"episodios_{cod.replace('.', '')}.parquet"
            episodios.to_parquet(salida, index=False)
            print(f"Episodios de excedencia detectados: {len(episodios):,}")
            print(f"Guardado en: {salida}")

            top5 = episodios.nlargest(5, "pico_maximo")[[
                "NOMBRE_EST", "DEPARTAMENTO", "inicio", "fin",
                "horas_excedencia", "pico_maximo",
            ]]
            print(f"\nTop 5 episodios mas severos de {cod}:")
            print(top5.to_string(index=False))
            resumen.append({
                "contaminante": cod,
                "limite_ug_m3": limite,
                "horas_con_excedencia": int(episodios["horas_excedencia"].sum()),
                "episodios_detectados": len(episodios),
            })

    print("\n\n=== RESUMEN GENERAL DE ALERTAS ===")
    print(pd.DataFrame(resumen).to_string(index=False))


if __name__ == "__main__":
    main()