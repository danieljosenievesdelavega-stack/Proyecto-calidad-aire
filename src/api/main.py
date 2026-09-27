from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import queries

app = FastAPI(
    title="Calidad del Aire Colombia API",
    version="1.0.0",
    description="Consultas descriptivas sobre contaminantes atmosfericos criterio.",
)
allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "AIR_ALLOWED_ORIGINS",
        "http://localhost:8501,http://localhost:8502,http://127.0.0.1:8501,http://127.0.0.1:8502",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _validate_contaminant(contaminant: str) -> str:
    if contaminant not in queries.CONTAMINANTS:
        raise HTTPException(
            status_code=400,
            detail=f"Contaminante no soportado. Usa: {', '.join(queries.CONTAMINANTS)}",
        )
    return contaminant


@app.get("/health")
def health() -> dict[str, str]:
    if not queries.database_ready():
        raise HTTPException(status_code=503, detail="La base de datos no está disponible")
    return {"status": "ok", "data": "ready"}


@app.get("/api/summary")
def get_summary(
    department: str | None = Query(None),
    municipality: str | None = Query(None),
    station_type: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    include_extremes: bool = Query(False),
) -> dict[str, Any]:
    return queries.summary(
        department=department, municipality=municipality, station_type=station_type,
        start_date=start_date, end_date=end_date, include_extremes=include_extremes,
    )


@app.get("/api/contaminants")
def get_contaminants(
    department: str | None = Query(None),
    municipality: str | None = Query(None),
    station_type: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    include_extremes: bool = Query(False),
) -> list[dict[str, Any]]:
    return queries.contaminants(
        department=department, municipality=municipality, station_type=station_type,
        start_date=start_date, end_date=end_date, include_extremes=include_extremes,
    )


@app.get("/api/stations")
def get_stations(
    contaminant: str = Query("PM2.5"),
    limit: int = Query(278, ge=1, le=500),
    department: str | None = Query(None),
    municipality: str | None = Query(None),
    station_type: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    include_extremes: bool = Query(False),
) -> list[dict[str, Any]]:
    return queries.stations(
        _validate_contaminant(contaminant), limit, department, municipality,
        start_date, end_date, station_type, include_extremes,
    )


@app.get("/api/trend")
def get_trend(
    contaminant: str = Query("PM2.5"),
    station_id: int | None = Query(None),
    department: str | None = Query(None),
    municipality: str | None = Query(None),
    station_type: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    include_extremes: bool = Query(False),
) -> list[dict[str, Any]]:
    return queries.trend(
        _validate_contaminant(contaminant), station_id, department, municipality,
        station_type, start_date, end_date, include_extremes,
    )


@app.get("/api/anomalies")
def get_anomalies(
    contaminant: str = Query("PM2.5"),
    limit: int = Query(50, ge=1, le=500),
    department: str | None = Query(None),
    municipality: str | None = Query(None),
    station_type: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> list[dict[str, Any]]:
    return queries.anomalies(
        _validate_contaminant(contaminant),
        limit=limit,
        department=department,
        municipality=municipality,
        station_type=station_type,
        start_date=start_date,
        end_date=end_date,
    )


@app.get("/api/alerts")
def get_alerts(
    contaminant: str = Query("PM2.5"),
    limit: int = Query(50, ge=1, le=500),
    department: str | None = Query(None),
    municipality: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> list[dict[str, Any]]:
    return queries.alert_episodes(
        _validate_contaminant(contaminant), limit, department, municipality,
        start_date, end_date,
    )
