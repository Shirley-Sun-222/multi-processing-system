# file: system_config.py (V2.0.1 - 包含两个相同的系统配置)

# =================================================================================
# 全局系统配置
# ---------------------------------------------------------------------------------
# 程序启动时会为列表中的每个“系统集”创建一个独立的控制窗口。
# !!! 请务必为每个系统集修改 'port' 和 'id'，确保它们是唯一的 !!!
# =================================================================================

SYSTEM_SETS = [
    {
        # --- 系统集 1: 主要实验平台 ---
        "set_id": "power_supply_1_system",
        "set_description": "控制电源系统 1",

        "power_supply": {
            'id': 'gpd_power_1',
            'type': 'gpd_4303s',
            'port': 'ASRL6::INSTR', # ！！！修改为电源1的实际串口
            'description': '固纬 GPD-4303S 电源 #1'
        },
        "subsystem_A": {
            "channel": 1,
            "pumps": [
                {'id': 'kamoer_pump_1A', 'type': 'kamoer', 'port': 'COM3', 'address': 192, 'description': '系统1A-蠕动泵 #1'},
                {'id': 'kamoer_pump_1B', 'type': 'kamoer', 'port': 'COM4', 'address': 192, 'description': '系统1A-蠕动泵 #2'},
                {'id': 'plunger_pump_1A', 'type': 'oushisheng', 'port': 'COM5', 'address': 1, 'description': '系统1A-柱塞泵 #1'}
            ]
        },
        "subsystem_B": {
            "channel": 2,
            "pumps": [
                {'id': 'kamoer_pump_1C', 'type': 'kamoer', 'port': 'COM5', 'address': 1, 'description': '系统1B-蠕动泵 #3'},
                {'id': 'kamoer_pump_1D', 'type': 'kamoer', 'port': 'COM6', 'address': 192, 'description': '系统1B-蠕动泵 #4'},
                {'id': 'plunger_pump_1B', 'type': 'oushisheng', 'port': 'COM4', 'address': 55, 'description': '系统1B-柱塞泵 #2'}
            ]
        }
    },
    {
        # --- 系统集 2: 备份/平行实验平台 ---
        "set_id": "power_supply_2_system",
        "set_description": "控制电源系统 2",

        "power_supply": {
            'id': 'gpd_power_2', # ID必须唯一
            'type': 'gpd_4303s',
            'port': 'ASRL7::INSTR', # ！！！修改为电源2的实际串口
            'description': '固纬 GPD-4303S 电源 #2'
        },
        "subsystem_A": {
            "channel": 1,
            "pumps": [
                # 即使泵的型号相同，ID也必须是唯一的
                {'id': 'kamoer_pump_2A', 'type': 'kamoer', 'port': 'COM11', 'address': 192, 'description': '系统2A-蠕动泵 #1'},
                {'id': 'kamoer_pump_2B', 'type': 'kamoer', 'port': 'COM12', 'address': 192, 'description': '系统2A-蠕动泵 #2'},
                {'id': 'plunger_pump_2A', 'type': 'oushisheng', 'port': 'COM13', 'address': 55, 'description': '系统2A-柱塞泵 #1'}
            ]
        },
        "subsystem_B": {
            "channel": 2,
            "pumps": [
                {'id': 'kamoer_pump_2C', 'type': 'kamoer', 'port': 'COM14', 'address': 192, 'description': '系统2B-蠕动泵 #3'},
                {'id': 'kamoer_pump_2D', 'type': 'kamoer', 'port': 'COM15', 'address': 192, 'description': '系统2B-蠕动泵 #4'},
                {'id': 'plunger_pump_2B', 'type': 'oushisheng', 'port': 'COM16', 'address': 55, 'description': '系统2B-柱塞泵 #2'}
            ]
        }
    }
]