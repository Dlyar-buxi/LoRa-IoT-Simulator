#!/usr/bin/env python3
"""Headless experiment generator for LoRa-IoT-Simulator.

Runs a full simulation with the backend engine + SQLite recorder WITHOUT
starting the FastAPI web server. Useful for CI benchmarks, batch runs, and
Docker (`docker exec ... python scripts/generate_experiment.py`).

This script imports only `backend.engine` and `backend.database`; it never
imports `backend.main`, so no uvicorn / WebSocket / MQTT server is launched.

Exit code is non-zero on failure so CI can detect problems.
"""

import argparse
import json
import logging
import os
import sys

# Make the project root importable when run as a bare script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engine import SimulationEngine  # noqa: E402
from backend.database import ExperimentRecorder  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("generate_experiment")


def gw_positions(count, area_size):
    """Grid placement of `count` gateways across the square area.

    Positions scale with `area_size` (unlike the frozen default 2000-area
    topology) so small benchmark areas stay inside the field. Supports 1-4.
    """
    q = area_size * 0.25
    h = area_size * 0.75
    layouts = {
        1: [(h, h)],
        2: [(q, q), (h, h)],
        3: [(q, q), (h, q), (q, h)],
        4: [(q, q), (h, q), (q, h), (h, h)],
    }
    pts = layouts.get(count, layouts[2])
    return [[f"GW{i + 1:03}", x, y] for i, (x, y) in enumerate(pts)]


def run(args):
    db_path = args.db or os.getenv("DB_PATH", "experiments.db")
    recorder = ExperimentRecorder(db_path=db_path, enabled=True)
    if not recorder.connect():
        log.error("Could not open database at %s", db_path)
        return 2

    gateways = gw_positions(args.gateway_count, args.area_size)

    engine = SimulationEngine(
        duration=args.duration,
        seed=args.seed,
        node_count=args.node_count,
        area_size=args.area_size,
        gateway_positions=gateways,
        adr_enabled=args.adr,
    )

    # Wire the recorder as the telemetry sink (same path the web server uses).
    engine.set_telemetry_sink(recorder.record_event)

    recorder.begin_experiment(
        {
            "seed": engine.seed,
            "node_count": engine.node_count,
            "duration": engine.duration,
            "area_size": engine.area_size,
            "adr_enabled": engine.adr_enabled,
            "gateway_cfg": engine.gateway_positions,
        }
    )

    engine.start()
    executed = 0
    while engine.state != "finished":
        executed += engine.step(50)

    recorder.finalize_experiment(
        engine.get_statistics(),
        engine.get_nodes(),
        engine.get_gateways(),
    )
    recorder.close()

    stats = engine.get_statistics()
    log.info(
        "Experiment done: nodes=%d area=%d seed=%d gw=%d adr=%s steps=%d pdr=%.3f",
        engine.node_count, engine.area_size, engine.seed,
        args.gateway_count, engine.adr_enabled, executed, stats["pdr"],
    )
    print(json.dumps({
        "executed": executed,
        "pdr": round(stats["pdr"], 4),
        "throughput": stats["throughput"],
        "retransmissions": stats["retransmissions"],
        "db": db_path,
    }, ensure_ascii=False))
    return 0


def main():
    p = argparse.ArgumentParser(description="Generate a LoRa-IoT simulation run (headless).")
    p.add_argument("--nodes", type=int, default=20, dest="node_count")
    p.add_argument("--area", type=float, default=2000.0, dest="area_size")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--duration", type=float, default=60.0)
    p.add_argument("--gateways", type=int, default=2, choices=[1, 2, 3, 4], dest="gateway_count")
    p.add_argument("--adr", action="store_true", default=False, dest="adr")
    p.add_argument("--db", type=str, default=None, help="SQLite path (default: $DB_PATH or experiments.db)")
    args = p.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
