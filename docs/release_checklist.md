# Release Checklist — v1.1.0

Final verification list for the LoRa IoT Simulator v1.1.0 release.
`[x]` = verified in this release; `[ ]` = to be confirmed by the maintainer
(GitHub UI / local environment).

## Code

- [x] Main branch clean (`6a2c14f`, synced with `origin/main`)
- [x] Tag created (`v1.1.0`)
- [ ] Release published on GitHub (Draft a new release → tag `v1.1.0`)

## Demo

- [ ] Docker demo works (`docker compose --profile demo up --build`)
- [ ] Local demo works (`python scripts/run_demo.py` → `demo.db` + `demo_report.md`)
- [ ] Dashboard accessible (`http://localhost:8000`)

## Benchmark

- [x] Benchmark scripts run (`python scripts/run_all_benchmarks.py`)
- [x] CSV artifacts generated (`docs/benchmark/*.csv`)
- [x] Figures generated (`docs/benchmark/figures/*.png`)

## Documentation

- [x] README updated (Research Benchmark + Quick Demo sections)
- [x] Quick Demo verified (Docker + Local paths documented)
- [x] Reproducibility guide added (`docs/reproducibility.md`)
- [x] Portfolio page added (`docs/portfolio.md`)
- [x] Release notes added (`docs/releases/v1.1.0.md`)

## Frozen core (must stay unchanged)

- [x] `simulator/` engine untouched
- [x] `gateway/` services untouched
- [x] `backend/` engine untouched
- [x] `Dockerfile` / `docker-compose.yml` core logic untouched
