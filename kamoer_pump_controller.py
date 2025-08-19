# kamoer_pump_controller.py

import time
import struct
from pymodbus.client.serial import ModbusSerialClient
from pymodbus.exceptions import ModbusException

class KamoerPulseController:
    """
    Kamoer 2802 脉冲发生控制板控制器
    """

    def __init__(self, port, unit=192, baudrate=9600, timeout=1):
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

    def enable_485_control(self, enable=True):
        """启用或禁用 485 通信控制。"""
        address = 0x1004
        action = "启用" if enable else "禁用"
        print(f"正在{action} 485 控制...")
        try:
            response = self.client.write_coil(address, enable, device_id=self.unit)
            if hasattr(response, 'isError') and response.isError():
                raise ModbusException(f"写入线圈 {address} 失败")
            print("485 控制设置成功。")
            return True
        except Exception as e:
            print(f"错误: {e}")
            return False

    def set_pump_state(self, start=True):
        """启动或停止泵。"""
        address = 0x1001
        action = "启动" if start else "停止"
        print(f"正在{action}泵...")
        try:
            response = self.client.write_coil(address, start, device_id=self.unit)
            if hasattr(response, 'isError') and response.isError():
                raise ModbusException(f"写入线圈 {address} 失败")
            print("泵状态更改成功。")
            return True
        except Exception as e:
            print(f"错误: {e}")
            return False

    def set_direction(self, direction='forward'):
        """设置电机的旋转方向。"""
        address = 0x1003
        value = (direction.lower() == 'reverse')
        print(f"设置方向为 {'反转' if value else '正转'}...")
        try:
            response = self.client.write_coil(address, value, device_id=self.unit)
            if hasattr(response, 'isError') and response.isError():
                raise ModbusException(f"写入线圈 {address} 失败")
            print("方向设置成功。")
            return True
        except Exception as e:
            print(f"错误: {e}")
            return False

    def set_speed(self, speed_rpm):
        """设置泵的目标转速。"""
        address1 = 0x3001 # 高位寄存器
        address2 = 0x3002 # 低位寄存器
        print(f"设置转速为 {speed_rpm} RPM...")
        try:
            # 手动将浮点数转换为两个16位寄存器值
            float_bytes = struct.pack('>f', speed_rpm)
            reg1 = struct.unpack('>H', float_bytes[:2])[0]
            reg2 = struct.unpack('>H', float_bytes[2:])[0]
            response = self.client.write_registers(address1, [reg1, reg2], device_id=self.unit)

            if hasattr(response, 'isError') and response.isError():
                raise ModbusException(f"写入寄存器 {address1} 失败")
            print("转速设置成功。")
            return True
        except Exception as e:
            print(f"错误: {e}")
            return False

    def read_real_time_speed(self):
            """读取泵的实时转速。"""
            # 根据手册，即时转速储存在 0x3005 (高16位) 和 0x3006 (低16位)
            address = 0x3005
            print("正在读取实时转速...")
            try:
                response = self.client.read_holding_registers(
                    address=address,
                    count=2,  # 读取2个寄存器以组成一个32位元浮点数
                    device_id=self.unit
                )

                if response.isError():
                    raise ModbusException(f"读取寄存器 {address} 时设备返回错误: {response}")

                # 检查是否成功读取到足够的数据
                if not hasattr(response, 'registers') or len(response.registers) < 2:
                    raise ModbusException("未能从设备读取到足够的寄存器数据")

                # 手动将收到的两个16位元寄存器解码为一个32位元浮点数
                # 根据手册，数据为大端序 (Big-Endian)
                high_word_bytes = struct.pack('>H', response.registers[0])
                low_word_bytes = struct.pack('>H', response.registers[1])
                float_bytes = high_word_bytes + low_word_bytes
                speed = struct.unpack('>f', float_bytes)[0]

                print(f"当前转速是: {speed:.2f} RPM")
                return speed
                
            except ModbusException as e:
                # 捕捉并打印 Modbus 相关的错误 (包含通讯逾时)
                print(f"读取转速时发生 Modbus 错误: {e}")
                return None
            except Exception as e:
                # 捕捉其他可能的错误，例如数据解析失败
                print(f"解析数据时发生意外错误: {e}")
                return None



# --- 使用示例 ---
if __name__ == '__main__':
    COM_PORT = 'COM3'  # 修改为您的实际串口
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
