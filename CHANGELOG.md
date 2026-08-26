# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Release codename: **v1.2.0-hardening (HR-ready)**. Target: a polished,
engineering-signal-dense open-source showcase that stands up to a senior
engineer's 8-minute screen and a hiring manager's 30-second scan.

### Added

- **Python packaging & lint** — Added `pyproject.toml` with a unified Ruff
  (lint + formatter) configuration and pytest default options; the project now
  runs `ruff check .` and `ruff format --check .` as a CI quality gate. (T1)
- **Developer toolchain file** — Added `requirements-dev.txt` shipping
  `pytest>=8`, `pytest-cov>=5`, `ruff>=0.6`, and `pre-commit>=3.7`. (T1)
- **Git pre-commit hooks** — Added `.pre-commit-config.yaml` with Ruff
  format + Ruff auto-fix, trailing-whitespace / EOF-fixer / mixed-line-ending,
  YAML + TOML validators, and merge-conflict marker detection. (T2)
- **Expanded CI matrix** — Replaced the single-Python `test.yml` with a
  4-job workflow: (1) `quality` Ruff gate; (2) `test` matrix on Python
  3.11 / 3.12 / 3.13 with `--cov-fail-under=60` + coverage artifact upload;
  (3) `docker` build + container HEALTHCHECK probe; (4) `dependency-review`
  on pull requests. (T3)
- **CodeQL SAST pipeline** — Added `.github/workflows/codeql.yml` running
  the security-and-quality query suite on every push/PR to `main` plus a
  weekly Monday schedule. (T4)
- **Automated dependency updates** — Added `.github/dependabot.yml` with
  pip weekly, docker monthly, and github-actions monthly package ecosystems
  and labelled pull-request prefixes. (T5)
- **Security policy** — Added `SECURITY.md` listing supported versions
  (main / v1.2.x fully supported; v1.1.x best-effort; <v1.0 unsupported),
  private GitHub Security Advisories as the preferred disclosure path,
  5/10/30 day SLA tiers, a 6-step security update process, and a known
  attack-surface table (REST, WS, MQTT, SQLite, static assets, Docker). (T5)
- **Docker multi-stage + non-root runtime user** — Rewrote `Dockerfile`
  into a builder stage (pip prefix install) + a runtime stage that copies
  only site-packages, creates a fixed-uid `simulator` (65532:65532)
  nologin system user, declares `/app/data` as a `VOLUME`, and probes
  `/health` in a stdlib-only `HEALTHCHECK`. `.dockerignore` expanded
  to exclude editor/CI/venv artefacts while keeping docs/examples/screenshots
  reachable from the image. (T6)
- **Lint + format sections in CONTRIBUTING.md** — Documented the Ruff
  rule set (E/F/I/UP/B/SIM), per-file ignores for the frozen core, and
  exact commands for local use matching the CI gate. (T7)
- **Two new architecture sections** — Added §3 *Thread Safety & Concurrency
  Model* (SimulationEngine `threading.RLock`, WsManager `asyncio.Lock`,
  Recorder `threading.Lock` + hook contracts) and §4 *Authentication & API
  Key Enforcement* (REST header vs WS query param, surface coverage table)
  to `docs/architecture.md`. (T8)
- **Restyle README landing** — Added a Ruff / Coverage / CodeQL / Dependabot /
  Docker badge row above the fold; replaced the ASCII architecture diagram
  with a Mermaid flowchart; added a benchmark baseline table (3 experiments x
  runtime + RSS + figure outputs); rewrote the Resume Highlights section with
  seven quantified bullets; corrected `14/14` to `23/23` test figures. (T10)
- **Dashboard resilience layer** — Added exponential-backoff WebSocket
  reconnect (1 s to 30 s cap), a global toast component for user-facing
  success/error feedback, a disabled + spinner loading state on the Apply
  button that always recovers within 10 s, and an API Key UI bar that
  stores the key in `localStorage`, redacts the middle digits on display,
  and injects `X-API-Key` headers + `?token=` query into every REST/WS
  call. (T11 / T12 / T13)
- **Benchmark runner JSON report** — Extended
  `scripts/run_all_benchmarks.py` with a `--report-json <file>` CLI that
  writes a structured machine-readable report including per-stage
  `duration_seconds` and `peak_rss_mb` timing samples. (T14)

### Changed

