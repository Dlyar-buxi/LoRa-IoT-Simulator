"""
LoRa wireless channel model

负责：

1. 距离计算
2. 路径损耗
3. RSSI计算
4. SNR计算
5. 接收成功判断

"""

from simulator.propagation import PropagationModel



class LoRaChannel:



    # LoRa典型接收灵敏度

    SF_SENSITIVITY = {

        7: -123,

        8: -126,

        9: -129,

        10: -132,

        11: -134,

        12: -137

    }



    def __init__(

            self,

            noise_floor=-120):


        self.propagation = PropagationModel()


        self.noise_floor = noise_floor



    def calculate_link(

            self,

            packet,

            gateway):



        """
        计算一次无线传输


        输入:

        packet:
            LoRa数据包


        gateway:
            网关


        返回:

        packet
        """



        # 1. distance


        distance = (

            self.propagation.calculate_distance(

                packet.x,

                packet.y,

                gateway.x,

                gateway.y

            )

        )



        # 2. path loss


        path_loss = (

            self.propagation.calculate_path_loss(

                distance

            )

        )



        # 3. RSSI


        rssi = (

            packet.tx_power -

            path_loss

        )



        # 4. SNR


        snr = (

            rssi -

            self.noise_floor

        )



        # 5. sensitivity


        sensitivity = (

            self.SF_SENSITIVITY.get(

                packet.sf,

                -123

            )

        )



        success = (

            rssi >= sensitivity

        )



        # 回填packet


        packet.distance = round(

            distance,

            2

        )


        packet.gateway_id = gateway.id


        packet.rssi = round(

            rssi,

            2

        )


        packet.snr = round(

            snr,

            2

        )


        packet.success = success



        return packet
