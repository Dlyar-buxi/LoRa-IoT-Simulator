"""
LoRa MAC retry / backoff test (Sprint 4.1)

参考 test_mac.py 风格，用 DummyNode 驱动状态机：
- 首次发送失败 -> RETRY, retry_count=1
- 退避 -> WAIT_BACKOFF
- 重传 -> TRANSMITTING
- 成功 -> IDLE（Packet.retry_count 作为遥测保留，此处只查 MAC 状态）
"""

from simulator.mac import (
    LoRaMAC,
    MacState,
)


class DummyNode:
    def create_packet(self):
        return {"data": "sensor"}


def test_retry():
    mac = LoRaMAC(DummyNode())

    print("===== Retry Test =====")
    print()

    # 首次发送
    mac.start_transmission()
    assert mac.state == MacState.TRANSMITTING

    # 模拟发送失败
    mac.handle_failure()
    print("First TX:")
    print("State:", mac.state.name)
    print("Retry count:", mac.retry_count)
    print()
    assert mac.state == MacState.RETRY
    assert mac.retry_count == 1

    # 进入退避
    mac.start_backoff()
    print("Backoff:")
    print("State:", mac.state.name)
    print()
    assert mac.state == MacState.WAIT_BACKOFF

    # 退避结束，重传
    mac.retry_transmission()
    print("Second TX:")
    print("State:", mac.state.name)
    print()
    assert mac.state == MacState.TRANSMITTING

    # 模拟重传成功
    mac.handle_success()
    print("Success:")
    print("State:", mac.state.name)
    print()
    assert mac.state == MacState.IDLE

    print("Retry Test PASS")


if __name__ == "__main__":
    test_retry()
