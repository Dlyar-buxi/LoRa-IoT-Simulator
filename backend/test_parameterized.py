"""参数化实验平台 hermetic 验收（Sprint 5.3）。

不依赖真实 experiments.db / MQTT：进程内禁用 DB（避免落盘），仅测参数注入与 API。
覆盖：默认单例行为不变 / configure 重建 / 部分参数保留 / ADR 运行期绑定不串味 /
配置后 step+export 正常 / GET+POST /api/simulation/config（含非法参数 4xx）。

运行：python -m backend.test_parameterized
"""

import os

# 禁用 SQLite Recorder，避免本测试在项目中落盘 experiments.db
os.environ.setdefault("DB_ENABLED", "false")

from backend.engine import SimulationEngine
from backend.main import app
from simulator import config


def test_default_singleton_behavior():
    """无参构造必须保持 200/2/2000/seed42/60s/ADR，且 step/export 正常。"""
    e = SimulationEngine()
    assert e.node_count == 200
    assert len(e.gateway_positions) == 2
    assert e.area_size == 2000
    assert e.seed == 42
    assert e.duration == 60
    assert e.adr_enabled is True
    assert config.ADR_ENABLED is True

    e.step(10)
    assert len(e.history) == 10
    exp = e.get_export()
    assert len(exp["nodes"]) == 200
    assert len(exp["gateways"]) == 2


def test_configure_rebuild():
    """configure 改全部参数后重建 topology，并运行期绑定 ADR。"""
    e = SimulationEngine()
    gw = [["GW001", 100, 100], ["GW002", 4000, 4000], ["GW003", 2500, 2500]]
    e.configure(
        node_count=50,
        area_size=5000,
        gateways=gw,
        seed=99,
        duration=120,
        adr_enabled=False,
    )
    assert e.node_count == 50
    assert e.area_size == 5000
    assert len(e.gateway_positions) == 3
    assert e.seed == 99
    assert e.duration == 120
    assert e.adr_enabled is False
    assert e.state == "ready"
    assert config.ADR_ENABLED is False  # 运行期绑定生效

    e.step(20)
    exp = e.get_export()
    assert len(exp["nodes"]) == 50
    assert len(e.history) == 20


def test_configure_partial_keeps_others():
    """只传部分参数时，其余沿用当前值。"""
    e = SimulationEngine()
    e.configure(node_count=10)
    assert e.node_count == 10
    assert e.area_size == 2000
    assert len(e.gateway_positions) == 2
    assert e.seed == 42
    assert e.duration == 60
    assert e.adr_enabled is True


def test_adr_toggle_no_cross_contamination():
    """每个 engine 的 ADR 意图各自绑定全局 config，不串味。"""
    e1 = SimulationEngine()
    e1.configure(adr_enabled=False)
    assert e1.adr_enabled is False and config.ADR_ENABLED is False

    e2 = SimulationEngine()
    e2.configure(adr_enabled=True)
    assert e2.adr_enabled is True and config.ADR_ENABLED is True


def test_configure_then_step_and_export():
    """参数化后 step 推进、status/export 反映新拓扑。"""
    e = SimulationEngine()
    e.configure(node_count=30, seed=7, duration=30)
    executed = e.step(30)
    assert executed == 30
    st = e.get_status()
    assert st["received"] >= 0
    exp = e.get_export()
    assert len(exp["nodes"]) == 30


def test_api_config_endpoint():
    """GET/POST /api/simulation/config：默认读取、合法设置、非法拒绝 4xx。"""
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        # GET 默认
        r = client.get("/api/simulation/config")
        assert r.status_code == 200
        body = r.json()
        assert body["node_count"] == 200 and len(body["gateways"]) == 2

        # POST 合法
        r = client.post(
            "/api/simulation/config",
            json={
                "node_count": 50,
                "area_size": 3000,
                "gateways": [
                    ["GW001", 500, 500],
                    ["GW002", 1500, 1500],
                    ["GW003", 2500, 2500],
                ],
                "seed": 123,
                "duration": 120,
                "adr_enabled": False,
            },
        )
        assert r.status_code == 200
        b = r.json()
        assert b["node_count"] == 50
        assert b["area_size"] == 3000
        assert len(b["gateways"]) == 3
        assert b["adr_enabled"] is False

        # GET 反映新配置
        r = client.get("/api/simulation/config")
        assert r.json()["node_count"] == 50

        # 非法参数 -> 400
        assert (
            client.post("/api/simulation/config", json={"node_count": 0}).status_code
            == 400
        )
        assert (
            client.post("/api/simulation/config", json={"gateways": []}).status_code
            == 400
        )
        assert (
            client.post(
                "/api/simulation/config",
                json={"gateways": [["GW001", 1, 1], ["GW001", 2, 2]]},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/simulation/config", json={"gateways": [["GW001", 9999, 9999]]}
            ).status_code
            == 400
        )


if __name__ == "__main__":
    tests = [
        test_default_singleton_behavior,
        test_configure_rebuild,
        test_configure_partial_keeps_others,
        test_adr_toggle_no_cross_contamination,
        test_configure_then_step_and_export,
        test_api_config_endpoint,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS backend.test_parameterized :: {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL backend.test_parameterized :: {t.__name__} -- {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR backend.test_parameterized :: {t.__name__} -- {e}")
    if failed:
        print(f"REGRESSION FAIL={failed}")
        import sys

        sys.exit(1)
    print("REGRESSION PASS (parameterized)")
