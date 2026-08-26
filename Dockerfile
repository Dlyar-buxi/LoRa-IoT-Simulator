# LoRa-IoT-Simulator — backend image
#
# Build & run with Docker Compose (recommended):
#   docker compose up --build
#
# Or standalone:
#   docker build -t lora-iot-simulator .
#   docker run -p 8000:8000 -e MQTT_BROKER_URL=mqtt://host.docker.internal:1883 lora-iot-simulator
#
# The dashboard is served by the backend at http://localhost:8000/
# SQLite experiments are written to DB_PATH (mount a volume there to persist).

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (frozen core + release layer).
COPY simulator/ ./simulator/
COPY gateway/   ./gateway/
COPY backend/   ./backend/
COPY frontend/  ./frontend/
COPY scripts/   ./scripts/

# Defaults; override via Compose env / .env.
# experiments.db lives under /app/data so a named volume can persist it.
ENV DB_PATH=/app/data/experiments.db \
    MQTT_BROKER_URL=mqtt://mosquitto:1883

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
