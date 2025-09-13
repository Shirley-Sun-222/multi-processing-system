'''
# file: kamoer_pump_controller.py (继承 BasePump 的版本)

Author: Xueli Sun
Date: 2025.8.19
Version:1.0

Kamoer Peristaltic Pump Controller. Inherits from BasePump and implements the required interface.

'''

import time
import struct
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from base_pump import BasePump

class KamoerPeristalticPump(BasePump):
    """
    Kamoer 2802 脉冲发生控制板控制器。
    此类继承自 BasePump，并实现了其定义的标准接口。
    """
    def __init__(self, port, unit_address=192, baudrate=9600, timeout=1):
        # 首先调用父类的 __init__ 方法
        super().__init__(port, unit_address, baudrate)
        # 然后进行自己的初始化
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
        print(f"[{self.__class__.__name__}] 正在连接设备...")
        if self.client.connect():
            self.is_connected = True
            print(f"[{self.__class__.__name__}] 连接成功。")
            # 启用485控制是该泵的特定初始化步骤
            return self._enable_485_control(True)
        else:
            self.is_connected = False
            print(f"[{self.__class__.__name__}] 连接失败。")
            return False

    def disconnect(self):
        print(f"[{self.__class__.__name__}] 正在关闭连接。")
        self.client.close()
        self.is_connected = False

    def start(self, speed=100.0, direction='forward'):
        """
        启动蠕动泵。

        :param speed: 目标转速 (RPM)。
        :param direction: 旋转方向 ('forward' 或 'reverse')。
        """
        print(f"[{self.__class__.__name__}] 正在启动泵，转速: {speed} RPM, 方向: {direction}...")
        if not self.is_connected:
            print("错误: 设备未连接。")
            return False
        
        # 蠕动泵需要先设方向和速度，再启动
        self._set_direction(direction)
        time.sleep(0.1) # 短暂延时确保指令被处理
        self._set_speed(speed)
        time.sleep(0.1)
        return self._set_pump_state(start=True)

    def stop(self):
        print(f"[{self.__class__.__name__}] 正在停止泵...")
        return self._set_pump_state(start=False)

    def set_parameters(self, speed=None, direction=None, **kwargs):
        """
        在线设置泵的运行参数。
        """
        if not self.is_connected:
            print("错误: 设备未连接。")
            return False
        
        success = True
        # 如果提供了 direction 参数，则设置方向
        if direction is not None:
            print(f"[{self.__class__.__name__}] 动态设置方向为: {direction}...")
            if not self._set_direction(direction):
                success = False
            time.sleep(0.05) # 增加延时确保指令执行

        # 如果提供了 speed 参数，则设置速度
        if speed is not None:
            print(f"[{self.__class__.__name__}] 动态设置转速为: {speed} RPM...")
            if not self._set_speed(speed):
                success = False
        
        return success
        
    def get_status(self):
        speed = self._read_real_time_speed()
        is_running = speed is not None and speed > 0.01

        # ★★★ 核心修正: 如果泵没有运行，实际转速为0 ★★★
        actual_speed = speed if is_running else 0.0
        
        return {
            "is_running": is_running,
            "speed_rpm": actual_speed if actual_speed is not None else 0.0,
            "flow_rate_ml_min": 0.0 # 蠕动泵主要通过转速控制
        }

    # --- 内部辅助函数 (加上下划线表示内部使用) ---
    def _enable_485_control(self, enable=True):
        address = 0x1004
        return self._write_coil(address, enable)

    def _set_pump_state(self, start=True):
        address = 0x1001
        return self._write_coil(address, start)

    def _set_direction(self, direction='forward'):
        address = 0x1003
        value = (direction.lower() == 'reverse')
        return self._write_coil(address, value)

    def _set_speed(self, speed_rpm):
        address = 0x3001
        try:
            float_bytes = struct.pack('>f', float(speed_rpm))
            reg1 = struct.unpack('>H', float_bytes[:2])[0]
            reg2 = struct.unpack('>H', float_bytes[2:])[0]
            return self._write_multiple_registers(address, [reg1, reg2])
        except Exception as e:
            print(f"[{self.__class__.__name__}] 转换浮点数时发生错误: {e}")
            return False

    def _read_real_time_speed(self):
        address = 0x3005
        
        # ★★★ 修改点：将一次性读2个寄存器，改为分两次、每次读1个 ★★★
        
        # registers = self._read_holding_registers(address, 2) # 这是旧的、有问题的代码行
        
        reg1 = self._read_holding_registers(address, 1)
        reg2 = self._read_holding_registers(address + 1, 1) # 读取下一个地址的寄存器

        # 确保两次都读取成功
        if reg1 is not None and reg2 is not None:
            # pymodbus 默认返回列表，需要从中取出单个值
            registers = [reg1[0], reg2[0]] 
            float_bytes = struct.pack('>HH', *registers)
            return struct.unpack('>f', float_bytes)[0]
            
        return None


    def _write_coil(self, address, value):
        try:
            r = self.client.write_coil(address, value, device_id=self.unit_address)
            return not r.isError()
        except ModbusException as e:
            print(f"[{self.__class__.__name__}] 错误: {e}")
            return False

    def _write_multiple_registers(self, address, values):
        try:
            r = self.client.write_registers(address, values, device_id=self.unit_address)
            return not r.isError()
        except ModbusException as e:
            print(f"[{self.__class__.__name__}] 错误: {e}")
            return False
            
    def _read_holding_registers(self, address, count):
        try:
            r = self.client.read_holding_registers(address, device_id=self.unit_address) #这个地方一直有bug，如出错，尝试增在address后增加count参数
            return None if r.isError() else r.registers
        except ModbusException as e:
            print(f"[{self.__class__.__name__}] 错误: {e}")
            return None