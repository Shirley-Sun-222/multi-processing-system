# file: power_supply_controller.py (已修正为GPD-2303S的2通道版本)

import pyvisa
import time

class GPD4303SPowerSupply:
    """
    一个用于控制 GW Instek GPD-X303S 系列直流电源的类。
    已适配 GPD-2303S (2通道) 型号。
    """
    def __init__(self, port, baudrate=9600, timeout=2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout * 1000 # pyvisa 的 timeout 单位是毫秒
        self.is_connected = False
        self.instrument = None
        # ★★★ 核心修正 1：将通道数修正为 2 ★★★
        self.num_channels = 2
        print(f"初始化设备: GPD4303SPowerSupply on {port}")

    def connect(self):
        print(f"[{self.__class__.__name__}] 正在连接电源...")
        try:
            rm = pyvisa.ResourceManager()
            self.instrument = rm.open_resource(self.port)
            
            self.instrument.read_termination = '\n'
            self.instrument.write_termination = '\n'
            
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
        if self.instrument and self.is_connected:
            print(f"[{self.__class__.__name__}] 正在关闭连接。")
            self.set_output(enable=False)
            self.instrument.close()
        self.is_connected = False
    
    def _send_command(self, command):
        if not self.is_connected: return
        try:
            self.instrument.write(command)
            time.sleep(0.05)
        except pyvisa.errors.VisaIOError as e:
            print(f"发送指令 '{command}' 失败: {e}")

    def _query(self, query):
        if not self.is_connected: return None
        try:
            response = self.instrument.query(query).strip()
            time.sleep(0.05)
            return response
        except pyvisa.errors.VisaIOError as e:
            print(f"查询 '{query}' 失败: {e}")
            return None

    def set_voltage(self, channel, voltage):
        # ★★★ 核心修正 2：确保设置的通道号不超出范围 ★★★
        if not 1 <= channel <= self.num_channels:
            print(f"错误: 通道 {channel} 无效。有效通道为 1-{self.num_channels}。")
            return
        self._send_command(f"VSET{channel}:{voltage:.3f}")

    def set_current(self, channel, current):
        # ★★★ 核心修正 2：确保设置的通道号不超出范围 ★★★
        if not 1 <= channel <= self.num_channels:
            print(f"错误: 通道 {channel} 无效。有效通道为 1-{self.num_channels}。")
            return
        self._send_command(f"ISET{channel}:{current:.3f}")

    def set_output(self, enable):
        state = "1" if enable else "0"
        self._send_command(f"OUT{state}")

    def get_voltage(self, channel):
        if not 1 <= channel <= self.num_channels: return 0.0
        response = self._query(f"VOUT{channel}?")
        try:
            return float(response.replace('V', '')) if response is not None else 0.0
        except (ValueError, AttributeError):
            return 0.0

    def get_current(self, channel):
        if not 1 <= channel <= self.num_channels: return 0.0
        response = self._query(f"IOUT{channel}?")
        try:
            return float(response.replace('A', '')) if response is not None else 0.0
        except (ValueError, AttributeError):
            return 0.0
        
    def get_status(self):
        status = {}
        if not self.is_connected:
            status['output_on'] = False
            for i in range(1, self.num_channels + 1):
                status[f'ch{i}_voltage'] = 0.0
                status[f'ch{i}_current'] = 0.0
            return status

        # --- 核心修正：使用查询电压的方式来判断总输出状态 ---
        ch1_voltage = self.get_voltage(1)
        # 如果通道1的电压大于一个小的阈值，就认为总输出是打开的
        status['output_on'] = ch1_voltage >= 0.001

        # 继续获取所有通道的详细状态
        status['ch1_voltage'] = ch1_voltage
        status['ch1_current'] = self.get_current(1)
        
        for i in range(2, self.num_channels + 1):
            status[f'ch{i}_voltage'] = self.get_voltage(i)
            status[f'ch{i}_current'] = self.get_current(i)

        # 原始的 STATUS? 查询逻辑不再用于判断 on/off，但可以保留用于调试
        status_word_str = self._query("STATUS?")
        # print(f"[电源] STATUS? 返回 (仅供调试): {status_word_str}")
        # print(f"[电源] 解析后 output_on: {status['output_on']}")
        return status
    