- **Narrowed the frozen core contract** — `CONTRIBUTING.md` previously
  listed `backend/`, `frontend/` and `requirements.txt` as frozen,
  which contradicted 6 sprints of Adapter-layer work. The contract now
  correctly freezes only `simulator/` and `gateway/`. (T7)
- **Replaced monkey-patch lifecycle wiring** — All references to
  monkeypatching `engine.reset` / `engine.configure` were removed
  from `docs/architecture.md` and replaced with the explicit lifecycle
  hook API (`register_pre_reset_hook`, `register_reset_hook`,
  `register_pre_configure_hook`, `register_configure_hook`). (T8)
- **Frontend auto-run switched to chained setTimeout** — Auto-run no
  longer stacks requests under high latency; each `tick() + refresh()`
  finishes before the next loop is scheduled. (from v1.2 hardening P1-8)
- **Bumped project metadata version** to `1.2.0-hardening` in
  `pyproject.toml`.

### Fixed

- **Race conditions on SimulationEngine** — All state-mutating and
  state-reading operations (step, reset, configure, get_*, export) are now
  serialised by a single `threading.RLock`, preventing heapq corruption and
  `deque` consistency issues under concurrent FastAPI thread-pool calls.
  (from v1.2 hardening P0-1)
- **Unbounded engine history** — `SimulationEngine.history` is now a
  `collections.deque(maxlen=10000)` (configurable via
  `ENGINE_HISTORY_MAX_LEN`), capping memory on long experiments.
  (from v1.2 hardening P0-1)
- **SQLite write performance (DELETE journal to WAL + batching)** — The
  Recorder now opens its connection with `journal_mode=WAL` and batches
  event inserts: flushing after 100 rows or 1 s, whichever comes first.
  Close / experiment finalize force-flush pending rows so tail data never
  gets dropped. (from v1.2 hardening P0-3)
- **API Key authentication implemented & correctly routed** — REST
  endpoints use `X-API-Key` via Starlette `BaseHTTPMiddleware`; WebSocket
  `/ws` uses `?token=` query checked inline before accept. Test suite
  23/23 green including the auth-gated endpoints. (from v1.2 hardening)
- **GET /api/experiments/{id} response size guard** — Event detail now
  defaults to `events_limit=1000`, keeping replay payloads bounded.
  (from v1.2 hardening)
- **Ruff lint compliance on Adapter Python sources** — Import sort,
  `Optional[X]` to `X | None`, `try/except/pass` to `contextlib.suppress`,
  ambiguous variable name `l`, and nested-if simplifications — all
  auto-fixed or manually patched across `backend/auth.py`,
  `backend/database.py`, `backend/engine.py`, `backend/mqtt_client.py`,
  `backend/routes.py`. (T1 autofix pass)

## [1.1.0] - 2026-08-27

Benchmark release (Sprint 6.2 baseline).

### Added
- Sprint 6.1 reproducible research suite (Scalability, ADR, Distance benchmarks).
- `scripts/run_all_benchmarks.py` unified runner + figures under `docs/benchmark/`.
- Benchmark narrative in README with three PNG figures and finding highlights.
- `v6.4-channel-model` experiment tags for frozen snapshot references.

## [1.0.0] - 2026-08-26

First public release candidate (RC v5.5 baseline, commit `47fa815`).

### Core platform
- STM32-style embedded node model with LoRa PHY link budget (`simulator/`).
- LoRa gateway packet collection with RSSI aggregation (`gateway/`).
- FastAPI backend streaming telemetry over MQTT and persisting runs to SQLite.
- Web dashboard with live topology, packet-delivery charts, and gateway stats.

### Sprints included (development history)
- **Sprint 4** — Reliability and adaptive network (ADR-aware link model).
- **Sprint 4.4** — Visualization platform.
- **Sprint 5.1** — MQTT realtime telemetry.
- **Sprint 5.2** — SQLite experiment persistence.
- **Sprint 5.3** — Parameterized experiment platform (`engine.configure()`).
- **Sprint 5.4** — Project packaging and documentation.
- **Sprint 5.5** — Dashboard experiment configuration panel.

[Unreleased]: https://github.com/Dlyar-buxi/LoRa-IoT-Simulator/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Dlyar-buxi/LoRa-IoT-Simulator/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Dlyar-buxi/LoRa-IoT-Simulator/releases/tag/v1.0.0
