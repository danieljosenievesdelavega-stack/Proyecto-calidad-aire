import pytest

from src.api import queries


def test_missing_base_artifact_is_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr(queries, "DATA_PATH", tmp_path / "missing.parquet")

    with pytest.raises(queries.ArtifactUnavailableError):
        queries.summary()


def test_missing_derived_artifact_is_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr(queries, "ANOMALIES_PATH", tmp_path)

    with pytest.raises(queries.ArtifactUnavailableError):
        queries.anomalies("PM2.5")


def test_latest_measurement_date_reads_pipeline_metadata(monkeypatch):
    from datetime import date

    class Result:
        def scalar_one_or_none(self):
            return date(2025, 4, 30)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query):
            assert "MAX(fecha_max)" in str(query)
            return Result()

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            pass

    monkeypatch.setattr(queries, "load_dotenv", lambda *_args: None)
    monkeypatch.setattr(queries, "create_engine", lambda _url: Engine())
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")

    assert queries.latest_measurement_date() == date(2025, 4, 30)


def test_latest_measurement_date_is_optional_without_database_url(monkeypatch):
    monkeypatch.setattr(queries, "load_dotenv", lambda *_args: None)
    monkeypatch.setenv("DATABASE_URL", "")

    assert queries.latest_measurement_date() is None
