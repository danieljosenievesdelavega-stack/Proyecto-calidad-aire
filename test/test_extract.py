from pathlib import Path

import pytest
import requests

from src.etl import extract


class FailedResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def raise_for_status(self):
        raise requests.exceptions.ConnectionError("fallo simulado")


def test_descarga_propaga_error_y_elimina_temporal(monkeypatch, tmp_path):
    output_dir = Path(tmp_path)
    temporary = output_dir / "calidad_aire_completo.csv.part"
    temporary.write_bytes(b"incompleto")
    monkeypatch.setattr(extract.requests, "get", lambda *args, **kwargs: FailedResponse())

    with pytest.raises(requests.exceptions.ConnectionError):
        extract.descargar_dataset("dataset-prueba", output_dir)

    assert not temporary.exists()
    assert not (output_dir / "calidad_aire_completo.csv").exists()
