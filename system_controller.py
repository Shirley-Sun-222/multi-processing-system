# file: system_controller.py (已将定时单位改为秒)

import time
import threading
from queue import Empty

from kamoer_pump_controller import KamoerPeristalticPump
from plunger_pump_controller import OushishengPlungerPump
from power_supply_controller import GPD4303SPowerSupply

def device_factory(config):
    """一个通用的设备工厂，可以创建泵或电源。"""
    device_type = config['type'].lower()
    if device_type == 'kamoer':
        return KamoerPeristalticPump(port=config['port'], unit_address=config['address'])
    elif device_type == 'oushisheng':
        return OushishengPlungerPump(port=config['port'], unit_address=config['address'])
    elif device_type == 'gpd_4303s':
        return GPD4303SPowerSupply(port=config['port'])
    else:
        raise ValueError(f"未知的设备类型: {device_type}")

class SystemController:
    def __init__(self, device_configs, command_queue, status_queue, log_queue):
        self.device_configs = device_configs
        self.command_queue = command_queue
        self.status_queue = status_queue
        self.log_queue = log_queue
        self.devices = {}
        self._running = True
        self.power_off_timer_thread = None

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
        cmd_type = command.get('type')
        params = command.get('params', {})
        self._log(f"后台进程：收到指令: {cmd_type}，参数: {params}")

        device_id = params.get('pump_id') or params.get('device_id')
        target_device = self.devices.get(device_id)

        if device_id and not target_device:
            self.status_queue.put({'error': f"指令失败：未找到ID为 '{device_id}' 的设备。"})
            return
        
        # ★★★ 修改点 1: 过滤参数时，键名从 'auto_off_minutes' 改为 'auto_off_seconds' ★★★
        filtered_params = {k: v for k, v in params.items() if k not in ['pump_id', 'device_id', 'auto_off_seconds']}
        
        if cmd_type == 'start_pump':
            target_device.start(**filtered_params)
        elif cmd_type == 'stop_pump':
            target_device.stop()
        elif cmd_type == 'set_pump_params':
            target_device.set_parameters(**filtered_params)
        elif cmd_type == 'set_power_voltage':
            target_device.set_voltage(params['channel'], params['voltage'])
        elif cmd_type == 'set_power_current':
            target_device.set_current(params['channel'], params['current'])
        elif cmd_type == 'set_power_output':
            if self.power_off_timer_thread and self.power_off_timer_thread.is_alive():
                 self._log("后台进程: 检测到新的电源操作，正在停止旧的定时关闭任务。")
            
            target_device.set_output(params['enable'])
            
            # ★★★ 修改点 2: 检查的键名改为 'auto_off_seconds' ★★★
            if params['enable'] and 'auto_off_seconds' in params:
                duration_seconds = params['auto_off_seconds']
                if duration_seconds > 0:
                    self.power_off_timer_thread = threading.Thread(
                        target=self._power_off_timer, 
                        args=(duration_seconds, device_id)
                    )
                    self.power_off_timer_thread.daemon = True
                    self.power_off_timer_thread.start()

        elif cmd_type == 'run_protocol':
            threading.Thread(target=self._execute_protocol, args=(params.get('protocol', []),)).start()
        elif cmd_type == 'stop_all':
            for dev in self.devices.values():
                if hasattr(dev, 'stop'): dev.stop()
                if hasattr(dev, 'set_output'): dev.set_output(False)
        elif cmd_type == 'shutdown':
            self._running = False
        else:
            self._log(f"后台进程：收到未知指令: {cmd_type}")

    # ★★★ 修改点 3: 修改定时器函数的参数和日志信息 ★★★
    def _power_off_timer(self, duration_seconds, device_id):
        """在一个独立的线程中等待指定时间，然后发送关闭电源的命令。"""
        self._log(f"后台进程：电源定时关闭任务已启动，将在 {duration_seconds} 秒后关闭 {device_id}。")
        
        # 直接使用传入的秒数，不再需要乘以60
        time.sleep(duration_seconds)
        
        if self._running:
            self._log(f"后台进程：{duration_seconds} 秒时间到，正在发送关闭 {device_id} 的指令。")
            self.command_queue.put({
                'type': 'set_power_output',
                'params': {'device_id': device_id, 'enable': False}
            })
        else:
            self._log(f"后台进程：定时任务时间到，但主程序已关闭，取消自动关机。")

    def _publish_status(self):
        system_status = {'timestamp': time.time(), 'devices': {}}
        for dev_id, dev_obj in self.devices.items():
            system_status['devices'][dev_id] = dev_obj.get_status()
        print(f"[后台] 推送状态: {system_status}")
        self.status_queue.put(system_status)

    def _shutdown(self):
        self._log(f"后台进程：正在安全关闭所有设备...")
        self._running = False
        for device in self.devices.values():
            if hasattr(device, 'is_connected') and device.is_connected:
                device.disconnect()
        self._log(f"后台进程：已安全关闭。")

    def _execute_protocol(self, protocol):
        self._log(f"开始执行自动化协议...")
        try:
            for step in protocol:
                if not self._running:
                    self._log("协议执行被中断。")
                    break
                
                command_type = step.get('command')
                if not command_type: continue

                if command_type == 'delay':
                    duration = step.get('duration', 0)
                    self._log(f" -> 协议步骤：延时 {duration} 秒")
                    time.sleep(duration)
                else:
                    params = {k: v for k, v in step.items() if k != 'command'}
                    command_to_process = {'type': command_type, 'params': params}
                    self._process_command(command_to_process)
                    time.sleep(0.1)
            
            if self._running:
                self.status_queue.put({'info': '自动化协议执行完毕。'})
                self._log(f"自动化协议执行完毕。")
        except Exception as e:
            error_msg = f"协议执行出错: {e}"
            self.status_queue.put({'error': error_msg})
            self._log(error_msg)