"""
LoRa MAC State Machine

Sprint 3.1.1

实现:
- 状态管理
- 发送流程
- 成功确认
- 失败重试

"""


from enum import Enum, auto



class MacState(Enum):

    IDLE = auto()

    TRANSMITTING = auto()

    WAIT_ACK = auto()

    RETRY = auto()



class LoRaMAC:


    def __init__(self, node):

        self.node = node

        self.state = MacState.IDLE

        self.retry_count = 0

        self.max_retry = 3

        self.current_packet = None



    def generate_packet(self):

        """
        从节点生成数据包
        """

        self.current_packet = (

            self.node.create_packet()

        )


        return self.current_packet



    def start_transmission(self):

        """
        开始发送
        """


        if self.current_packet is None:

            self.generate_packet()



        self.state = MacState.TRANSMITTING



        return self.current_packet



    def wait_ack(self):

        """
        等待ACK
        """


        if self.state == MacState.TRANSMITTING:

            self.state = MacState.WAIT_ACK



    def handle_success(self):

        """
        发送成功
        """


        self.retry_count = 0


        self.state = MacState.IDLE



    def handle_failure(self):

        """
        发送失败

        进入重试
        """


        self.retry_count += 1



        if self.retry_count <= self.max_retry:

            self.state = MacState.RETRY


        else:

            self.retry_count = 0

            self.state = MacState.IDLE



    def retry_transmission(self):

        """
        重传
        """


        if self.state == MacState.RETRY:


            self.state = MacState.TRANSMITTING
