FROM python:3.11-slim

WORKDIR /app

# Dipendenze di sistema essenziali
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia script e modello
COPY mqtt_anomaly_consumer.py .
COPY model_random_forest.joblib .

ENV PYTHONUNBUFFERED=1

CMD ["python", "mqtt_anomaly_consumer.py"]