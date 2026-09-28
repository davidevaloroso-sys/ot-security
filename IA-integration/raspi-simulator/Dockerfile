FROM python:3.11-alpine@sha256:cd04730b8511def3fbf14204d66a0c1536f290b8e896ed5a94cd64cb15ac1356
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
