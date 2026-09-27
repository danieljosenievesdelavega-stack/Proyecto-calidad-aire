"""
Capa de consultas para el dashboard/API -- version Postgres (Supabase/Neon).
Reemplaza la version anterior que leia el Parquet local con DuckDB.

Requiere: pip install sqlalchemy psycopg2-binary python-dotenv
Variable de entorno DATABASE_URL apuntando a Supabase/Neon.
"""
from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
_engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=5)

CONTAMINANTS = ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO"]


def _rows(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with _engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]


def database_ready() -> bool:
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def _build_filters(
    *,
    contaminant: str | None = None,
    department: str | None = None,
    municipality: str | None = None,
    station_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Filtros comunes sobre medias_diarias (m) + estaciones (e), ya unidas en cada query."""
    filters: list[str] = []
    params: dict[str, Any] = {}

    if contaminant:
        filters.append("m.msfl_code = :contaminant")
        params["contaminant"] = contaminant
    if department:
        filters.append("e.departamento = :department")
        params["department"] = department
    if municipality:
        filters.append("e.municipio = :municipality")
        params["municipality"] = municipality
    if station_type:
        filters.append("UPPER(e.tipo_estacion) = UPPER(:station_type)")
        params["station_type"] = station_type
    if start_date:
        filters.append("m.fecha >= CAST(:start_date AS DATE)")
        params["start_date"] = start_date
    if end_date:
        filters.append("m.fecha <= CAST(:end_date AS DATE)")
        params["end_date"] = end_date

    return filters, params


def _registros_col(include_extremes: bool) -> str:
    return "registros" if include_extremes else "registros_sin_extremos"


def _promedio_col(include_extremes: bool) -> str:
    return "promedio" if include_extremes else "promedio_sin_extremos"


def summary(
    *,
    department: str | None = None,
    municipality: str | None = None,
    station_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_extremes: bool = False,
) -> dict[str, Any]:
    filters, params = _build_filters(
        department=department, municipality=municipality, station_type=station_type,
        start_date=start_date, end_date=end_date,
    )
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    registros_col = _registros_col(include_extremes)

    rows = _rows(
        f"""
        SELECT
            SUM(m.{registros_col}) AS records,
            COUNT(DISTINCT m.estacion_id) AS stations,
            COUNT(DISTINCT m.msfl_code) AS variables,
            MIN(m.fecha) AS start_date,
            MAX(m.fecha) AS end_date
        FROM medias_diarias m
        JOIN estaciones e ON e.estacion_id = m.estacion_id
        {where_clause}
        """,
        params,
    )
    return rows[0]


def contaminants(
    *,
    department: str | None = None,
    municipality: str | None = None,
    station_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_extremes: bool = False,
) -> list[dict[str, Any]]:
    filters, params = _build_filters(
        department=department, municipality=municipality, station_type=station_type,
        start_date=start_date, end_date=end_date,
    )
    filters.append("m.msfl_code = ANY(:contaminantes)")
    params["contaminantes"] = CONTAMINANTS
    where_clause = f"WHERE {' AND '.join(filters)}"
    registros_col = _registros_col(include_extremes)
    promedio_col = _promedio_col(include_extremes)

    return _rows(
        f"""
        SELECT
            m.msfl_code AS contaminant,
            SUM(m.{registros_col}) AS records,
            ROUND((
                SUM(m.{promedio_col} * m.{registros_col}) / NULLIF(SUM(m.{registros_col}), 0)
            )::numeric, 3) AS average,
            ROUND(MIN(m.minimo)::numeric, 3) AS minimum,
            ROUND(MAX(m.maximo)::numeric, 3) AS maximum
        FROM medias_diarias m
        JOIN estaciones e ON e.estacion_id = m.estacion_id
        {where_clause}
        GROUP BY m.msfl_code
        ORDER BY records DESC
        """,
        params,
    )


def stations(
    contaminant: str = "PM2.5",
    limit: int = 100,
    department: str | None = None,
    municipality: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    station_type: str | None = None,
    include_extremes: bool = False,
) -> list[dict[str, Any]]:
    filters, params = _build_filters(
        contaminant=contaminant, department=department, municipality=municipality,
        station_type=station_type, start_date=start_date, end_date=end_date,
    )
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    registros_col = _registros_col(include_extremes)
    promedio_col = _promedio_col(include_extremes)
    params["limit"] = limit

    return _rows(
        f"""
        SELECT
            e.estacion_id AS station_id, e.nombre AS station,
            e.municipio AS municipality, e.departamento AS department,
            e.latitud AS latitude, e.longitud AS longitude,
            SUM(m.{registros_col}) AS records,
            ROUND((
                SUM(m.{promedio_col} * m.{registros_col}) / NULLIF(SUM(m.{registros_col}), 0)
            )::numeric, 3) AS average
        FROM medias_diarias m
        JOIN estaciones e ON e.estacion_id = m.estacion_id
        {where_clause}
        GROUP BY e.estacion_id, e.nombre, e.municipio, e.departamento, e.latitud, e.longitud
        ORDER BY average DESC
        LIMIT :limit
        """,
        params,
    )


def station_count(
    contaminant: str,
    department: str | None = None,
    municipality: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    station_type: str | None = None,
    include_extremes: bool = False,
) -> int:
    filters, params = _build_filters(
        contaminant=contaminant, department=department, municipality=municipality,
        station_type=station_type, start_date=start_date, end_date=end_date,
    )
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    rows = _rows(
        f"""
        SELECT COUNT(DISTINCT m.estacion_id) AS stations
        FROM medias_diarias m
        JOIN estaciones e ON e.estacion_id = m.estacion_id
        {where_clause}
        """,
        params,
    )
    return int(rows[0]["stations"])


def trend(
    contaminant: str = "PM2.5",
    station_id: int | None = None,
    department: str | None = None,
    municipality: str | None = None,
    station_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_extremes: bool = False,
) -> list[dict[str, Any]]:
    filters, params = _build_filters(
        contaminant=contaminant, department=department, municipality=municipality,
        station_type=station_type, start_date=start_date, end_date=end_date,
    )
    if station_id is not None:
        filters.append("m.estacion_id = :station_id")
        params["station_id"] = station_id
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    registros_col = _registros_col(include_extremes)
    promedio_col = _promedio_col(include_extremes)

    # NOTA: el p95 mensual aqui es un PROMEDIO de los p95 diarios, no el p95 real
    # recalculado sobre datos horarios -- es una aproximacion aceptada al perder
    # el detalle horario en la capa de agregados. Documentar esta limitacion.
    return _rows(
        f"""
        SELECT
            DATE_TRUNC('month', m.fecha) AS period,
            ROUND((
                SUM(m.{promedio_col} * m.{registros_col}) / NULLIF(SUM(m.{registros_col}), 0)
            )::numeric, 3) AS average,
            ROUND(AVG(m.p95)::numeric, 3) AS p95,
            SUM(m.{registros_col}) AS records
        FROM medias_diarias m
        JOIN estaciones e ON e.estacion_id = m.estacion_id
        {where_clause}
        GROUP BY period
        ORDER BY period
        """,
        params,
    )


def _build_anomaly_filters(
    contaminant: str,
    department: str | None,
    municipality: str | None,
    station_type: str | None,
    start_date: str | None,
    end_date: str | None,
) -> tuple[list[str], dict[str, Any]]:
    filters = ["a.msfl_code = :contaminant"]
    params: dict[str, Any] = {"contaminant": contaminant}
    if department:
        filters.append("e.departamento = :department")
        params["department"] = department
    if municipality:
        filters.append("e.municipio = :municipality")
        params["municipality"] = municipality
    if station_type:
        filters.append("UPPER(e.tipo_estacion) = UPPER(:station_type)")
        params["station_type"] = station_type
    if start_date:
        filters.append("a.fecha_hora::DATE >= CAST(:start_date AS DATE)")
        params["start_date"] = start_date
    if end_date:
        filters.append("a.fecha_hora::DATE <= CAST(:end_date AS DATE)")
        params["end_date"] = end_date
    return filters, params


def anomalies(
    contaminant: str = "PM2.5",
    limit: int = 50,
    department: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    municipality: str | None = None,
    station_type: str | None = None,
) -> list[dict[str, Any]]:
    filters, params = _build_anomaly_filters(
        contaminant, department, municipality, station_type, start_date, end_date
    )
    params["limit"] = limit
    where_clause = " AND ".join(filters)

    return _rows(
        f"""
        SELECT a.estacion_id AS station_id, e.nombre AS station,
               e.departamento AS department, a.fecha_hora AS date,
               ROUND(a.valor::numeric, 3) AS value
        FROM anomalias a
        JOIN estaciones e ON e.estacion_id = a.estacion_id
        WHERE {where_clause}
        ORDER BY a.valor DESC
        LIMIT :limit
        """,
        params,
    )


def anomaly_count(
    contaminant: str = "PM2.5",
    department: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    municipality: str | None = None,
    station_type: str | None = None,
) -> int:
    filters, params = _build_anomaly_filters(
        contaminant, department, municipality, station_type, start_date, end_date
    )
    where_clause = " AND ".join(filters)

    rows = _rows(
        f"""
        SELECT COUNT(*) AS total
        FROM anomalias a
        JOIN estaciones e ON e.estacion_id = a.estacion_id
        WHERE {where_clause}
        """,
        params,
    )
    return int(rows[0]["total"])


def alert_episodes(
    contaminant: str = "PM2.5",
    limit: int = 50,
    department: str | None = None,
    municipality: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    filters = ["al.msfl_code = :contaminant"]
    params: dict[str, Any] = {"contaminant": contaminant, "limit": limit}
    if department:
        filters.append("e.departamento = :department")
        params["department"] = department
    if municipality:
        filters.append("e.municipio = :municipality")
        params["municipality"] = municipality
    if start_date:
        filters.append("al.inicio::DATE >= CAST(:start_date AS DATE)")
        params["start_date"] = start_date
    if end_date:
        filters.append("al.fin::DATE <= CAST(:end_date AS DATE)")
        params["end_date"] = end_date
    where_clause = " AND ".join(filters)

    return _rows(
        f"""
        SELECT e.nombre AS station, e.departamento AS department, e.municipio AS municipality,
               al.inicio AS start, al.fin AS end, al.horas_excedencia AS hours,
               ROUND(al.pico_maximo::numeric, 2) AS peak_value,
               ROUND(al.limite_normativo::numeric, 2) AS legal_limit,
               ROUND((al.pico_maximo / al.limite_normativo)::numeric, 2) AS severity_ratio
        FROM alertas_episodios al
        JOIN estaciones e ON e.estacion_id = al.estacion_id
        WHERE {where_clause}
        ORDER BY al.pico_maximo DESC
        LIMIT :limit
        """,
        params,
    )


def alert_episode_count(
    contaminant: str = "PM2.5",
    department: str | None = None,
    municipality: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> int:
    filters = ["al.msfl_code = :contaminant"]
    params: dict[str, Any] = {"contaminant": contaminant}
    if department:
        filters.append("e.departamento = :department")
        params["department"] = department
    if municipality:
        filters.append("e.municipio = :municipality")
        params["municipality"] = municipality
    if start_date:
        filters.append("al.inicio::DATE >= CAST(:start_date AS DATE)")
        params["start_date"] = start_date
    if end_date:
        filters.append("al.fin::DATE <= CAST(:end_date AS DATE)")
        params["end_date"] = end_date
    where_clause = " AND ".join(filters)

    rows = _rows(
        f"""
        SELECT COUNT(*) AS total
        FROM alertas_episodios al
        JOIN estaciones e ON e.estacion_id = al.estacion_id
        WHERE {where_clause}
        """,
        params,
    )
    return int(rows[0]["total"])


def locations(
    contaminant: str | None = None,
    department: str | None = None,
    municipality: str | None = None,
    station_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_extremes: bool = False,
) -> list[dict[str, Any]]:
    filters, params = _build_filters(
        contaminant=contaminant, department=department, municipality=municipality,
        station_type=station_type, start_date=start_date, end_date=end_date,
    )
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    return _rows(
        f"""
        SELECT DISTINCT e.estacion_id AS station_id, e.nombre AS station,
               e.municipio AS municipality, e.departamento AS department,
               e.latitud AS latitude, e.longitud AS longitude
        FROM medias_diarias m
        JOIN estaciones e ON e.estacion_id = m.estacion_id
        {where_clause}
        ORDER BY station_id
        """,
        params,
    )


def pipeline_status() -> dict[str, Any]:
    """Nuevo: para mostrar 'ultima medicion disponible' en el dashboard."""
    rows = _rows(
        """
        SELECT dataset_actualizado_en, ejecutado_en, total_registros,
               total_estaciones, fecha_min, fecha_max
        FROM pipeline_metadata
        ORDER BY ejecutado_en DESC
        LIMIT 1
        """
    )
    return rows[0] if rows else {}