# Contributing to LoRa-IoT-Simulator

Thanks for your interest in improving the LoRa-IoT-Simulator! This document
explains how to set up a development environment, run the tests, and the
boundaries you must respect when submitting changes.

## Project layout

```
LoRa-IoT-Simulator/
├── simulator/        # STM32-style node + LoRa PHY link model (FROZEN CORE)
├── gateway/          # LoRa gateway packet collection (FROZEN CORE)
├── backend/          # FastAPI service, SQLite persistence, engine (CORE API)
├── frontend/         # Web dashboard (HTML/JS/CSS)
├── scripts/          # Headless CLI helpers (generate_experiment / export_report)
├── docs/             # Architecture and API reference
├── examples/         # Runnable example scripts
└── docker-compose.yml
```

## Frozen core policy

To keep the simulation model and historical experiment data reproducible, the
following directories are treated as a **frozen core** and must not change
behavior between releases:

- `simulator/`
- `gateway/`
- `backend/` (Python service)
- `frontend/` (dashboard)
- `requirements.txt`

Pull requests that modify these paths to add features will be reviewed very
carefully. Bug fixes that only touch *presentation/robustness* (e.g. defensive
`.get()` access, error handling) may be accepted if they do not alter the
simulation model or experiment logic.

The **release layer** — `LICENSE`, `README.md`, `CONTRIBUTING.md`,
`CHANGELOG.md`, `.github/`, `Dockerfile`, `docker-compose.yml`,
`scripts/`, `docs/`, `examples/`, `.gitignore` — is where most contributions
should land.

## Development setup

```bash
# Python 3.12+ recommended
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install pytest              # for tests

# Run the backend locally (needs a reachable MQTT broker)
cp .env.example .env
python -m backend.main

# Run the full stack with Docker
docker compose up --build
```

## Running tests

```bash
pytest backend/                 # backend API + engine unit tests
python simulator/run_demo.py    # smoke-run the node simulation
python gateway/run_demo.py      # smoke-run gateway collection
```

Headless scripts import from `backend` directly and never start the web server:

```bash
python scripts/generate_experiment.py --nodes 20 --area 400 --seed 1 --duration 60
python scripts/export_report.py --db experiments.db --out report.md
```

## Commit & PR guidelines

- Keep commits focused; describe the *why*, not just the *what*.
- Add a CHANGELOG.md entry under `Unreleased` for user-visible changes.
- Do not commit generated databases (`*.db`) or virtual environments (`venv/`).
- Open a PR against `master`; CI will run the backend test suite.

## Code of conduct

Be respectful, assume good intent, and keep discussions technical and
constructive.
