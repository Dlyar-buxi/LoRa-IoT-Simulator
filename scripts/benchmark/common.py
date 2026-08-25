"""Sprint 6.1 common benchmark runner (Step 2).

Read-only usage of the frozen simulator stack: imports
backend.engine.SimulationEngine and adds a tiny `finished()` helper via a
subclass so the benchmark orchestration code stays minimal. The frozen
backend/ source is NOT modified.
"""
import os
import statistics
import sys

# Make the project root importable when this file is executed as a script
# inside scripts/benchmark/ (so `from backend.engine import ...` resolves).
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.engine import SimulationEngine  # noqa: E402


class BenchmarkEngine(SimulationEngine):
    """Thin outer-layer extension: adds finished() used by run_experiment.

    Does not override any frozen behaviour — only exposes the finished state
    that the benchmark loop checks.
    """

    def finished(self):
        return self.state == "finished"


def run_experiment(
        node_count=50,
        duration=100,
        adr_enabled=True,
        seed=42
):
    """
    Common benchmark runner.
    """

    engine = BenchmarkEngine()

    engine.configure(
        node_count=node_count,
        duration=duration,
        seed=seed,
        adr_enabled=adr_enabled
    )

    engine.start()

    while not engine.finished():
        engine.step()

    stats = engine.get_statistics()
    packets = engine.get_packets()

    rssis = []
    sfs = []

    success = 0
    failed = 0

    for p in packets:
        if "rssi" in p:
            rssis.append(p["rssi"])

        if "sf" in p:
            sfs.append(p["sf"])

        if p.get("success"):
            success += 1
        else:
            failed += 1

    return {
        "nodes": node_count,
        "pdr": stats.get("pdr", 0),
        "throughput": stats.get("throughput", 0),
        "avg_rssi":
            statistics.mean(rssis)
            if rssis else None,
        "avg_sf":
            statistics.mean(sfs)
            if sfs else None,
        "collision_rate":
            failed / (success + failed)
            if success + failed else 0
    }
