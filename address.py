# file: change_known_address.py
from pymodbus.client import ModbusSerialClient

# 修改欧世盛泵的配置地址

# --- 请修改以下配置 ---
PUMP_PORT = 'COM7'      # ！！！泵当前连接的COM端口！！！
CURRENT_ADDRESS = 85    # ！！！泵的当前已知地址！！！
NEW_ADDRESS = 2         # ！！！您想要设定的【新】地址！！！
# ---------------------

ADDRESS_REGISTER = 9

client = ModbusSerialClient(port=PUMP_PORT, baudrate=9600, timeout=1)

print(f"正在连接端口 {PUMP_PORT}...")

try:
    if not client.connect():
        print("连接失败！请检查COM端口和设备连接。")
        exit()

    print("连接成功！")
    print(f"准备发送指令：命令地址为 {CURRENT_ADDRESS} 的设备，将其地址修改为 {NEW_ADDRESS}...")

    # 直接与当前地址的设备通讯
    response = client.write_register(
        address=ADDRESS_REGISTER,
        value=NEW_ADDRESS,
        device_id=CURRENT_ADDRESS  # <-- 注意：这里使用的是当前地址
    )

    if response.isError():
        print(f"!!! 地址设置失败 !!!")
        print(f"设备返回错误: {response}")
    else:
        print(">>> 地址设置成功！")
        print(f">>> 请重启泵的电源，并在 system_config.py 中更新地址为 {NEW_ADDRESS}。")

except Exception as e:
    print(f"发生意外错误: {e}")

finally:
    client.close()
    print("连接已关闭。")