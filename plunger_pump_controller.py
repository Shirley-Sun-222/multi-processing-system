# file: plunger_pump_controller.py (已添加对多余参数的兼容处理)

import time
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from base_pump import BasePump

class OushishengPlungerPump(BasePump):
    """
    欧世盛柱塞泵控制器。
    此类继承自 BasePump，并实现了其定义的标准接口。
    """
    def __init__(self, port, unit_address=55, baudrate=9600, timeout=1):
        super().__init__(port, unit_address, baudrate)
        self.client = ModbusSerialClient(
            port=self.port,
            baudrate=self.baudrate,
            timeout=timeout,
            parity='N',
            stopbits=1,
            bytesize=8
        )

    # --- 实现 BasePump 的标准接口 ---
    def connect(self):
        print(f"[{self.__class__.__name__}] 正在连接柱塞泵...")
        if self.client.connect():
            self.is_connected = True
            print(f"[{self.__class__.__name__}] 连接成功。")
            return True
        else:
            self.is_connected = False
            print(f"[{self.__class__.__name__}] 连接失败。")
            return False

    def disconnect(self):
        print(f"[{self.__class__.__name__}] 正在关闭连接。")
        self.client.close()
        self.is_connected = False
    
    # ★★★ 修改点 1：修改 start 方法以接受并忽略多余参数 ★★★
    def start(self, flow_rate=1.0, **kwargs):
        """
        启动柱塞泵。
        使用 **kwargs 来接收并忽略所有非预期的参数（如 direction）。
        :param flow_rate: 目标流量 (ml/min)。
        """
        print(f"[{self.__class__.__name__}] 正在启动泵，流量: {flow_rate} ml/min...")
        if not self.is_connected:
            print("错误: 设备未连接。")
            return False
        
        # 柱塞泵需要先设流量，再启动
        self.set_parameters(flow_rate=flow_rate) # 复用 set_parameters
        time.sleep(0.05)
        return self._write_register(0x05, 1) # 启动泵的地址是 5，值为 1

    def stop(self):
        print(f"[{self.__class__.__name__}] 正在停止泵...")
        return self._write_register(0x07, 1) # 停止泵的地址是 7，值为 1

    # ★★★ 修改点 2：实现 set_parameters 方法 ★★★
    def set_parameters(self, flow_rate=None, **kwargs):
        """
        在线设置泵的运行参数。
        使用 **kwargs 来接收并忽略所有非预期的参数（如 direction）。
        """
        if not self.is_connected:
            print("错误: 设备未连接。")
            return False

        if flow_rate is not None:
            print(f"[{self.__class__.__name__}] 动态设置流量为: {flow_rate} ml/min...")
            return self._set_flow_rate(flow_rate)
        return False

    def get_status(self):
        is_running = self._is_running()
        pressure = self._read_pressure()
        flow_rate = self._read_set_flow_rate()
        return {
            "is_running": is_running,
            "pressure_mpa": pressure if pressure is not None else 0.0,
            "flow_rate_ml_min": flow_rate if flow_rate is not None else 0.0
        }

    # --- 内部辅助函数 ---
    def _set_flow_rate(self, flow_ml_min):
        value = int(float(flow_ml_min) * 1000)
        return self._write_register(1, value)

    def _read_pressure(self):
        value = self._read_register(0x04)
        return value / 10.0 if value is not None else None

    def _is_running(self):
        value = self._read_register(0x0E)
        return value == 1 if value is not None else False
    
    def _read_set_flow_rate(self):
        value = self._read_register(0x0B)
        return value / 1000.0 if value is not None else None

    def _write_register(self, address, value):
        try:
            r = self.client.write_register(address, value, device_id=self.unit_address)
            return not r.isError()
        except ModbusException as e:
            print(f"[{self.__class__.__name__}] 写寄存器错误: {e}")
            return False

    def _read_register(self, address):
        try:
            r = self.client.read_holding_registers(address, device_id=self.unit_address) # 这个地方一直有bug，如出错，尝试增在address后增加count参数
            return None if r.isError() else r.registers[0]
        except ModbusException as e:
            print(f"[{self.__class__.__name__}] 读寄存器错误: {e}")
            return None