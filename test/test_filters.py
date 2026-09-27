from src.api import queries
import duckdb


def test_trend_accepts_dashboard_filters():
    rows = queries.trend(
        contaminant="PM2.5",
        start_date="2024-01-01",
        end_date="2024-12-31",
        station_type="Fija",
        include_extremes=False,
    )

    assert isinstance(rows, list)


def test_mobile_filter_uses_station_name_and_excludes_it_from_fixed():
    connection = duckdb.connect()
    connection.execute("""
        CREATE TABLE sample_stations (
            TIPO_ESTACION VARCHAR,
            NOMBRE_EST VARCHAR,
            es_horario BOOLEAN
        )
    """)
    connection.executemany(
        "INSERT INTO sample_stations VALUES (?, ?, TRUE)",
        [
            ("Fija", "MOVIL KOICA"),
            ("Fija", "MÓVIL FONTIBÓN"),
            ("Fija", "Estación fija"),
            ("Móvil", "Unidad oficial"),
            ("Fija", None),
        ],
    )

    mobile_filters, mobile_params = queries._build_filters(
        station_type="Móvil", include_extremes=True
    )
    mobile_names = {
        row[0]
        for row in connection.execute(
            f"SELECT NOMBRE_EST FROM sample_stations WHERE {' AND '.join(mobile_filters)}",
            mobile_params,
        ).fetchall()
    }

    fixed_filters, fixed_params = queries._build_filters(
        station_type="Fija", include_extremes=True
    )
    fixed_names = {
        row[0]
        for row in connection.execute(
            f"SELECT NOMBRE_EST FROM sample_stations WHERE {' AND '.join(fixed_filters)}",
            fixed_params,
        ).fetchall()
    }

    connection.close()
    assert mobile_names == {"MOVIL KOICA", "MÓVIL FONTIBÓN", "Unidad oficial"}
    assert fixed_names == {"Estación fija", None}
