from simulator.packet import Packet

from simulator.channel import LoRaChannel



class TestGateway:


    def __init__(self):

        self.id = "GW001"

        self.x = 1000

        self.y = 1000




packet = Packet(

    node_id="Node001",

    payload={

        "temperature":25.5

    },

    sf=7,

    tx_power=14

)



# 模拟节点位置

packet.x = 1500

packet.y = 1200



gateway = TestGateway()



channel = LoRaChannel()



result = channel.calculate_link(

    packet,

    gateway

)



print(

    "===== LoRa Channel Test ====="

)


print(

    f"Node: {result.node_id}"

)


print(

    f"Distance: {result.distance} m"

)


print(

    f"RSSI: {result.rssi} dBm"

)


print(

    f"SNR: {result.snr} dB"

)


print(

    f"SF: {result.sf}"

)


print(

    f"SUCCESS: {result.success}"

)
