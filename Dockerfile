FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non usare root in produzione seria, ma per iniziare:
# RUN useradd -m appuser && chown -R appuser /app
# USER appuser

CMD ["python", "main.py"]