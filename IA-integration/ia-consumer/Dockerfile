FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mqtt_anomaly_consumer.py .
COPY model_random_forest.joblib .

CMD ["python", "mqtt_anomaly_consumer.py"]