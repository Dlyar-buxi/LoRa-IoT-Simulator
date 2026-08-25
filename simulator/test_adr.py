"""
LoRa ADR (Adaptive Data Rate) test (Sprint 4.2)

验证 adr.adapt_sf 的双阈值规则与边界钳制。
"""

from simulator import config
from simulator.adr import adapt_sf


def test_adr():
    # adapt_sf 依赖全局开关 config.ADR_ENABLED；
    # 显式置为启用态，避免被其他测试模块的运行期修改污染。
    config.ADR_ENABLED = True

    print("===== ADR Test =====")
    print()

    # 高 SNR：链路好，应降低 SF
    sf = adapt_sf(12, 30)
    print("High SNR:")
    print(f"SF12 -> SF{sf}")
    print()
    assert sf == 11

    # 中 SNR：维持不变
    sf = adapt_sf(9, 7)
    print("Medium SNR:")
    print(f"SF9 -> SF{sf}")
    print()
    assert sf == 9

    # 低 SNR：链路差，应提高 SF
    sf = adapt_sf(7, 2)
    print("Low SNR:")
    print(f"SF7 -> SF{sf}")
    print()
    assert sf == 8

    # 边界：已是 SF7，即便高 SNR 也不能再降
    sf = adapt_sf(7, 30)
    print("Boundary:")
    print(f"SF7 stays SF{sf}")
    print()
    assert sf == 7

    # 边界：已是 SF12，即便低 SNR 也不能再升
    sf = adapt_sf(12, 2)
    print(f"SF12 stays SF{sf}")
    print()
    assert sf == 12

    print("ADR Test PASS")


if __name__ == "__main__":
    test_adr()
