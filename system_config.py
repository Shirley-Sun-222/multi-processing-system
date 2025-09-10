# file: system_config.py (设备池最终版)

# ==========================================================
# 全局设备资源池
# 在这里列出您拥有的所有硬件设备及其连接信息。
# ==========================================================
DEVICE_POOL = {
    # 蠕动泵 (请确保 'id' 是唯一的)
    "pumps": [
        {
            'id': 'kamoer_pump_1',
            'type': 'kamoer',
            'port': 'COM5',       # ！！！修改为1号Kamoer泵的实际串口 COM？
            'address': 192,
            'description': '卡默尔蠕动泵 #1'
        },
        {
            'id': 'kamoer_pump_2',
            'type': 'kamoer',
            'port': 'COM4',       # ！！！修改为2号Kamoer泵的实际串口
            'address': 192,
            'description': '卡默尔蠕动泵 #2'
        },
        {
            'id': 'kamoer_pump_3',
            'type': 'kamoer',
            'port': 'COM5',       # ！！！修改为3号Kamoer泵的实际串口
            'address': 192,
            'description': '卡默尔蠕动泵 #3'
        },
        {
            'id': 'kamoer_pump_4',
            'type': 'kamoer',
            'port': 'COM6',       # ！！！修改为4号Kamoer泵的实际串口
            'address': 192,
            'description': '卡默尔蠕动泵 #4'
        },

        # 柱塞泵
        {
            'id': 'plunger_pump_1',
            'type': 'oushisheng',
            'port': 'COM4',       # ！！！修改为1号柱塞泵的实际串口 
            'address': 55,
            'description': '欧世盛柱塞泵 #1'
        },
        {
            'id': 'plunger_pump_2',
            'type': 'oushisheng',
            'port': 'COM4',       # ！！！修改为2号柱塞泵的实际串口
            'address': 1,
            'description': '欧世盛柱塞泵 #2'
        }
    ],

    # 电源供应器
    "power_supplies": [
        {
            'id': 'gpd_power_1',
            'type': 'gpd_4303s',
            'port': 'ASRL6::INSTR', # ！！！修改为电源的实际串口 ASRL？::INSTR
            'description': '固纬 GPD-4303S 电源'
        }
    ]
}