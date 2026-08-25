"""
LoRa Gateway

职责:

1. 接收LoRa数据包
2. 统计接收情况
3. 提供网络指标

"""


from simulator.packet import Packet



class Gateway:


    def __init__(

            self,

            gateway_id,

            x,

            y):


        # 与channel.py保持一致

        self.id = gateway_id


        self.x = x

        self.y = y



        # 保存成功接收的数据包

        self.received_packets = []



        # 统计

        self.success_count = 0

        self.failed_count = 0



        self.rssi_history = []

        self.snr_history = []



    def receive(

            self,

            packet: Packet):



        if packet.success:


            self.success_count += 1


            self.received_packets.append(

                packet

            )


            self.rssi_history.append(

                packet.rssi

            )


            self.snr_history.append(

                packet.snr

            )


            return True



        else:


            self.failed_count += 1


            return False



    def statistics(self):


        total = (

            self.success_count +

            self.failed_count

        )


        if total == 0:

            return {

                "gateway":

                self.id,

                "total":

                0

            }



        return {


            "gateway":

                self.id,


            "total":

                total,


            "received":

                self.success_count,


            "failed":

                self.failed_count,


            "success_rate":

                round(

                    self.success_count /

                    total *

                    100,

                    2

                ),


            "avg_rssi":

                round(

                    sum(self.rssi_history)

                    /

                    len(self.rssi_history),

                    2

                )

                if self.rssi_history

                else None,



            "avg_snr":

                round(

                    sum(self.snr_history)

                    /

                    len(self.snr_history),

                    2

                )

                if self.snr_history

                else None

        }
