"""
Verifica si el dataset de datos.gov.co se actualizo desde la ultima corrida,
consultando solo la metadata (liviano), no el archivo completo.
"""
import json
import logging
import os
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_ID = os.environ.get("SISAIRE_DATASET_ID", "g4t8-zkc3")
METADATA_URL = f"https://www.datos.gov.co/api/views/{DATASET_ID}.json"
ESTADO_PATH = PROJECT_ROOT / "data" / ".estado_pipeline.json"


def obtener_ultima_actualizacion_remota():
    resp = requests.get(METADATA_URL, timeout=30)
    resp.raise_for_status()
    metadata = resp.json()
    return metadata["rowsUpdatedAt"]


def obtener_ultima_actualizacion_local():
    if ESTADO_PATH.exists():
        return json.loads(ESTADO_PATH.read_text(encoding="utf-8")).get("ultima_actualizacion")
    return None


def guardar_ultima_actualizacion(timestamp):
    ESTADO_PATH.parent.mkdir(parents=True, exist_ok=True)
    ESTADO_PATH.write_text(
        json.dumps({"ultima_actualizacion": timestamp}), encoding="utf-8"
    )


def hay_actualizacion_nueva():
    remota = obtener_ultima_actualizacion_remota()
    local = obtener_ultima_actualizacion_local()
    if local is None:
        logging.info("Primera ejecucion, no hay estado previo guardado.")
        return True, remota
    if remota > local:
        logging.info(f"Dataset actualizado: {local} -> {remota}")
        return True, remota
    logging.info("Sin cambios en el dataset desde la ultima corrida.")
    return False, remota


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    hay_nueva, timestamp_remoto = hay_actualizacion_nueva()
    logging.info(f"¿Hay actualizacion nueva?: {hay_nueva}")