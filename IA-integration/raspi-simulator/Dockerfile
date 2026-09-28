FROM python:3.14-alpine@sha256:9e9fde4d32eedce0b661d9ab91e826b62dddf28e928c230ec55f1866cac66b01
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY IA-integration/raspi-simulator/requirements.txt ./requirements.txt
RUN apk upgrade --no-cache \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip setuptools wheel \
    && adduser -D -u 10001 appuser
COPY ot_common.py ./
COPY IA-integration/raspi-simulator/main.py ./
USER 10001
CMD ["python", "main.py"]
