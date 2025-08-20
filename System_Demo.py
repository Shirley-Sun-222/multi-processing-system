# file: main_control_logic.py (示例)

from kamoer_pump_controller import KamoerPeristalticPump
from plunger_pump_controller import OushishengPlungerPump
import time

# --- 系统 A 的配置 --- # 需要修改
pump_a1_config = {'type': 'kamoer', 'port': 'COM3', 'address': 192}
pump_a2_config = {'type': 'plunger', 'port': 'COM3', 'address': 1} # 假设它们在同一个485总线上

# --- 创建泵的实例 ---
# 这里可以使用一个工厂函数来根据配置创建不同的泵对象
def pump_factory(config):
    if config['type'] == 'kamoer':
        return KamoerPeristalticPump(port=config['port'], unit_address=config['address'])
    elif config['type'] == 'plunger':
        return OushishengPlungerPump(port=config['port'], unit_address=config['address'])
    else:
        raise ValueError(f"未知的泵类型: {config['type']}")

pump1 = pump_factory(pump_a1_config)
pump2 = pump_factory(pump_a2_config)

# --- 统一的控制流程 ---
pumps = [pump1, pump2]

for p in pumps:
    p.connect()

time.sleep(1)

# 使用统一的接口启动不同的泵
pump1.start(speed=50.0, direction='reverse')
pump2.start(flow_rate=2.5)

time.sleep(5)

# 使用统一的接口获取状态
status1 = pump1.get_status()
status2 = pump2.get_status()
print(f"泵1状态: {status1}")
print(f"泵2状态: {status2}")

time.sleep(1)

# 使用统一的接口停止
for p in pumps:
    p.stop()
    p.disconnect()