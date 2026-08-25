# Reproducibility Checklist

How to rebuild every result in this repository from a clean checkout.

## Environment

- **Python**: CPython 3.13 (developed and tested on 3.13.x; requires 3.12+)
- **Dependencies**: `requirements.txt` — install with
  `python -m pip install -r requirements.txt`
- **Docker** (optional, for the containerized demo): 20.10+ with the Compose v2
  plugin (`docker compose` subcommand)

## Benchmark

Command:

```bash
python scripts/run_all_benchmarks.py
```

Expected artifacts (written to `docs/benchmark/`):

- `scalability.csv` — throughput vs. node count
- `adr_compare.csv` — ADR on/off PDR by link distance
- `distance.csv` — PDR vs. link distance
- `figures/scalability.png`
- `figures/adr_compare.png`
- `figures/distance_pdr.png`

> Benchmarks drive the **frozen** simulation core through the read-only
> `backend.engine.SimulationEngine` harness, so no core code is involved.
> Some experiments use stochastic packet loss; re-running may yield slightly
> different numeric values, but the qualitative trends (PDR degradation with
> distance, linear throughput scaling) are stable across runs.

## Demo

Docker (recommended, zero local setup):

```bash
docker compose --profile demo up --build
```

Local Python:

```bash
python -m pip install -r requirements.txt
python scripts/run_demo.py
```

## Verification

Expected for the demo experiment (`scripts/run_demo.py` / `demo-init`):

- nodes: **20**
- gateways: **2**
- seed: **1**
- area: **400**
- PDR: **1.0**

## Release

- Version: **v1.1.0**
- Tag: `v1.1.0` (`git tag -a v1.1.0 -m "Release v1.1.0"`)
