# file: power_supply_controller.py

import pyvisa
import time

class GPD4303SPowerSupply:
    """
    一个用于控制 GW Instek GPD-X303S 系列直流电源的类。
    通过 USB (VCP) 发送 SCPI-like 指令进行控制。
    """
    def __init__(self, port, baudrate=9600, timeout=2000):
        """
        :param port: 仪器的 VISA 资源名, e.g., 'ASRL3::INSTR' or 'COM3'
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout # ms
        self.is_connected = False
        self.instrument = None
        # 根据说明书，GPD-4303S 有4个通道
        self.num_channels = 4
        print(f"初始化设备: GPD4303SPowerSupply on {port}")

    def connect(self):
        """建立与设备的连接。"""
        print(f"[{self.__class__.__name__}] 正在连接电源...")
        try:
            rm = pyvisa.ResourceManager()
            self.instrument = rm.open_resource(self.port)
            self.instrument.timeout = self.timeout
            self.instrument.baud_rate = self.baudrate
            idn = self.instrument.query("*IDN?")
            print(f"[{self.__class__.__name__}] 连接成功. 设备信息: {idn.strip()}")
            self.is_connected = True
            return True
        except pyvisa.errors.VisaIOError as e:
            self.is_connected = False
            print(f"[{self.__class__.__name__}] 连接失败: {e}")
            return False

    def disconnect(self):
        """断开与设备的连接。"""
        if self.instrument and self.is_connected:
            print(f"[{self.__class__.__name__}] 正在关闭连接。")
            # 在关闭前将所有通道的输出关闭
            self.set_output(enable=False)
            self.instrument.close()
        self.is_connected = False
    
    def _send_command(self, command):
        """向仪器发送指令。"""
        if not self.is_connected: return
        try:
            self.instrument.write(command)
        except pyvisa.errors.VisaIOError as e:
            print(f"发送指令 '{command}' 失败: {e}")

    def _query(self, query):
        """向仪器发送查询并读取返回。"""
        if not self.is_connected: return None
        try:
            return self.instrument.query(query).strip()
        except pyvisa.errors.VisaIOError as e:
            print(f"查询 '{query}' 失败: {e}")
            return None

    def set_voltage(self, channel, voltage):
        """设置指定通道的电压。"""
        if not 1 <= channel <= self.num_channels: print(f"错误: 通道 {channel} 无效。"); return
        self._send_command(f"VSET{channel}:{voltage:.3f}")

    def set_current(self, channel, current):
        """设置指定通道的电流上限。"""
        if not 1 <= channel <= self.num_channels: print(f"错误: 通道 {channel} 无效。"); return
        self._send_command(f"ISET{channel}:{current:.3f}")

    def set_output(self, enable):
        """打开或关闭所有通道的输出。"""
        state = "1" if enable else "0"
        self._send_command(f"OUT{state}")

    def get_voltage(self, channel):
        """读取指定通道的实际输出电压。"""
        if not 1 <= channel <= self.num_channels: return 0.0
        response = self._query(f"VOUT{channel}?")
        try: return float(response) if response is not None else 0.0
        except ValueError: return 0.0

    def get_current(self, channel):
        """读取指定通道的实际输出电流。"""
        if not 1 <= channel <= self.num_channels: return 0.0
        response = self._query(f"IOUT{channel}?")
        try: return float(response) if response is not None else 0.0
        except ValueError: return 0.0
        
    def get_status(self):
        """获取所有通道的状态。"""
        status = {}
        if not self.is_connected:
            for i in range(1, self.num_channels + 1):
                status[f'ch{i}_voltage'] = 0.0
                status[f'ch{i}_current'] = 0.0
            status['output_on'] = False
            return status

        for i in range(1, self.num_channels + 1):
            status[f'ch{i}_voltage'] = self.get_voltage(i)
            status[f'ch{i}_current'] = self.get_current(i)
        
        status_word_str = self._query("STATUS?")
        if status_word_str:
            try:
                status_word = int(status_word_str)
                # 根据手册，第5位(bit 5)是总输出状态 (0=off, 1=on)
                # 使用位运算检查该位是否为1
                status['output_on'] = (status_word & (1 << 5)) != 0
            except (ValueError, IndexError):
                status['output_on'] = False
        else:
            status['output_on'] = False
            
        return status