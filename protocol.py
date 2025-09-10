# 这是一个协议的例子
auto_protocol = [
    {'command': 'start_pump', 'pump_id': 'peristaltic_1', 'params': {'speed': 100}},
    {'command': 'delay', 'duration': 5},  # 延时5秒
    {'command': 'start_pump', 'pump_id': 'plunger_pump', 'params': {'flow_rate': 2.0}},
    {'command': 'delay', 'duration': 10}, # 再延时10秒
    {'command': 'set_pump_params', 'pump_id': 'peristaltic_1', 'params': {'speed': 200}}, # 蠕动泵提速
    {'command': 'delay', 'duration': 5},
    {'command': 'stop_pump', 'pump_id': 'peristaltic_1'},
    {'command': 'stop_pump', 'pump_id': 'plunger_pump'}
]