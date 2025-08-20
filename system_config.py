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
    'power_supply': {
        'port': 'COM5'
        # ... 其他电源相关配置
    }
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
    'power_supply': {
        'port': 'COM8'
    }
}