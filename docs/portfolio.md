# Project Portfolio — LoRa IoT Simulator

## Overview

LoRa IoT Simulator is a full-stack LoRa/LPWAN network simulation and monitoring
platform. It models the full path from embedded sensor nodes, through LoRa
PHY/MAC and gateways, all the way to a live web dashboard — and turns the
simulator from "a tool that runs" into "a platform you can study" via a
reproducible benchmark suite and one-command demo deployment.

The simulation core is **frozen** (unchanged since Sprint 4) and exposed to the
application layer through a strict read-only harness, so research results stay
stable while the surrounding tooling evolves.

## Technical Stack

**Backend**
- Python 3.13
- FastAPI (REST API + static dashboard hosting)
- SQLite (experiment persistence)

**IoT / Simulation**
- LoRaWAN physical-layer & MAC simulation (path loss, SNR, collisions, ADR, retransmission)
- MQTT (Eclipse Mosquitto) for broker integration

**Deployment**
- Docker Compose (backend + broker; opt-in `demo` profile for seeded data)

**Research tooling**
- Reproducible benchmark harness (`scripts/benchmark/`, `scripts/run_all_benchmarks.py`)
- matplotlib / numpy / pandas for analysis and figures

## Key Engineering Work

### Simulation Engine
- Implemented a discrete-event LoRa PHY/MAC simulator: propagation model
  (log-distance path loss + shadow fading), link-level SNR/success calculation,
  ALOHA-style MAC with collision detection and retransmission, and an ADR
  (adaptive data rate) controller.
- The engine is a self-contained, dependency-free core kept byte-for-byte stable
  so benchmark numbers remain comparable across releases.

### Benchmark System
- Built a three-experiment benchmark suite evaluating **scalability**
  (throughput vs. node count), **ADR performance** (PDR on/off across distance),
  and **link reliability** (PDR vs. distance).
- Drove the frozen engine through a read-only `backend.engine.SimulationEngine`
  harness — zero changes to core code — and emitted CSV data + PNG figures into
  `docs/benchmark/`.
- Unified the three experiments behind `scripts/run_all_benchmarks.py` for a
  single, ordered, logged run.

### Reproducible Deployment
- Added a cross-platform local demo runner (`scripts/run_demo.py`) that
  headlessly generates a sample experiment (`demo.db`) and a markdown report.
- Added an opt-in Docker Compose `demo` profile with a one-shot `demo-init`
  service that seeds a sample experiment into the shared volume on first launch.
- Documented the full reproduction path in `docs/reproducibility.md` so any
  clone can rebuild every result.

## Engineering Highlights

- **Designed a reproducible experiment pipeline** — fixed seeds, documented
  environment, and a single command (`scripts/run_all_benchmarks.py`) that
  regenerates all benchmark artifacts deterministically where the model allows.
- **Built an automated benchmark workflow** — consistent logging, CSV + figure
  outputs, and a methodology write-up, turning ad-hoc runs into citable results.
- **Implemented a containerized demo environment** — an opt-in Compose profile
  (`--profile demo`) that ships a working, data-backed dashboard with zero local
  setup, while keeping production deployments clean by default.
- **Maintained a frozen-core architecture** — all research and demo tooling is
  additive; the simulation engine, backend, and MQTT integration are never
  modified, which is what makes results reproducible release over release.
