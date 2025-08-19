# kamoer_pump_controller.py (重构版/手动浮点数转换)

import time
import struct
from pymodbus.client import ModbusSerialClient
# 已移除 BinaryPayloadBuilder 的导入
from pymodbus.exceptions import ModbusException

class KamoerPulseController:
    """
    Kamoer 2802 脉冲发生控制板控制器 (重构版)
    """

    def __init__(self, port, unit=192, baudrate=9600, timeout=1):
        """
        初始化用于串口通讯的 Modbus 客户端。

        :param port: 串口端口。
        :param unit: 设备的 Modbus 从机地址。
        :param baudrate: 波特率。
        :param timeout: 通讯超时时间（秒）。
        """
        self.client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            parity='N',
            stopbits=1,
            bytesize=8
        )
        self.unit = unit

    def connect(self):
        """建立与串口的连接。"""
        print("正在连接设备...")
        if self.client.connect():
            print("连接成功。")
            return True
        else:
            print("连接失败。")
            return False

    def close(self):
        """关闭串口连接。"""
        print("正在关闭连接。")
        self.client.close()

    # --- 内部辅助函数 ---
    def _write_coil(self, address, value):
        """通用的写入线圈内部函数。"""
        try:
            response = self.client.write_coil(address, value, device_id=self.unit)
            if response.isError():
                raise ModbusException(f"写入线圈 {address} 失败")
            return True
        except ModbusException as e:
            print(f"错误: {e}")
            return False

    def _write_multiple_registers(self, address, values):
        """通用的写入多个寄存器内部函数。"""
        try:
            # 注意：此处的 values 预期是一个包含整数的列表 [reg1, reg2]
            response = self.client.write_registers(address, values, device_id=self.unit)
            if response.isError():
                raise ModbusException(f"写入多个寄存器 {address} 失败")
            return True
        except ModbusException as e:
            print(f"错误: {e}")
            return False
            
    def _read_holding_registers(self, address, count):
        """通用的读取保持寄存器内部函数。"""
        try:
            response = self.client.read_holding_registers(address, count, device_id=self.unit)
            if response.isError():
                raise ModbusException(f"读取寄存器 {address} 失败")
            return response.registers
        except ModbusException as e:
            print(f"错误: {e}")
            return None

    # --- 公共控制函数 ---
    def enable_485_control(self, enable=True):
        """启用或禁用 485 通信控制。"""
        address = 0x1004
        action = "启用" if enable else "禁用"
        print(f"正在{action} 485 控制...")
        if self._write_coil(address, enable):
            print("485 控制设置成功。")
            return True
        return False

    def set_pump_state(self, start=True):
        """启动或停止泵。"""
        address = 0x1001
        action = "启动" if start else "停止"
        print(f"正在{action}泵...")
        if self._write_coil(address, start):
            print("泵状态更改成功。")
            return True
        return False

    def set_direction(self, direction='forward'):
        """设置电机的旋转方向。"""
        address = 0x1003
        value = (direction.lower() == 'reverse')
        print(f"设置方向为 {'反转' if value else '正转'}...")
        if self._write_coil(address, value):
            print("方向设置成功。")
            return True
        return False

    def set_speed(self, speed_rpm):
        """设置泵的目标转速。"""
        address = 0x3001
        print(f"设置转速为 {speed_rpm} RPM...")
        
        try:
            # ## 使用手动方式将浮点数转换为两个16位寄存器值 ##
            float_bytes = struct.pack('>f', speed_rpm)
            reg1 = struct.unpack('>H', float_bytes[:2])[0]
            reg2 = struct.unpack('>H', float_bytes[2:])[0]
            payload = [reg1, reg2]
            
            if self._write_multiple_registers(address, payload):
                print("转速设置成功。")
                return True
            return False
        except Exception as e:
            print(f"转换浮点数时发生错误: {e}")
            return False

    def read_real_time_speed(self):
        """读取泵的实时转速。"""
        address = 0x3005
        print("正在读取实时转速...")
        
        registers = self._read_holding_registers(address, 2)
        
        if registers and len(registers) >= 2:
            high_word_bytes = struct.pack('>H', registers[0])
            low_word_bytes = struct.pack('>H', registers[1])
            float_bytes = high_word_bytes + low_word_bytes
            speed = struct.unpack('>f', float_bytes)[0]
            
            print(f"当前转速是: {speed:.2f} RPM")
            return speed
        
        return None


# --- 使用示例 ---
if __name__ == '__main__':
    COM_PORT = 'COM_PORT'  # 修改为您的实际串口
    DEVICE_ADDRESS = 192
    BAUD_RATE = 9600

    if COM_PORT == 'COM_PORT':
        print("请先修改 COM_PORT 变量为您的实际串口。")
    else:
        controller = KamoerPulseController(
            port=COM_PORT,
            unit=DEVICE_ADDRESS,
            baudrate=BAUD_RATE
        )
        if controller.connect():
            try:
                # 启用485控制
                if not controller.enable_485_control(enable=True):
                    raise RuntimeError("无法启用 485 控制，程序中止。")
                time.sleep(1)

                # 设置转速为 100 RPM
                controller.set_speed(100.0)
                time.sleep(1)

                print("\n--- 启动泵，运行 5 秒 ---")
                controller.set_pump_state(start=True)
                time.sleep(2)
                
                # 读取实时转速
                controller.read_real_time_speed()
                time.sleep(3)

                print("\n--- 停止泵 ---")
                controller.set_pump_state(start=False)
                time.sleep(1)
                
                # 停止后检查转速
                controller.read_real_time_speed()
                
            except Exception as e:
                print(f"操作过程中发生错误: {e}")
            finally:
                controller.close()