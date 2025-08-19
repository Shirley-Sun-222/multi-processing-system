# plunger_pump_controller.py

import time
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

class OushishengPlungerPump:
    """
    一个通过 RS485 和 Modbus RTU 协议控制欧世盛 (Oushisheng) 柱塞泵的类。

    此类的实现基于 "柱塞泵.pdf" 说明文件。
    通讯配置: 9600 波特率, N (无校验), 8 数据位, 1 停止位。
    """

    def __init__(self, port, unit=1, baudrate=9600, timeout=1):
        """
        初始化用于串口通讯的 Modbus 客户端。

        :param port: 串口端口 (例如，在 Windows 上是 'COM3'，在 Linux 上是 '/dev/ttyUSB0')。
        :param unit: 泵的 Modbus 从机地址 (slave ID)。有效范围 1-254。
        :param baudrate: 波特率，默认为 9600。
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
        print("正在连接柱塞泵...")
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

    def _write_register(self, address, value):
        """通用的写入寄存器内部函数。"""
        try:
            # 协议使用 0x06 功能码写入单一寄存器。
            response = self.client.write_register(address, value, unit=self.unit)
            if response.isError():
                raise ModbusException(f"写入寄存器 {address} 失败")
            return True
        except ModbusException as e:
            print(f"错误: {e}")
            return False

    def _read_register(self, address):
        """通用的读取寄存器内部函数。"""
        try:
            # 协议使用 0x03 功能码读取寄存器。
            response = self.client.read_holding_registers(address, 1, unit=self.unit)
            if response.isError():
                raise ModbusException(f"读取寄存器 {address} 失败")
            return response.registers[0]
        except ModbusException as e:
            print(f"错误: {e}")
            return None

    def set_flow_rate(self, flow_ml_min):
        """
        设定泵的目标流量。

        :param flow_ml_min: 流量值 (ml/min)。说明书单位为 0.001 ml/min。
        """
        address = 1
        # 根据说明书，数据需乘以 1000
        value = int(flow_ml_min * 1000)
        print(f"设定流量为 {flow_ml_min} ml/min (发送值: {value})...")
        if self._write_register(address, value):
            print("流量设定成功。")
            return True
        return False

    def set_pressure_limit(self, pressure_mpa):
        """
        设定泵的压力上限。

        :param pressure_mpa: 压力值 (MPa)。说明书单位为 0.1 MPa。
        """
        address = 2
        # 根据说明书，数据需乘以 10
        value = int(pressure_mpa * 10)
        print(f"设定压力上限为 {pressure_mpa} MPa (发送值: {value})...")
        if self._write_register(address, value):
            print("压力上限设定成功。")
            return True
        return False

    def start_pump(self):
        """启动泵。"""
        address = 5
        print("正在启动泵...")
        if self._write_register(address, 1):
            print("泵已启动。")
            return True
        return False

    def stop_pump(self):
        """停止泵。"""
        address = 7
        print("正在停止泵...")
        if self._write_register(address, 1):
            print("泵已停止。")
            return True
        return False

    def zero_pressure(self):
        """将压力读数清零。"""
        address = 8
        print("正在将压力清零...")
        if self._write_register(address, 1):
            print("压力已清零。")
            return True
        return False

    def read_pressure(self):
        """
        读取当前的压力值。

        :return: 当前压力 (MPa)，或在失败时返回 None。
        """
        address = 4
        # print("正在读取当前压力...") # 为避免运行时重复打印，可注释掉
        value = self._read_register(address)
        if value is not None:
            # 根据说明书，读取值需除以 10
            pressure = value / 10.0
            print(f"当前压力: {pressure:.2f} MPa")
            return pressure
        return None

    def is_running(self):
        """
        检查泵的运行状态。

        :return: 如果正在运行返回 True，否则返回 False。
        """
        address = 0x0E # 寄存器地址 E
        print("正在读取运行状态...")
        value = self._read_register(address)
        if value is not None:
            running = (value == 1)
            print(f"泵是否在运行: {running}")
            return running
        return None

    def read_set_flow_rate(self):
        """
        读取已设定的流量值。

        :return: 已设定的流量 (ml/min)，或在失败时返回 None。
        """
        address = 0x0B # 寄存器地址 B
        print("正在读取设定的流量...")
        value = self._read_register(address)
        if value is not None:
            # 读取值需除以 1000
            flow_rate = value / 1000.0
            print(f"已设定流量: {flow_rate:.3f} ml/min")
            return flow_rate
        return None

    def read_set_pressure_limit(self):
        """
        读取已设定的压力上限。

        :return: 已设定的压力上限 (MPa)，或在失败时返回 None。
        """
        address = 0x0C # 寄存器地址 C
        print("正在读取设定的压力上限...")
        value = self._read_register(address)
        if value is not None:
            # 读取值需除以 10
            pressure_limit = value / 10.0
            print(f"已设定压力上限: {pressure_limit:.1f} MPa")
            return pressure_limit
        return None

    def read_alarm_code(self):
        """
        读取目前的警报代码。

        :return: 描述警报的字符串，或在失败时返回 None。
        """
        address = 0x0D # 寄存器地址 D
        print("正在读取警报代码...")
        value = self._read_register(address)
        if value is not None:
            alarms = {
                0x0000: "无故障",
                0x0080: "超压",
                0x10040: "系统故障",
                0x100C0: "系统故障与超压"
            }
            alarm_status = alarms.get(value, f"未知代码: {hex(value)}")
            print(f"警报状态: {alarm_status}")
            return alarm_status
        return None
    
    def set_device_address(self, new_address):
        """
        设定泵的新 Modbus 地址。
        !!! 警告: 执行此操作时，Modbus 总线上只应连接一台设备。

        :param new_address: 新的地址 (1-254)。
        """
        if not 1 <= new_address <= 254:
            print("错误：地址必须在 1 到 254 之间。")
            return False
            
        address = 9
        universal_address = 0x55 # 十进制 85
        print(f"警告：正在使用通用地址 {universal_address} 设定新地址为 {new_address}...")
        print("请确保总线上只有一台设备！")
        
        try:
            response = self.client.write_register(address, new_address, unit=universal_address)
            if response.isError():
                raise ModbusException(f"设定新地址失败")
            print(f"地址设定成功。请使用新地址 {new_address} 与泵通讯。")
            # 更新当前对象的地址以匹配新地址
            self.unit = new_address
            return True
        except ModbusException as e:
            print(f"错误: {e}")
            return False

# --- 使用范例 ---
if __name__ == '__main__':
    # 重要提示：请将 'COM_PORT' 替换为您的实际串口名称。
    COM_PORT = 'COM_PORT' # <-- 修改这里
    # 这是您要通讯的泵的地址。出厂默认通常是 1。
    PUMP_ADDRESS = 1

    if COM_PORT == 'COM_PORT':
        print("请编辑此脚本并设置 COM_PORT 变量。")
    else:
        pump = OushishengPlungerPump(port=COM_PORT, unit=PUMP_ADDRESS)
        if pump.connect():
            try:
                # --- 读取初始状态 ---
                print("\n--- 读取初始状态 ---")
                pump.is_running()
                pump.read_set_flow_rate()
                pump.read_pressure()
                pump.read_alarm_code()
                time.sleep(1)

                # --- 设定新参数 ---
                print("\n--- 设定新参数 ---")
                pump.set_flow_rate(5.0)  # 设定流量为 5.0 ml/min
                time.sleep(0.5)
                pump.set_pressure_limit(20.0) # 设定压力上限为 20.0 MPa
                time.sleep(1)

                # --- 启动泵并运行 5 秒 ---
                print("\n--- 启动泵 5 秒 ---")
                pump.start_pump()
                for i in range(5):
                    time.sleep(1)
                    pump.read_pressure() # 运行时持续读取压力
                
                # --- 停止泵 ---
                print("\n--- 停止泵 ---")
                pump.stop_pump()
                time.sleep(1)
                pump.is_running()

            except Exception as e:
                print(f"操作过程中发生错误: {e}")
            finally:
                pump.close()