"""
Orquestador: verifica actualizacion -> descarga -> limpia
Ubicacion: src/orquestacion/pipeline.py
Corre esto desde el programador de tareas (o Prefect/cron mas adelante).
"""
import logging
import subprocess
import sys
from pathlib import Path

# Raíz del proyecto
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

# Configurar carpeta y archivo de logs
LOGS_DIR = RAIZ / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "pipeline.log"

# Configuración del Logger (consola + archivo)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

from src.orquestacion.verificar_actualizacion import hay_actualizacion_nueva, guardar_ultima_actualizacion


def correr_paso(ruta_relativa):
    logging.info("=" * 50)
    logging.info(f"Corriendo: {ruta_relativa}")
    logging.info("=" * 50)
    
    # Ejecuta el script subproceso y captura sus logs
    resultado = subprocess.run(
        [sys.executable, str(RAIZ / ruta_relativa)],
        cwd=RAIZ,
        capture_output=True,
        text=True
    )
    
    # Imprime la salida del subproceso en los logs
    if resultado.stdout:
        logging.info(resultado.stdout.strip())
    if resultado.stderr:
        logging.error(resultado.stderr.strip())

    if resultado.returncode != 0:
        raise RuntimeError(f"{ruta_relativa} fallo con codigo {resultado.returncode}")


def main():
    hay_nueva, timestamp_remoto = hay_actualizacion_nueva()

    if not hay_nueva:
        logging.info("No hay nada que hacer. Pipeline no se ejecuta.")
        return

    try:
        correr_paso("src/etl/extract.py")
        correr_paso("src/etl/clean.py")
        correr_paso("src/analytics/eda.py")
        correr_paso("src/analytics/anomalias.py")
        correr_paso("src/analytics/alertas.py")

        guardar_ultima_actualizacion(timestamp_remoto)
        logging.info("Pipeline completado con exito. Estado actualizado.")

    except Exception as e:
        logging.error(f"Pipeline fallo, NO se actualiza el estado: {e}")
        raise


if __name__ == "__main__":
    main()