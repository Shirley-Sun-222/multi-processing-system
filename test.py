# file: manual_test.py

import struct
from pymodbus.client import ModbusSerialClient

# --- 请在这里配置您的泵的信息 ---
PUMP_PORT = 'COM5'  # 1号Kamoer泵的串口
PUMP_ADDRESS = 192  # Kamoer泵的Modbus地址

# ------------------------------------

client = ModbusSerialClient(port=PUMP_PORT, baudrate=9600, timeout=1)

print(f"正在连接 {PUMP_PORT}...")
if not client.connect():
    print("连接失败！请检查串口号是否正确，设备是否已上电。")
    exit()

print("连接成功！")

try:
    # 步骤 1: 启用485控制 (根据手册，这是必须的第一步)
    print("正在启用 485 控制...")
    response = client.write_coil(0x1004, True, device_id=PUMP_ADDRESS)
    if response.isError():
        print("!!! 启用 485 控制失败 !!!")
        print(f"错误详情: {response}")
    else:
        print(">>> 485 控制已启用。")

    # 步骤 2: 尝试读取单个寄存器 (这步应该会成功)
    print("\n正在尝试读取单个寄存器 (地址 0x3005)...")
    response = client.read_holding_registers(0x3005, 1, device_id=PUMP_ADDRESS)
    if response.isError():
        print("!!! 读取单个寄存器失败 !!!")
        print(f"错误详情: {response}")
    else:
        print(f">>> 成功读取单个寄存器，值为: {response.registers}")

    # 步骤 3: 尝试一次性读取两个寄存器 (这步很可能会复现报错)
    print("\n正在尝试一次性读取两个寄存器 (地址 0x3005, 数量 2)...")
    response = client.read_holding_registers(0x3005, 2, device_id=PUMP_ADDRESS)
    if response.isError():
        print("!!! 一次性读取两个寄存器失败 !!!")
        print(f"错误详情: {response}")
    else:
        print(f">>> 成功一次性读取两个寄存器，值为: {response.registers}")
        float_bytes = struct.pack('>HH', *response.registers)
        speed = struct.unpack('>f', float_bytes)[0]
        print(f">>> 解析出的实时速度为: {speed:.2f} RPM")

except Exception as e:
    print(f"\n!!!!!! 在测试过程中发生严重错误 !!!!!!!")
    print(f"错误类型: {type(e).__name__}")
    print(f"错误信息: {e}")

finally:
    client.close()
    print("\n连接已关闭。")