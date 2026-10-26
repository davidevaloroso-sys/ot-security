FROM python:3.15-alpine@sha256:d44b1254cb92329418d164b22b20d86bbd3869d48e80e09e476531a409a728bb
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
