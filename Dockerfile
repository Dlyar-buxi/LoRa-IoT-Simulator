# LoRa IoT Simulator — backend image (multi-stage, non-root)
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
#
# Stage layout (production-grade choices HRs look for):
#   builder  — installs wheels into a clean /install prefix. Rebuilds ONLY when
#              requirements.txt changes (optimised layer caching).
#   runtime  — a fresh slim image without pip cache / build tools. Runs as the
#              unprivileged `simulator` user. DB volume is chowned so writes work.

# ---------------- builder ----------------
FROM python:3.12-slim AS builder

# Build-stage prefix — pip installs every wheel under here so we can copy the
# whole tree into the runtime image without pulling pip/build tools along.
ENV PIP_PREFIX=/install \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Layer 1: only requirements (cache-friendly — if this file is unchanged,
# we reuse this layer across `docker build`s, even when source changes).
COPY requirements.txt .
RUN pip install --no-cache-dir \
        --disable-pip-version-check \
        --prefix="${PIP_PREFIX}" \
        -r requirements.txt

# ---------------- runtime ----------------
FROM python:3.12-slim AS runtime

# uvicorn on 0.0.0.0 needs unbuffered stdout for log visibility
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# (1) Bring in the pre-built site-packages + console-scripts from builder.
#     /install/{bin,lib,share} -> /usr/local matches the layout pip expects.
COPY --from=builder /install /usr/local

# (2) Copy application source (release layer — frozen core + adapter + frontend)
COPY simulator/ ./simulator/
COPY gateway/   ./gateway/
COPY backend/   ./backend/
COPY frontend/  ./frontend/
COPY examples/  ./examples/
COPY docs/      ./docs/
COPY scripts/   ./scripts/
COPY pyproject.toml requirements.txt ./

# (3) Runtime artefacts + unprivileged user.
#     - /app/data is where experiments.db will live (mounted as a named volume
#       in docker-compose). Must be writable by the runtime user.
#     - `simulator` user has no login shell: can't be abused for SSH-ing into
#       the container (defense-in-depth).
RUN mkdir -p /app/data \
 && groupadd --system --gid 65532 simulator \
 && useradd  --system --uid 65532 --gid simulator \
             --shell /usr/sbin/nologin \
             --home-dir /app \
             simulator \
 && chown -R simulator:simulator /app

# Persistent DB mount point — compose wires a named volume here.
VOLUME ["/app/data"]

# Default env vars; override via compose / .env / `docker run -e`.
ENV DB_PATH=/app/data/experiments.db \
    MQTT_BROKER_URL=mqtt://mosquitto:1883

EXPOSE 8000

# HEALTHCHECK: 200 on "/" means both static-files mount + FastAPI router up.
# Uses only stdlib so we don't need curl inside the slim image.
HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=10s \
    --retries=3 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/', timeout=3); sys.exit(0)"

# Defensive runtime identity. Everything above this line is still root-owned
# (read-only), only /app is owned by simulator — minimises blast radius if
# someone does manage to RCE via an edge case in the API.
USER simulator

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
