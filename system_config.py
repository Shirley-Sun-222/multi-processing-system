# file: system_config.py

# ==========================================================
# 系统 A 的硬件配置
# ==========================================================
SYSTEM_A_CONFIG = {
    'system_name': 'System A',
    'pumps': [
        {
            'id': 'peristaltic_1', # 给设备起一个唯一的内部名字
            'type': 'kamoer',     # 与 pump_factory 中的类型匹配
            'port': 'COM3',       # ！！！修改为系统 A 的实际串口
            'address': 192,
            'description': '卡默尔蠕动泵'
        },
        {
            'id': 'peristaltic_2',
            'type': 'lange', # 假设这是您的第二台不同品牌的蠕动泵
            'port': 'COM4',
            'address': 1,
            'description': '兰格蠕动泵'
        },
        {
            'id': 'plunger_pump',
            'type': 'oushisheng', # 与 pump_factory 中的类型匹配
            'port': 'COM3',       # 假设与卡默尔泵在同一 RS485 总线
            'address': 1,
            'description': '欧世盛柱塞泵'
        }
    ],
    'power_supplies': [
        {
            'id': 'gpd_power_1',
            'type': 'gpd_4303s',
            # USB连接通常会被识别为一个COM口，您需要在设备管理器中查看
            'port': 'COM5', # ！！！修改为电源的实际串口
            'description': '固纬 GPD-4303S 电源'
        }
    ]
}

# ==========================================================
# 系统 B 的硬件配置 (与系统 A 结构相同，但参数不同)
# ==========================================================
SYSTEM_B_CONFIG = {
    'system_name': 'System B',
    'pumps': [
        {
            'id': 'peristaltic_1',
            'type': 'kamoer',
            'port': 'COM6', # ！！！修改为系统 B 的实际串口
            'address': 192,
            'description': '卡默尔蠕动泵'
        },
        {
            'id': 'peristaltic_2',
            'type': 'lange',
            'port': 'COM7',
            'address': 1,
            'description': '兰格蠕动泵'
        },
        {
            'id': 'plunger_pump',
            'type': 'oushisheng',
            'port': 'COM6',
            'address': 1,
            'description': '欧世盛柱塞泵'
        }
    ],
    'power_supplies': [
        {
            'id': 'gpd_power_1',
            'type': 'gpd_4303s',
            'port': 'COM8', # ！！！修改为电源的实际串口
            'description': '固纬 GPD-4303S 电源'
        }
    ]
}