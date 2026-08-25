"""
LoRa MAC state machine test
"""

from simulator.mac import (
    LoRaMAC,
    MacState,
)


class DummyNode:
    def create_packet(self):
        return {"data": "sensor"}


def test_mac_state_machine():
    mac = LoRaMAC(DummyNode())

    print("===== LoRa MAC State Test =====")
    print("Initial:", mac.state.name)

    assert mac.state == MacState.IDLE

    mac.start_transmission()
    print("Start TX:", mac.state.name)
    assert mac.state == MacState.TRANSMITTING

    mac.wait_ack()
    assert mac.state == MacState.WAIT_ACK

    mac.handle_success()
    print("ACK Success:", mac.state.name)
    assert mac.state == MacState.IDLE

    mac.handle_failure()
    print("Retry:", mac.state.name)
    assert mac.state == MacState.RETRY

    mac.retry_transmission()
    print("Retry TX:", mac.state.name)
    assert mac.state == MacState.TRANSMITTING

    print()
    print("MAC state machine PASS")


if __name__ == "__main__":
    test_mac_state_machine()
