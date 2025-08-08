# kamoer_pulse_controller.py

import time
import struct
from pymodbus.client import ModbusSerialClient
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.constants import Endian
from pymodbus.exceptions import ModbusException

class KamoerPulseController:
    """
    一个通过 RS485 和 Modbus RTU 协议控制 Kamoer 2802 脉冲发生控制板的类。

    该类的实现基于《2802脉冲发生控制板说明书_A3_2024-06-13.pdf》。
    """

    def __init__(self, port, unit=192, baudrate=9600, timeout=1):
        """
        初始化用于串口通信的 Modbus 客户端。

        :param port: 串口端口 (例如，在 Windows 上是 'COM3'，在 Linux 上是 '/dev/ttyUSB0')。
        :param unit: 设备的 Modbus 从机地址 (slave ID)。
                     根据说明书，默认地址为 192。
        :param baudrate: 通信波特率。默认为 9600。
        :param timeout: 连接超时时间（秒）。
        """
        # 串口默认设置为 8 个数据位，无校验位，1 个停止位。
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
        """
        启用或禁用 485 通信控制。
        设备上电后必须调用此方法并设置为 True。

        :param enable: True 为启用，False 为禁用。
        """
        # 对应于线圈寄存器 0x1004。
        address = 0x1004
        action = "启用" if enable else "禁用"
        print(f"正在{action} 485 控制...")
        try:
            # write_coil 使用功能码 0x05。
            response = self.client.write_coil(address, enable, unit=self.unit)
            if response.isError():
                raise ModbusException(f"写入线圈 {address} 失败")
            print("485 控制设置成功。")
            return True
        except ModbusException as e:
            print(f"错误: {e}")
            return False

    def set_pump_state(self, start=True):
        """
        启动或停止泵。

        :param start: True 为启动泵，False 为停止泵。
        """
        # 对应于线圈寄存器 0x1001。
        address = 0x1001
        action = "启动" if start else "停止"
        print(f"正在{action}泵...")
        try:
            # write_coil 使用功能码 0x05。
            response = self.client.write_coil(address, start, unit=self.unit)
            if response.isError():
                raise ModbusException(f"写入线圈 {address} 失败")
            print("泵状态更改成功。")
            return True
        except ModbusException as e:
            print(f"错误: {e}")
            return False

    def set_direction(self, direction='forward'):
        """
        设置电机的旋转方向。

        :param direction: 'forward' 代表正转 (0)，'reverse' 代表反转 (1)。
        """
        # 对应于线圈寄存器 0x1003。
        address = 0x1003
        value = (direction.lower() == 'reverse')  # False 为 0 (正转), True 为 1 (反转)
        print(f"设置方向为 {'反转' if value else '正转'}...")
        try:
            response = self.client.write_coil(address, value, unit=self.unit)
            if response.isError():
                raise ModbusException(f"写入线圈 {address} 失败")
            print("方向设置成功。")
            return True
        except ModbusException as e:
            print(f"错误: {e}")
            return False

    def set_speed(self, speed_rpm):
        """
        设置泵的目标转速。

        :param speed_rpm: 期望的转速，单位为转/分钟 (浮点数)。
        """
        # 对应于保持寄存器 0x3001 和 0x3002，用于一个单精度浮点数。
        address = 0x3001
        print(f"设置转速为 {speed_rpm} RPM...")
        try:
            # 说明书示例显示写入32位浮点数需要使用功能码 0x10。
            builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
            builder.add_32bit_float(speed_rpm)
            payload = builder.to_registers()
            
            response = self.client.write_registers(address, payload, unit=self.unit, skip_encode=True)
            if response.isError():
                raise ModbusException(f"写入寄存器 {address} 失败")
            print("转速设置成功。")
            return True
        except ModbusException as e:
            print(f"错误: {e}")
            return False

    def read_real_time_speed(self):
        """
        读取泵的当前实时转速。

        :return: 当前转速 (RPM) 的浮点数，如果读取失败则返回 None。
        """
        # 对应于保持寄存器 0x3005 和 0x3006，用于一个单精度浮点数。
        address = 0x3005
        print("正在读取实时转速...")
        try:
            # read_holding_registers 使用功能码 0x03。
            response = self.client.read_holding_registers(address, 2, unit=self.unit)
            if response.isError():
                raise ModbusException(f"读取寄存器 {address} 失败")

            # 从两个16位寄存器中解码出32位浮点数。
            b1 = (response.registers[0] >> 8) & 0xFF
            b2 = response.registers[0] & 0xFF
            b3 = (response.registers[1] >> 8) & 0xFF
            b4 = response.registers[1] & 0xFF
            
            byte_string = bytes([b1, b2, b3, b4])
            speed = struct.unpack('>f', byte_string)[0]
            
            print(f"当前转速是: {speed:.2f} RPM")
            return speed
        except ModbusException as e:
            print(f"错误: {e}")
            return None

# --- 使用示例 ---
if __name__ == '__main__':
    # 重要提示：请将 'COM_PORT' 替换为您的实际串口名称。
    # 在 Windows 上可能是 'COM3', 'COM4' 等。
    # 在 Linux 或 macOS 上可能是 '/dev/ttyUSB0', '/dev/tty.usbserial-xxxx' 等。
    COM_PORT = 'COM_PORT' # <-- 修改这里
    
    # 默认地址是 192，波特率是 9600。
    # 如果您重新配置了设备，请修改这些值。
    DEVICE_ADDRESS = 192 # 来自 C011 设置
    BAUD_RATE = 9600     # 来自 C012 设置

    if COM_PORT == 'COM_PORT':
        print("请编辑此脚本并设置 COM_PORT 变量。")
    else:
        # 1. 初始化控制器
        controller = KamoerPulseController(port=COM_PORT, unit=DEVICE_ADDRESS, baudrate=BAUD_RATE)

        # 2. 连接到设备
        if controller.connect():
            try:
                # 3. 关键步骤：启用 485 控制。
                # 在此之前，控制板不会响应其他命令。
                if not controller.enable_485_control(enable=True):
                    raise RuntimeError("无法启用 485 控制。程序中止。")
                
                time.sleep(1) # 等待片刻

                # 4. 设置泵的方向
                controller.set_direction('forward')
                time.sleep(1)

                # 5. 设置泵的转速为 100 RPM
                controller.set_speed(100.0)
                time.sleep(1)

                # 6. 启动泵
                print("\n--- 启动泵，运行 5 秒 ---")
                controller.set_pump_state(start=True)
                
                # 让它运行并检查转速
                time.sleep(2)
                controller.read_real_time_speed()
                time.sleep(3)

                # 7. 停止泵
                print("\n--- 停止泵 ---")
                controller.set_pump_state(start=False)
                time.sleep(1)

                # 8. 停止后检查转速
                controller.read_real_time_speed()
                
            except Exception as e:
                print(f"操作过程中发生错误: {e}")
            finally:
                # 9. 关闭连接
                controller.close()