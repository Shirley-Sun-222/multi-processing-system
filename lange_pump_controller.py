# file: lange_pump_controller.py

'''
Lange L100-1S-2 Peristaltic Pump Controller.
Inherits from BasePump and implements the required interface using Modbus RTU protocol.
Protocol details are based on the provided user manual (蠕动泵2.pdf).
'''

import time
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from base_pump import BasePump

class LangePeristalticPump(BasePump):
    """
    保定兰格 L100-1S-2 蠕动泵控制器。
    此类继承自 BasePump，并实现了其定义的标准接口。
    """
    # 根据手册附录2，定义Modbus寄存器地址
    ADDR_SET_SPEED = 0x01       # 设置转速 (0.01 RPM/unit)
    ADDR_STATUS_WORD = 0x04     # 状态字 (启停/方向)

    def __init__(self, port, unit_address=1, baudrate=9600, timeout=1):
        super().__init__(port, unit_address, baudrate)
        self.client = ModbusSerialClient(
            port=self.port,
            baudrate=self.baudrate,
            timeout=timeout,
            parity='N',
            stopbits=1,
            bytesize=8
        )
        self._last_direction_bit = 0 # 用于在停止时保持方向状态

    def connect(self):
        print(f"[{self.__class__.__name__}] 正在连接设备...")
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

    def start(self, speed=100.0, direction='forward'):
        print(f"[{self.__class__.__name__}] 正在启动泵，转速: {speed} RPM, 方向: {direction}...")
        if not self.is_connected:
            print("错误: 设备未连接。")
            return False
        
        # 1. 设置转速
        self.set_parameters(speed=speed)
        time.sleep(0.05)

        # 2. 设置方向并启动
        # 根据手册，BIT4: 0=正转(forward), 1=反转(reverse)
        self._last_direction_bit = 0x10 if direction.lower() == 'reverse' else 0x00
        # 根据手册，BIT0: 0=停止, 1=运行
        run_bit = 0x01
        
        status_word = self._last_direction_bit | run_bit
        return self._write_register(self.ADDR_STATUS_WORD, status_word)

    def stop(self):
        print(f"[{self.__class__.__name__}] 正在停止泵...")
        # 保持方向位 (BIT4)，只将运行位 (BIT0) 设置为0
        status_word = self._last_direction_bit | 0x00
        return self._write_register(self.ADDR_STATUS_WORD, status_word)

    def set_parameters(self, speed=None, **kwargs):
        if speed is not None:
            print(f"[{self.__class__.__name__}] 动态设置转速为: {speed} RPM...")
            # 根据手册，转速单位为 0.01 RPM，所以需要乘以100
            speed_value = int(float(speed) * 100)
            return self._write_register(self.ADDR_SET_SPEED, speed_value)
        return False

    def get_status(self):
        if not self.is_connected:
            return {"is_running": False, "speed_rpm": 0.0}

        # 读取状态字
        status_word = self._read_register(self.ADDR_STATUS_WORD)
        # 读取设定的转速
        speed_value = self._read_register(self.ADDR_SET_SPEED)

        is_running = False
        if status_word is not None:
            # 检查运行位 (BIT0)
            is_running = (status_word & 0x01) == 1

        speed_rpm = 0.0
        if speed_value is not None:
            speed_rpm = speed_value / 100.0
        
        return {
            "is_running": is_running,
            "speed_rpm": speed_rpm
        }

    # --- 内部Modbus通信辅助函数 ---
    def _write_register(self, address, value):
        try:
            r = self.client.write_register(address, value, device_id=self.unit_address)
            return not r.isError()
        except ModbusException as e:
            print(f"[{self.__class__.__name__}] 写寄存器错误: {e}")
            return False

    def _read_register(self, address):
        try:
            r = self.client.read_holding_registers(address, 1, device_id=self.unit_address)
            return None if r.isError() else r.registers[0]
        except ModbusException as e:
            print(f"[{self.__class__.__name__}] 读寄存器错误: {e}")
            return None