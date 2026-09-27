import duckdb
import pandas as pd

from src.analytics.alertas import calcular_alertas


def _write_measurements(path, hours):
    frame = pd.DataFrame(
        {
            "ESTACION_ID": [1] * hours,
            "NOMBRE_EST": ["Estacion prueba"] * hours,
            "DEPARTAMENTO": ["Cundinamarca"] * hours,
            "MUNICIPIO": ["Bogota"] * hours,
            "fecha_inicio": pd.date_range("2024-01-01", periods=hours, freq="h"),
            "MED_CONCENTRACION_ESTANDAR": [40.0] * hours,
            "MSFL_CODE": ["PM2.5"] * hours,
            "es_horario": [True] * hours,
        }
    )
    frame.to_parquet(path, index=False)


def test_alerta_exige_cobertura_minima(tmp_path):
    parquet = tmp_path / "datos.parquet"
    _write_measurements(parquet, 30)

    with duckdb.connect() as con:
        result = calcular_alertas(con, "PM2.5", 24, 37.0, "promedio movil 24h", parquet)

    assert len(result) == 1
    assert result.iloc[0]["horas_excedencia"] == 13


def test_alerta_no_evalua_ventana_incompleta(tmp_path):
    parquet = tmp_path / "datos.parquet"
    _write_measurements(parquet, 10)

    with duckdb.connect() as con:
        result = calcular_alertas(con, "PM2.5", 24, 37.0, "promedio movil 24h", parquet)

    assert result.empty
