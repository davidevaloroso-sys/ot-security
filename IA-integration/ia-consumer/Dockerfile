FROM python:3.15-alpine@sha256:d44b1254cb92329418d164b22b20d86bbd3869d48e80e09e476531a409a728bb AS dependencies
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

FROM python:3.15-alpine@sha256:d44b1254cb92329418d164b22b20d86bbd3869d48e80e09e476531a409a728bb
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
