"""Descarga el CSV histórico de SISAIRE de forma atómica."""
import os
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ID = "g4t8-zkc3"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"


def descargar_dataset(
    dataset_id: str | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """Descarga el dataset y devuelve la ruta consolidada."""
    dataset_id = dataset_id or os.environ.get("SISAIRE_DATASET_ID", DEFAULT_DATASET_ID)
    output_dir.mkdir(parents=True, exist_ok=True)
    final_file = output_dir / "calidad_aire_completo.csv"
    temp_file = output_dir / "calidad_aire_completo.csv.part"
    url = f"https://www.datos.gov.co/api/views/{dataset_id}/rows.csv?accessType=DOWNLOAD"

    print(f"Iniciando descarga en streaming\nDestino temporal: {temp_file}")
    start_time = time.time()
    bytes_downloaded = 0

    try:
        with requests.get(url, stream=True, timeout=600) as response:
            response.raise_for_status()
            with temp_file.open("wb") as output:
                for chunk in response.iter_content(chunk_size=5 * 1024 * 1024):
                    if chunk:
                        output.write(chunk)
                        bytes_downloaded += len(chunk)

        os.replace(temp_file, final_file)
        elapsed = time.time() - start_time
        print(
            f"Descarga completada: {final_file} "
            f"({bytes_downloaded / (1024 * 1024):.2f} MB, {elapsed / 60:.2f} min)"
        )
        return final_file
    except BaseException:
        if temp_file.exists():
            temp_file.unlink()
        raise


if __name__ == "__main__":
    descargar_dataset()
