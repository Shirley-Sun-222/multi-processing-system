# file: set_pump_address.py
from pymodbus.client import ModbusSerialClient

# --- 請修改以下配置 ---
PUMP_PORT = 'COM5'  # ！！！請修改為您連接的泵的實際COM端口！！！
NEW_ADDRESS = 1     # ！！！請設置您想要的新地址 (1-254之間的十進制數)！！！
# ---------------------

# 根據協議，修改地址時必須使用通用地址 0x55 (十進制 85)
UNIVERSAL_ADDRESS = 85
# 根據協議，地址設定功能對應的寄存器是 9
ADDRESS_REGISTER = 9

# 初始化Modbus客戶端
client = ModbusSerialClient(
    port=PUMP_PORT,
    baudrate=9600,
    timeout=1,
    parity='N',
    stopbits=1,
    bytesize=8
)

print(f"正在嘗試連接端口 {PUMP_PORT}...")

try:
    if not client.connect():
        print("連接失敗！請檢查：")
        print(f"1. COM端口 '{PUMP_PORT}' 是否正確。")
        print("2. 泵是否已上電，並且是唯一連接到電腦的設備。")
        exit()

    print("連接成功！")
    print(f"準備發送指令：使用通用地址 {UNIVERSAL_ADDRESS} 將新地址設置為 {NEW_ADDRESS}...")

    # 發送寫入指令來設定新地址
    # client.write_register(register_address, new_value, device_id)
    response = client.write_register(
        address=ADDRESS_REGISTER,
        value=NEW_ADDRESS,
        device_id=UNIVERSAL_ADDRESS
    )

    if response.isError():
        print(f"!!! 地址設置失敗 !!!")
        print(f"設備返回錯誤: {response}")
    else:
        print(">>> 地址設置成功！")
        print(f">>> 請重啟泵的電源，然後在 system_config.py 中將地址更新為 {NEW_ADDRESS}。")

except Exception as e:
    print(f"發生意外錯誤: {e}")

finally:
    client.close()
    print("連接已關閉。")