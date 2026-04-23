FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN useradd -u 10001 -m appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser mqtt_anomaly_consumer.py .
COPY --chown=appuser:appuser model_random_forest.joblib .

USER appuser

CMD ["python", "mqtt_anomaly_consumer.py"]