# file: system_controller.py (V2.0 - 支持新架构)

import time
import threading
from queue import Empty

# 假设这些控制器类存在且功能正确
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
    """
    后台控制器进程。
    管理一个电源系统下的所有硬件设备。
    """
    def __init__(self, device_configs, command_queue, status_queue, log_queue):
        self.device_configs = device_configs
        self.command_queue = command_queue
        self.status_queue = status_queue
        self.log_queue = log_queue
        self.devices = {}
        self._running = True
        self.power_off_timer_thread = None
        
        # 定时器相关变量
        self.ui_update_interval = 1.0  # UI状态每秒更新一次
        self.data_log_interval = 30.0  # 数据记录默认间隔30秒
        self.last_log_time = 0

    def _log(self, message):
        """向UI发送日志信息。"""
        print(message)
        if self.log_queue: self.log_queue.put(message)

    def _setup_devices(self):
        """根据配置初始化并连接所有硬件设备。"""
        self._log("后台进程：正在设置设备...")
        try:
            for config in self.device_configs:
                dev_id = config['id']
                self._log(f" -> 正在创建设备: {dev_id} ({config['type']})")
                self.devices[dev_id] = device_factory(config)

            self._log("后台进程：正在连接所有设备...")
            for dev_id, dev_obj in self.devices.items():
                if not dev_obj.connect():
                    raise ConnectionError(f"设备 {dev_id} 连接失败。")
            
            self._log("后台进程：所有设备连接成功。")
            return True
        except Exception as e:
            self._log(f"后台进程：设备设置失败: {e}")
            self._shutdown()
            return False

    def run(self):
        """控制器主循环。"""
        if not self._setup_devices():
            if self.log_queue: self.log_queue.put("STOP")
            return

        last_status_time = time.time()
        self.last_log_time = last_status_time

        while self._running:
            # 1. 处理来自UI的指令
            try:
                command = self.command_queue.get_nowait()
                self._process_command(command)
            except Empty:
                pass

            current_time = time.time()
            
            # 2. 定时推送实时状态给UI (用于图表)
            if current_time - last_status_time >= self.ui_update_interval:
                self._publish_status(loggable=False)
                last_status_time = current_time

            # 3. 根据用户设置的间隔，推送可记录的数据点
            if current_time - self.last_log_time >= self.data_log_interval:
                self._publish_status(loggable=True) # 标记这个点是需要记录的
                self.last_log_time = current_time

            time.sleep(0.05)

        self._shutdown()
        if self.log_queue: self.log_queue.put("STOP")

    def _process_command(self, command):
        """解析并执行来自UI的指令。"""
        cmd_type = command.get('type')
        params = command.get('params', {})
        self._log(f"后台进程：收到指令: {cmd_type}，参数: {params}")

        device_id = params.get('pump_id') or params.get('device_id')
        target_device = self.devices.get(device_id)

        if cmd_type not in ['shutdown', 'stop_all', 'set_log_interval'] and not target_device:
            self.status_queue.put({'error': f"指令失败：未找到ID为 '{device_id}' 的设备。"})
            return
        
        # --- 指令处理 ---
        if cmd_type == 'set_power_output':
            if self.power_off_timer_thread and self.power_off_timer_thread.is_alive():
                self._log("后台进程: 停止旧的定时关闭任务。")
            target_device.set_output(params['enable'])
            if params['enable'] and 'auto_off_seconds' in params:
                duration = params['auto_off_seconds']
                if duration > 0:
                    self.power_off_timer_thread = threading.Thread(target=self._power_off_timer, args=(duration, device_id))
                    self.power_off_timer_thread.daemon = True
                    self.power_off_timer_thread.start()
        
        elif cmd_type == 'set_power_voltage':
            target_device.set_voltage(params['channel'], params['voltage'])
        
        elif cmd_type == 'set_power_current':
            target_device.set_current(params['channel'], params['current'])

        elif cmd_type == 'start_pump':
            target_device.start(speed=params.get('speed'), flow_rate=params.get('flow_rate'), direction=params.get('direction'))

        elif cmd_type == 'stop_pump':
            target_device.stop()

        elif cmd_type == 'set_pump_params':
            target_device.set_parameters(speed=params.get('speed'), flow_rate=params.get('flow_rate'), direction=params.get('direction'))
        
        elif cmd_type == 'set_log_interval':
            new_interval = params.get('interval', 30.0)
            if new_interval > 0:
                self.data_log_interval = new_interval
                self._log(f"后台进程: 数据记录间隔已更新为 {new_interval} 秒。")

        elif cmd_type == 'stop_all':
            for dev in self.devices.values():
                if hasattr(dev, 'stop'): dev.stop()
                if hasattr(dev, 'set_output'): dev.set_output(False)
        
        elif cmd_type == 'shutdown':
            self._running = False

    def _power_off_timer(self, duration_seconds, device_id):
        """后台计时器，用于定时关闭电源。"""
        self._log(f"后台进程：定时关闭任务已启动，将在 {duration_seconds} 秒后关闭 {device_id}。")
        time.sleep(duration_seconds)
        if self._running:
            self._log(f"后台进程：{duration_seconds} 秒时间到，正在自动关闭 {device_id}。")
            self.command_queue.put({'type': 'set_power_output', 'params': {'device_id': device_id, 'enable': False}})

    def _publish_status(self, loggable=False):
        """获取所有设备状态并发送到UI。"""
        system_status = {
            'timestamp': time.time(),
            'devices': {},
            'loggable': loggable # 附加一个标志位
        }
        for dev_id, dev_obj in self.devices.items():
            system_status['devices'][dev_id] = dev_obj.get_status()
        self.status_queue.put(system_status)

    def _shutdown(self):
        """安全关闭所有设备连接。"""
        self._log("后台进程：正在安全关闭所有设备...")
        self._running = False
        for device in self.devices.values():
            if hasattr(device, 'is_connected') and device.is_connected:
                device.disconnect()
        self._log("后台进程：所有设备已安全关闭。")
