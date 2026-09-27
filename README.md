# Monitoreo de calidad del aire en Colombia

Aplicativo web de analítica descriptiva para contaminantes atmosfericos criterio. El proyecto descarga y limpia datos de SISAIRE, calcula analisis reproducibles y expone un MVP web con API y dashboard.

## Instalar

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Los datos procesados deben existir en `data/processed/calidad_aire_limpio.parquet`. Para regenerarlos desde el CSV crudo:

```powershell
python src/etl/clean.py
python src/analytics/anomalias.py
python src/analytics/alertas.py
```

El pipeline completo se ejecuta con `python src/orquestacion/pipeline.py`. El
dataset de datos.gov.co se configura mediante `SISAIRE_DATASET_ID`; por defecto
se usa `g4t8-zkc3`. Las alertas solo evalúan ventanas con al menos 75% de
cobertura temporal y guardan episodios en `data/processed/alertas`.

Las mediciones se interpretan en hora local de Colombia. La presión `P` se
conserva con la unidad declarada por la fuente, aunque el informe de calidad
advierte que sus valores parecen estar expresados en hPa y no en mmHg.
El archivo `data/.estado_pipeline.json` registra la última actualización remota
procesada; ese estado solo se actualiza después de completar todas las fases.
Los artefactos derivados deben regenerarse cuando cambia el Parquet limpio.

## Ejecutar la API

Desde la raiz del proyecto:

```powershell
uvicorn src.api.main:app --reload
```

- Documentacion interactiva: http://127.0.0.1:8000/docs
- Salud: http://127.0.0.1:8000/health
- Resumen: http://127.0.0.1:8000/api/summary
- Alertas: http://127.0.0.1:8000/api/alerts?contaminant=PM2.5

La API devuelve HTTP 503 cuando el Parquet limpio o un artefacto analítico aún
no existe. Una respuesta vacía significa que el artefacto sí existe, pero no
hay resultados para los filtros solicitados. `AIR_ALLOWED_ORIGINS` permite
configurar los orígenes CORS separados por comas.

## Ejecutar el dashboard

En otra terminal:

```powershell
streamlit run src/dashboard/app.py
```

El dashboard permite seleccionar contaminante, consultar tendencia mensual, explorar estaciones en el mapa y revisar anomalías detectadas.
