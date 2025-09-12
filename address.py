# file: change_known_address.py
from pymodbus.client import ModbusSerialClient

# --- 請修改以下配置 ---
PUMP_PORT = 'COM7'      # ！！！泵當前連接的COM端口！！！
CURRENT_ADDRESS = 85   # ！！！泵的當前已知地址！！！
NEW_ADDRESS = 2         # ！！！您想要設定的【新】地址！！！
# ---------------------

ADDRESS_REGISTER = 9

client = ModbusSerialClient(port=PUMP_PORT, baudrate=9600, timeout=1)

print(f"正在連接端口 {PUMP_PORT}...")

try:
    if not client.connect():
        print("連接失敗！請檢查COM端口和設備連接。")
        exit()

    print("連接成功！")
    print(f"準備發送指令：命令地址為 {CURRENT_ADDRESS} 的設備，將其地址修改為 {NEW_ADDRESS}...")

    # 直接與當前地址的設備通訊
    response = client.write_register(
        address=ADDRESS_REGISTER,
        value=NEW_ADDRESS,
        device_id=CURRENT_ADDRESS  # <-- 注意：這裡使用的是當前地址
    )

    if response.isError():
        print(f"!!! 地址設置失敗 !!!")
        print(f"設備返回錯誤: {response}")
    else:
        print(">>> 地址設置成功！")
        print(f">>> 請重啟泵的電源，並在 system_config.py 中更新地址為 {NEW_ADDRESS}。")

except Exception as e:
    print(f"發生意外錯誤: {e}")

finally:
    client.close()
    print("連接已關閉。")