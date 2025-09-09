# file: system_controller.py (修复完善版)

import time
import threading
from queue import Empty

from kamoer_pump_controller import KamoerPeristalticPump
from plunger_pump_controller import OushishengPlungerPump
from lange_pump_controller import LangePeristalticPump
from power_supply_controller import GPD4303SPowerSupply

def device_factory(config):
    """一个通用的设备工厂，可以创建泵或电源。"""
    device_type = config['type'].lower()
    if device_type == 'kamoer':
        return KamoerPeristalticPump(port=config['port'], unit_address=config['address'])
    elif device_type == 'oushisheng':
        return OushishengPlungerPump(port=config['port'], unit_address=config['address'])
    elif device_type == 'lange':
        return LangePeristalticPump(port=config['port'], unit_address=config['address'])
    elif device_type == 'gpd_4303s':
        return GPD4303SPowerSupply(port=config['port'])
    else:
        raise ValueError(f"未知的设备类型: {device_type}")

class SystemController:
    def __init__(self, config, command_queue, status_queue, log_queue):
        self.config = config
        self.command_queue = command_queue
        self.status_queue = status_queue
        self.log_queue = log_queue
        self.pumps = {}
        self.power_supplies = {}
        self._running = True

    def _log(self, message):
        """将日志消息同时打印到控制台并放入日志队列。"""
        print(message)
        if self.log_queue:
            self.log_queue.put(message)

    # 只要一个设备连接失败，就关闭控制系统
    
    # def _setup_devices(self):
    #     self._log(f"[{self.config['system_name']}] 正在设置设备...")
    #     try:
    #         if 'pumps' in self.config:
    #             for pump_config in self.config['pumps']:
    #                 self.pumps[pump_config['id']] = device_factory(pump_config)
            
    #         if 'power_supplies' in self.config:
    #             for ps_config in self.config['power_supplies']:
    #                 self.power_supplies[ps_config['id']] = device_factory(ps_config)

    #         all_devices = list(self.pumps.values()) + list(self.power_supplies.values())
    #         self._log(f"[{self.config['system_name']}] 正在连接所有设备...")
    #         for device_obj in all_devices:
    #             if not device_obj.connect():
    #                 # connect 方法内部会打印失败信息
    #                 raise ConnectionError(f"设备 {device_obj.__class__.__name__} on {device_obj.port} 连接失败。")
            
    #         self._log(f"[{self.config['system_name']}] 所有设备已连接并准备就绪。")
    #         return True
    #     except Exception as e:
    #         self._log(f"[{self.config['system_name']}] 设备设置失败: {e}")
    #         self._shutdown()
    #         return False


    # 当一个设备连接失败时，继续尝试连接其他设备。可用于调试。
    
    def _setup_devices(self):
        self._log(f"[{self.config['system_name']}] 正在设置设备...")
        errors = []
        # 创建设备对象
        if 'pumps' in self.config:
            for pump_config in self.config['pumps']:
                try:
                    self.pumps[pump_config['id']] = device_factory(pump_config)
                except Exception as e:
                    error_msg = f"泵 {pump_config.get('id', '')} 创建失败: {e}"
                    self._log(error_msg)
                    errors.append(error_msg)
        if 'power_supplies' in self.config:
            for ps_config in self.config['power_supplies']:
                try:
                    self.power_supplies[ps_config['id']] = device_factory(ps_config)
                except Exception as e:
                    error_msg = f"电源 {ps_config.get('id', '')} 创建失败: {e}"
                    self._log(error_msg)
                    errors.append(error_msg)

        # 连接设备
        all_devices = list(self.pumps.values()) + list(self.power_supplies.values())
        self._log(f"[{self.config['system_name']}] 正在连接所有设备...")
        for device_obj in all_devices:
            try:
                if not device_obj.connect():
                    error_msg = f"设备 {device_obj.__class__.__name__} on {getattr(device_obj, 'port', '?')} 连接失败。"
                    self._log(error_msg)
                    errors.append(error_msg)
            except Exception as e:
                error_msg = f"设备 {device_obj.__class__.__name__} on {getattr(device_obj, 'port', '?')} 连接异常: {e}"
                self._log(error_msg)
                errors.append(error_msg)

        if errors:
            self._log(f"[{self.config['system_name']}] 部分设备连接失败:\n" + "\n".join(errors))
            # 不调用 self._shutdown()，让已连接设备继续工作
            return False
        self._log(f"[{self.config['system_name']}] 所有设备已连接并准备就绪。")
        return True

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
        self._log(f"[{self.config['system_name']}] 收到指令: {cmd_type}，参数: {params}")

        # --- 泵指令 ---
        if cmd_type in ['start_pump', 'stop_pump', 'set_pump_params']:
            pump_id = params.get('pump_id')
            target_pump = self.pumps.get(pump_id)
            if not target_pump:
                self.status_queue.put({'error': f"指令失败：未找到ID为 '{pump_id}' 的泵。"})
                return
            if cmd_type == 'start_pump':
                params.pop('pump_id', None)
                target_pump.start(**params)
            elif cmd_type == 'stop_pump':
                target_pump.stop()
            elif cmd_type == 'set_pump_params':
                params.pop('pump_id', None)
                target_pump.set_parameters(**params)
        
        # --- 电源指令 ---
        elif cmd_type in ['set_power_voltage', 'set_power_current', 'set_power_output']:
            ps_id = params.get('device_id')
            target_ps = self.power_supplies.get(ps_id)
            if not target_ps:
                self.status_queue.put({'error': f"指令失败：未找到ID为 '{ps_id}' 的电源。"})
                return
            if cmd_type == 'set_power_voltage':
                target_ps.set_voltage(params.get('channel'), params.get('voltage'))
            elif cmd_type == 'set_power_current':
                target_ps.set_current(params.get('channel'), params.get('current'))
            elif cmd_type == 'set_power_output':
                target_ps.set_output(params.get('enable'))
        
        # --- 协议指令 ---
        elif cmd_type == 'run_protocol':
            protocol = params.get('protocol')
            if protocol:
                threading.Thread(target=self._execute_protocol, args=(protocol,)).start()
        
        # --- 全局指令 ---
        elif cmd_type == 'stop_all':
            for pump in self.pumps.values(): pump.stop()
            for ps in self.power_supplies.values(): ps.set_output(enable=False)
        elif cmd_type == 'shutdown':
            self._running = False
        else:
            self._log(f"[{self.config['system_name']}] 收到未知指令: {cmd_type}")

    def _publish_status(self):
        system_status = {'timestamp': time.time(), 'pumps': {}, 'power_supplies': {}}
        for pump_id, pump_obj in self.pumps.items():
            system_status['pumps'][pump_id] = pump_obj.get_status()
        for ps_id, ps_obj in self.power_supplies.items():
            system_status['power_supplies'][ps_id] = ps_obj.get_status()
        self.status_queue.put(system_status)

    def _shutdown(self):
        all_devices = list(self.pumps.values()) + list(self.power_supplies.values())
        self._log(f"[{self.config['system_name']}] 正在安全关闭所有设备...")
        for device in all_devices:
            if hasattr(device, 'is_connected') and device.is_connected:
                device.disconnect()
        self._log(f"[{self.config['system_name']}] 已安全关闭。")

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