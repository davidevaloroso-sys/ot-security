FROM python:3.11-slim@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY IA-integration/raspi-simulator/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd -u 10001 -m appuser
COPY ot_common.py ./
COPY IA-integration/raspi-simulator/main.py ./
USER 10001
CMD ["python", "main.py"]
