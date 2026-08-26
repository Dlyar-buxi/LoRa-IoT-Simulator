# Contributing to LoRa-IoT-Simulator

Thanks for your interest in improving the LoRa-IoT-Simulator! This document
explains how to set up a development environment, run the test and lint
tooling, and the boundaries you must respect when submitting changes.

## Project layout

```
LoRa-IoT-Simulator/
├── simulator/        # STM32-style node + LoRa PHY link model (FROZEN CORE)
├── gateway/          # LoRa gateway packet collection (FROZEN CORE)
├── backend/          # FastAPI service, SQLite persistence, engine (Adapter)
├── frontend/         # Web dashboard (vanilla JS + SVG)
├── scripts/          # Headless CLI helpers + benchmark runners
├── docs/             # Architecture, API reference, benchmark artifacts
├── examples/         # Runnable example scripts
└── docker-compose.yml
```

## Frozen core policy

To keep the simulation model and historical experiment data **byte-level
reproducible**, the following directories are treated as a **frozen core** and
must not change observable behaviour between releases:

- `simulator/`
- `gateway/`

Pull requests that touch these paths are only accepted for:

1. **Type annotations, docstrings and comments** that do not change runtime
   behaviour (no import movement, no value changes).
2. **Security / data-loss fixes** only, with a clear proof that the frozen
   output has changed and a bug report exists.

Bug fixes in the **Adapter layer** (`backend/`, `frontend/`, `scripts/`,
`docs/`, packaging and CI) are the normal path for feature work and
engineering hardening.

The **release layer** — `LICENSE`, `README.md`, `CONTRIBUTING.md`,
`CHANGELOG.md`, `SECURITY.md`, `.github/`, `Dockerfile`,
`.dockerignore`, `docker-compose.yml`, `scripts/`, `docs/`,
`examples/`, `pyproject.toml`, `requirements*.txt`, `.pre-commit-config.yaml`
— is where most packaging and process contributions should land.

## Development setup

Python 3.12+ recommended (CI matrix tests 3.11, 3.12, and 3.13).

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pre-commit install              # OPTIONAL — guards every commit

# Run the backend locally (broker-down degrades silently)
cp .env.example .env
python -m backend.main

# Run the full stack with Docker
docker compose up --build
```

## Lint & Format

This project uses **Ruff** as the unified linter + formatter (replaces flake8,
isort, and black). The frozen core directories are on per-file allowlists so
style-only PRs never pressure us into touching reproducible model code.

```bash
# Lint (fail on unfixable issues; autofixable issues are reported with [*])
python -m ruff check .

# Auto-fix autofixable issues (import sort, Optional -> X|None, try/except/pass -> suppress, …)
python -m ruff check --fix .

# Apply the project formatter (line-length=88, target-version=py312)
python -m ruff format .

# CI-equivalent — what the quality job runs on every push/PR
python -m ruff check . && python -m ruff format --check .
```

### Lint rules in use

- `E` / `F` — pyflakes + pycodestyle (excludes `E501` line-length; formatter owns that)
- `I` — isort import grouping.
- `UP` — pyupgrade (Python 3.12 modernisms, e.g. `X | None`).
- `B` — flake8-bugbear.
- `SIM` — flake8-simplify (ternaries, nested-if, suppress, etc.).

Per-file ignore directives live in `pyproject.toml` under
`[tool.ruff.lint.per-file-ignores]`. Known entries:

| Glob | Ignored rules | Why |
|------|---------------|-----|
| `simulator/*` | F401, F841, E402, F722, B008 | Frozen core |
| `gateway/*`   | F401, F841, E402               | Frozen core |
| `test_*.py`   | F841                           | Tests keep placeholder locals for readability |
| `scripts/**/*.py` | F401, F841                | Benchmark/runners allow unused glue code |

## Running tests

Regression target: **23/23** across backend, simulator, and gateway. All tests
are hermetic (`tempfile` / `:memory:` / `DB_ENABLED=false`) and never leave
artefacts in the project directory.

```bash
# Full suite + coverage (fail-under=60%, same as CI)
python -m pytest --cov --cov-fail-under=60 backend/ simulator/ gateway/ -q

# Just backend (API + engine + auth + DB)
pytest backend/ -q

# Self-tests of the frozen core (stdlib-only, no install needed)
pytest simulator/ gateway/ -q
```

## Pre-commit hooks (optional, recommended)

```bash
pip install -r requirements-dev.txt      # brings in pre-commit
pre-commit install
```

Hooks run on every commit:

1. `ruff-format` — auto-reformats staged Python.
2. `ruff-check`  — auto-fixes fixable lint issues.
3. `trailing-whitespace` / `end-of-file-fixer` / `mixed-line-ending`.
4. `check-yaml` — validates all YAML (CI, Dependabot, pre-commit itself).
5. `check-toml` — validates `pyproject.toml`.
6. `check-merge-conflict` — blocks merge-conflict markers.

Skip a hook locally (last resort): `git commit --no-verify`.

## Headless scripts

Scripts in `scripts/` import from `backend` directly and never start the web
server — they are the CI and one-shot path.

```bash
python scripts/generate_experiment.py --nodes 20 --area 400 --seed 1 --duration 60
python scripts/export_report.py --db experiments.db --out report.md
python scripts/run_all_benchmarks.py --report-json bench_report.json
```

## Commit & PR guidelines

- Keep commits focused; describe the *why*, not just the *what*.
- Add a `CHANGELOG.md` entry under `[Unreleased]` for user-visible changes
  (Added / Changed / Fixed sections).
- Do **not** commit generated databases (`*.db`), virtual environments
  (`venv/`), or benchmark figures unless explicitly regenerating the README
  showcase (figures live in `docs/benchmark/figures/`).
- Open a PR against `main`. CI runs:
  - Ruff lint + format gate (`quality` job).
  - Pytest on Python 3.11 · 3.12 · 3.13 with coverage fail-under=60%.
  - A Docker build + container HEALTHCHECK probe.
  - A dependency review (on PRs only).
- Sensitive issues: see `SECURITY.md` for the private disclosure path.

## Code of conduct

Be respectful, assume good intent, and keep discussions technical and
constructive.
