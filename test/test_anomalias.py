import duckdb
import pandas as pd

from src.analytics.anomalias import detectar_anomalias


def test_anomalias_usa_features_temporales_ciclicas(tmp_path):
    parquet = tmp_path / "datos.parquet"
    rows = 24
    pd.DataFrame(
        {
            "ESTACION_ID": [1] * rows,
            "NOMBRE_EST": ["Estacion prueba"] * rows,
            "MUNICIPIO": ["Bogota"] * rows,
            "TIPO_ESTACION": ["Fija"] * rows,
            "DEPARTAMENTO": ["Cundinamarca"] * rows,
            "fecha_inicio": pd.date_range("2024-01-01", periods=rows, freq="h"),
            "MED_CONCENTRACION_ESTANDAR": [20.0] * (rows - 1) + [500.0],
            "MSFL_CODE": ["PM2.5"] * rows,
            "es_horario": [True] * rows,
        }
    ).to_parquet(parquet, index=False)

    with duckdb.connect() as con:
        result = detectar_anomalias(con, "PM2.5", parquet)

    assert "estacion_cod" not in result.columns
    assert {"hora_sin", "hora_cos", "mes_sin", "mes_cos"}.issubset(result.columns)
    assert result["es_anomalia"].dtype == bool


def test_anomalias_maneja_contaminante_sin_datos(tmp_path):
    parquet = tmp_path / "datos.parquet"
    pd.DataFrame(
        {
            "ESTACION_ID": pd.Series(dtype="int64"),
            "NOMBRE_EST": pd.Series(dtype="str"),
            "MUNICIPIO": pd.Series(dtype="str"),
            "TIPO_ESTACION": pd.Series(dtype="str"),
            "DEPARTAMENTO": pd.Series(dtype="str"),
            "fecha_inicio": pd.Series(dtype="datetime64[ns]"),
            "MED_CONCENTRACION_ESTANDAR": pd.Series(dtype="float64"),
            "MSFL_CODE": pd.Series(dtype="str"),
            "es_horario": pd.Series(dtype="bool"),
        }
    ).to_parquet(parquet, index=False)

    with duckdb.connect() as con:
        result = detectar_anomalias(con, "PM10", parquet)

    assert result.empty
    assert "es_anomalia" in result.columns
