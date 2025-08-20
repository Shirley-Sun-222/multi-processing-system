'''
file: base_pump.py

Author: Xueli Sun
Date: 2025.8.19
Version:1.0

Base Pump Class. Universal Interface for Pump Control.

'''

class BasePump:
    """
    一个通用的泵设备基础类 (接口)。
    所有具体的泵控制器都应继承此类，并实现其所有方法。
    """

    def __init__(self, port, unit_address, baudrate):
        """
        初始化泵的基础属性。

        :param port: 串口端口。
        :param unit_address: 设备的 Modbus 从机地址。
        :param baudrate: 通讯波特率。
        """
        self.port = port
        self.unit_address = unit_address
        self.baudrate = baudrate
        self.is_connected = False
        print(f"初始化设备: {self.__class__.__name__} on {port} (地址: {unit_address})")

    def connect(self):
        """建立与设备的连接。"""
        raise NotImplementedError("子类必须实现 connect 方法")

    def disconnect(self):
        """断开与设备的连接。"""
        raise NotImplementedError("子类必须实现 disconnect 方法")

    def set_parameters(self, **kwargs):
        """
        在线设置泵的运行参数。
        :param kwargs: 参数字典，例如 {'speed': 150.0} 或 {'flow_rate': 7.5}
        """
        raise NotImplementedError("子类必须实现 set_parameters 方法")

    def stop(self):
        """停止泵的运行。"""
        raise NotImplementedError("子类必须实现 stop 方法")

    def get_status(self):
        """
        获取泵的当前状态。

        :return: 一个包含状态信息的字典，例如 {'is_running': True, 'speed': 99.8}
        """
        raise NotImplementedError("子类必须实现 get_status 方法")
    


