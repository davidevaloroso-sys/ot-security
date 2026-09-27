FROM python:3.11-slim@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY IA-integration/ia-consumer/requirements.txt ./requirements.txt
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip setuptools wheel \
    && useradd -u 10001 -m appuser
COPY ot_common.py ./
COPY IA-integration/ia-consumer/mqtt_anomaly_consumer.py ./
COPY IA-integration/ia-consumer/model_random_forest.joblib IA-integration/ia-consumer/training_metrics.json ./
USER 10001
CMD ["python", "mqtt_anomaly_consumer.py"]
