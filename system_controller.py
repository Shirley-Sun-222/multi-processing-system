# file: system_controller.py (修复完善版)

import time
import threading
from queue import Empty

from kamoer_pump_controller import KamoerPeristalticPump
from plunger_pump_controller import OushishengPlungerPump
# from lange_pump_controller import LangePeristalticPump
from power_supply_controller import GPD4303SPowerSupply

def device_factory(config):
    """一个通用的设备工厂，可以创建泵或电源。"""
    device_type = config['type'].lower()
    if device_type == 'kamoer':
        return KamoerPeristalticPump(port=config['port'], unit_address=config['address'])
    elif device_type == 'oushisheng':
        return OushishengPlungerPump(port=config['port'], unit_address=config['address'])
    # elif device_type == 'lange':
    #     return LangePeristalticPump(port=config['port'], unit_address=config['address'])
    elif device_type == 'gpd_4303s':
        return GPD4303SPowerSupply(port=config['port'])
    else:
        raise ValueError(f"未知的设备类型: {device_type}")

class SystemController:
    # 核心修改：__init__ 现在接收一个动态的设备配置列表
    def __init__(self, device_configs, command_queue, status_queue, log_queue):
        self.device_configs = device_configs
        self.command_queue = command_queue
        self.status_queue = status_queue
        self.log_queue = log_queue
        self.devices = {} # 使用一个通用的字典来存储所有设备
        self._running = True

    def _log(self, message):
        print(message)
        if self.log_queue: self.log_queue.put(message)

    def _setup_devices(self):
        self._log(f"后台进程：正在设置动态分配的设备...")
        try:
            for config in self.device_configs:
                dev_id = config['id']
                self._log(f" -> 正在创建设备: {dev_id} ({config['type']})")
                self.devices[dev_id] = device_factory(config)

            self._log(f"后台进程：正在连接所有设备...")
            for dev_id, dev_obj in self.devices.items():
                if not dev_obj.connect():
                    raise ConnectionError(f"设备 {dev_id} 连接失败。")
            
            self._log(f"后台进程：所有已分配设备连接成功。")
            return True
        except Exception as e:
            self._log(f"后台进程：设备设置失败: {e}")
            self._shutdown()
            return False

    def run(self):
        if not self._setup_devices():
            if self.log_queue: self.log_queue.put("STOP")
            return

        status_update_interval = 1.0
        last_status_time = time.time()
        while self._running:
            try:
                command = self.command_queue.get_nowait()
                self._process_command(command)
            except Empty:
                pass
            if time.time() - last_status_time >= status_update_interval:
                self._publish_status()
                last_status_time = time.time()
            time.sleep(0.05)

        self._shutdown()
        if self.log_queue: self.log_queue.put("STOP")

    def _process_command(self, command):
        # 简化：所有设备都在一个字典里，通过ID查找
        cmd_type = command.get('type')
        params = command.get('params', {})
        self._log(f"后台进程：收到指令: {cmd_type}，参数: {params}")

        device_id = params.get('pump_id') or params.get('device_id')
        target_device = self.devices.get(device_id)

        if device_id and not target_device:
            self.status_queue.put({'error': f"指令失败：未找到ID为 '{device_id}' 的设备。"})
            return
        
        # (泵和电源的指令处理逻辑保持不变)
        if cmd_type == 'start_pump': target_device.start(**params);
        elif cmd_type == 'stop_pump': target_device.stop();
        elif cmd_type == 'set_pump_params': target_device.set_parameters(**params);
        elif cmd_type == 'set_power_voltage': target_device.set_voltage(params['channel'], params['voltage']);
        elif cmd_type == 'set_power_current': target_device.set_current(params['channel'], params['current']);
        elif cmd_type == 'set_power_output': target_device.set_output(params['enable']);
        elif cmd_type == 'run_protocol': threading.Thread(target=self._execute_protocol, args=(command.get('protocol', []),)).start()
        elif cmd_type == 'stop_all':
            for dev in self.devices.values():
                if hasattr(dev, 'stop'): dev.stop()
                if hasattr(dev, 'set_output'): dev.set_output(False)
        elif cmd_type == 'shutdown': self._running = False
        else: self._log(f"后台进程：收到未知指令: {cmd_type}")

    def _publish_status(self):
        system_status = {'timestamp': time.time(), 'devices': {}}
        for dev_id, dev_obj in self.devices.items():
            system_status['devices'][dev_id] = dev_obj.get_status()
        self.status_queue.put(system_status)

    def _shutdown(self):
        self._log(f"后台进程：正在安全关闭所有设备...")
        for device in self.devices.values():
            if hasattr(device, 'is_connected') and device.is_connected:
                device.disconnect()
        self._log(f"后台进程：已安全关闭。")

    def _execute_protocol(self, protocol):
        self._log(f"[{self.config['system_name']}] 开始执行自动化协议...")
        try:
            for step in protocol:
                command_type = step.get('command')
                if not command_type: continue
                if command_type == 'delay':
                    self._log(f" -> 协议步骤：延时 {step.get('duration', 0)} 秒")
                    time.sleep(step.get('duration', 0))
                else:
                    params = {k: v for k, v in step.items() if k != 'command'}
                    command_to_process = {'type': command_type, 'params': params}
                    self._process_command(command_to_process)
            self.status_queue.put({'info': '自动化协议执行完毕。'})
            self._log(f"[{self.config['system_name']}] 自动化协议执行完毕。")
        except Exception as e:
            error_msg = f"协议执行出错: {e}"
            self.status_queue.put({'error': error_msg})
            self._log(error_msg)