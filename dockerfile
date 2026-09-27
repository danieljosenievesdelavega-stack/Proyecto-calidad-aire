FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt


COPY src ./src

# Exponemos los puertos (8501 para Streamlit, 8000 si tienes una API extra)
EXPOSE 8501 8000

CMD ["python", "-m", "streamlit", "run", "src/dashboard/app.py", "--server.port=8501"]