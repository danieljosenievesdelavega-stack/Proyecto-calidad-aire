from src.orquestacion import pipeline


def test_pipeline_ejecuta_fases_analiticas(monkeypatch):
    pasos = []
    estado = []
    monkeypatch.setattr(
        pipeline,
        "hay_actualizacion_nueva",
        lambda: (True, "2026-09-26T00:00:00Z"),
    )
    monkeypatch.setattr(pipeline, "correr_paso", pasos.append)
    monkeypatch.setattr(pipeline, "guardar_ultima_actualizacion", estado.append)

    pipeline.main()

    assert pasos == [
        "src/etl/extract.py",
        "src/etl/clean.py",
        "src/analytics/eda.py",
        "src/analytics/anomalias.py",
        "src/analytics/alertas.py",
    ]
    assert estado == ["2026-09-26T00:00:00Z"]
