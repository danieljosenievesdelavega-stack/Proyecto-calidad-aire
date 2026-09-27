"""Detecta anomalías en mediciones horarias por contaminante."""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARQUET_LIMPIO = PROJECT_ROOT / "data" / "processed" / "calidad_aire_limpio.parquet"
OUT_DIR = PROJECT_ROOT / "data" / "processed" / "anomalias"
CONTAMINANTES = ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO"]
CONTAMINACION_ESPERADA = 0.01


def detectar_anomalias(con, cod, parquet_path=PARQUET_LIMPIO):
    """Devuelve las mediciones horarias etiquetadas por Isolation Forest."""
    df = con.execute(
        """
        SELECT ESTACION_ID, NOMBRE_EST, MUNICIPIO, TIPO_ESTACION, DEPARTAMENTO,
               fecha_inicio, MED_CONCENTRACION_ESTANDAR AS valor
               {calidad_so2}
        FROM read_parquet(?)
        WHERE MSFL_CODE = ? AND es_horario = true
        """.format(calidad_so2=", calidad_so2" if cod == "SO2" else ""),
        [str(parquet_path), cod],
    ).df()

    if df.empty:
        df["es_anomalia"] = pd.Series(dtype="bool")
        return df

    df["hora"] = df["fecha_inicio"].dt.hour
    df["mes"] = df["fecha_inicio"].dt.month
    df["dia_semana"] = df["fecha_inicio"].dt.dayofweek
    df["hora_sin"] = np.sin(2 * np.pi * df["hora"] / 24)
    df["hora_cos"] = np.cos(2 * np.pi * df["hora"] / 24)
    df["mes_sin"] = np.sin(2 * np.pi * df["mes"] / 12)
    df["mes_cos"] = np.cos(2 * np.pi * df["mes"] / 12)
    df["dia_sin"] = np.sin(2 * np.pi * df["dia_semana"] / 7)
    df["dia_cos"] = np.cos(2 * np.pi * df["dia_semana"] / 7)

    features = [
        "valor", "hora_sin", "hora_cos", "mes_sin", "mes_cos", "dia_sin", "dia_cos",
    ]
    if len(df) < 2:
        df["anomalia"] = 1
        df["es_anomalia"] = False
        return df

    modelo = IsolationForest(
        n_estimators=200,
        contamination=min(CONTAMINACION_ESPERADA, max(1 / len(df), 0.5)),
        random_state=42,
        n_jobs=-1,
    )
    df["anomalia"] = modelo.fit_predict(df[features])
    df["es_anomalia"] = df["anomalia"] == -1
    return df


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resumen_general = []

    with duckdb.connect() as con:
        for cod in CONTAMINANTES:
            print(f"\n=== Procesando {cod} ===")
            df = detectar_anomalias(con, cod)
            print(f"Registros cargados: {len(df):,}")

            n_anomalias = int(df["es_anomalia"].sum())
            porcentaje = n_anomalias / len(df) * 100 if len(df) else 0
            print(f"Anomalias detectadas: {n_anomalias:,} ({porcentaje:.2f}%)")

            if cod == "SO2" and not df.empty:
                tabla_cruzada = pd.crosstab(df["calidad_so2"], df["es_anomalia"])
                print("\nComparacion Isolation Forest vs. clasificacion manual (calidad_so2):")
                print(tabla_cruzada)

            salida = OUT_DIR / f"anomalias_{cod.replace('.', '')}.parquet"
            df.to_parquet(salida, index=False)
            print(f"Guardado en: {salida}")

            top_anomalias = df[df["es_anomalia"]].nlargest(10, "valor")[[
                "NOMBRE_EST", "DEPARTAMENTO", "fecha_inicio", "valor",
            ]]
            print(f"\nTop 10 anomalias mas extremas de {cod}:")
            print(top_anomalias.to_string(index=False))
            resumen_general.append({
                "contaminante": cod,
                "registros": len(df),
                "anomalias": n_anomalias,
                "pct_anomalias": round(porcentaje, 2),
            })

    print("\n\n=== RESUMEN GENERAL ===")
    print(pd.DataFrame(resumen_general).to_string(index=False))


if __name__ == "__main__":
    main()
