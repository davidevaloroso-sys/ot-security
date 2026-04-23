FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN groupadd -g 10001 appgroup \
    && useradd -u 10001 -g 10001 -m appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=10001:10001 mqtt_anomaly_consumer.py .
COPY --chown=10001:10001 model_random_forest.joblib .

USER 10001

CMD ["python", "mqtt_anomaly_consumer.py"]