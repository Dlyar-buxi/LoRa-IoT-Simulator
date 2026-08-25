# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open-source release hardening: `LICENSE` (MIT), `CONTRIBUTING.md`,
  `CHANGELOG.md`.
- `scripts/generate_experiment.py` — headless experiment generation via the
  backend engine (no web server required).
- `scripts/export_report.py` — export an experiment run to Markdown.
- `scripts/run_demo.sh` — one-command local demo entrypoint.
- `Dockerfile` with a healthcheck; `docker-compose.yml` now builds the image,
  mounts a named `experiments-db` volume, and health-checks the API.
- `.github/workflows/test.yml` CI: runs `pytest backend/` plus simulator and
  gateway smoke scripts.
- GitHub issue and pull-request templates.
- Dashboard Experiment Configuration Panel: configure `node_count`, `area_size`,
  `seed`, `duration`, `adr_enabled`, and `gateway_count` (1–4) from the UI,
  with auto gateway placement and live topology coloring.

### Changed
- Renamed the "Collision Rate" metric to **Packet Loss Rate** = `1 - PDR`
  to avoid implying a collision-specific counter that the frozen PHY model does
  not expose.

### Removed
- `analysis/` and `network_server/` placeholder directories (never wired in).

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

[Unreleased]: https://github.com/Dlyar-buxi/LoRa-IoT-Simulator/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Dlyar-buxi/LoRa-IoT-Simulator/releases/tag/v1.0.0
