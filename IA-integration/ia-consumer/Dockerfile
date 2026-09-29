FROM python:3.11-alpine@sha256:cd04730b8511def3fbf14204d66a0c1536f290b8e896ed5a94cd64cb15ac1356 AS dependencies
WORKDIR /build
COPY IA-integration/ia-consumer/requirements.txt ./requirements.txt
# scikit-learn 1.6.1 has no musllinux wheel. Build the pinned version with
# limited parallelism; the compiler and isolated build tools stay in this stage.
# Pass scikit-learn explicitly so pip forwards the Meson settings, and constrain
# its resolution to requirements.txt before pip inspects newer source releases.
RUN apk add --no-cache build-base \
    && pip install --no-cache-dir --prefix=/install \
        --config-settings=compile-args=-j2 \
        -c requirements.txt -r requirements.txt scikit-learn

FROM python:3.11-alpine@sha256:cd04730b8511def3fbf14204d66a0c1536f290b8e896ed5a94cd64cb15ac1356
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=dependencies /install /usr/local
COPY IA-integration/ia-consumer/requirements.txt ./requirements.txt
RUN apk upgrade --no-cache && apk add --no-cache libgomp libstdc++ \
    && pip check \
    && pip uninstall -y pip setuptools wheel \
    && adduser -D -u 10001 appuser
COPY ot_common.py ./
COPY IA-integration/ia-consumer/mqtt_anomaly_consumer.py ./
COPY IA-integration/ia-consumer/model_random_forest.joblib IA-integration/ia-consumer/training_metrics.json ./
USER 10001
CMD ["python", "mqtt_anomaly_consumer.py"]
