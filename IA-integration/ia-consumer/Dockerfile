FROM python:3.14-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d
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
