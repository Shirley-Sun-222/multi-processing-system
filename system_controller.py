# file: system_controller.py (异步+协议)

import time
import threading
from queue import Empty

# 导入我们之前定义的泵的子类
from kamoer_pump_controller import KamoerPeristalticPump
from plunger_pump_controller import OushishengPlungerPump
# from another_pump_controller import AnotherPeristalticPump # 如果有第二个蠕动泵类，也在这里导入

def pump_factory(config):
    """根据配置字典创建并返回相应的泵对象实例。"""
    pump_type = config['type'].lower()
    if pump_type == 'kamoer':
        return KamoerPeristalticPump(port=config['port'], unit_address=config['address'])
    elif pump_type == 'oushisheng':
        return OushishengPlungerPump(port=config['port'], unit_address=config['address'])
    # elif pump_type == 'another_brand':
    #     return AnotherPeristalticPump(port=config['port'], unit_address=config['address'])
    else:
        raise ValueError(f"未知的泵类型: {pump_type}")

class SystemController:
    """
    管理一套完整的硬件系统，并在独立的进程中运行。
    """
    def __init__(self, config, command_queue, status_queue):
        """
        初始化控制器。

        :param config: 描述此系统所有硬件的配置字典。
        :param command_queue: 用于从 GUI 接收指令的队列。
        :param status_queue: 用于向 GUI 发送状态更新的队列。
        """
        self.config = config
        self.command_queue = command_queue
        self.status_queue = status_queue
        self.pumps = {} # 用于存储所有泵对象的字典
        self._running = True # 控制主循环的标志

    def _setup_devices(self):
        """根据配置初始化所有硬件设备。"""
        print(f"[{self.config['system_name']}] 正在设置设备...")
        try:
            for pump_config in self.config['pumps']:
                pump_id = pump_config['id']
                print(f" -> 正在创建泵: {pump_id} ({pump_config['type']})")
                self.pumps[pump_id] = pump_factory(pump_config)
            
            print(f"[{self.config['system_name']}] 正在连接所有设备...")
            for pump_id, pump_obj in self.pumps.items():
                if not pump_obj.connect():
                    raise ConnectionError(f"设备 {pump_id} 连接失败。")
            
            print(f"[{self.config['system_name']}] 所有设备已连接并准备就绪。")
            return True
        except Exception as e:
            print(f"[{self.config['system_name']}] 设备设置失败: {e}")
            self._shutdown()
            return False

    def run(self):
        """
        控制器的主循环。这将是进程启动后执行的函数。
        """
        if not self._setup_devices():
            return

        status_update_interval = 1.0
        last_status_time = time.time()

        while self._running:
            try:
                command = self.command_queue.get_nowait()
                self._process_command(command)
            except Empty:
                pass
            
            if time.time() - last_status_time > status_update_interval:
                self._publish_status()
                last_status_time = time.time()

            time.sleep(0.05)

        self._shutdown()

    def _process_command(self, command):
        """
        解析并执行单个指令。(*** 此处是核心修改 ***)
        """
        cmd_type = command.get('type')
        params = command.get('params', {})
        pump_id = params.get('pump_id') # 大部分新指令都需要 pump_id

        print(f"[{self.config['system_name']}] 收到指令: {cmd_type}，参数: {params}")

        # 查找目标泵。如果指令需要 pump_id 但没找到，则报错并返回。
        target_pump = self.pumps.get(pump_id)
        if pump_id and not target_pump:
            error_message = f"指令失败：未找到ID为 '{pump_id}' 的泵。"
            print(f"[{self.config['system_name']}] {error_message}")
            self.status_queue.put({'error': error_message})
            return

        # --- 新的、更精细的指令处理逻辑 ---
        if cmd_type == 'start_pump':
            if target_pump:
                if not target_pump.is_connected:
                    self.status_queue.put({'error': f"启动失败: {pump_id} 未连接!"})
                else:
                    # 移除 'pump_id' 键，剩下的参数直接传递给泵的 start 方法
                    # e.g., params={'pump_id':'p1', 'speed':100} 变为 **{'speed':100}
                    params.pop('pump_id', None) 
                    target_pump.start(**params)
        
        elif cmd_type == 'stop_pump':
            if target_pump:
                target_pump.stop()

        elif cmd_type == 'set_pump_params':
            if target_pump:
                params.pop('pump_id', None)
                target_pump.set_parameters(**params)

        elif cmd_type == 'run_protocol':
            protocol = params.get('protocol')
            if protocol:
                protocol_thread = threading.Thread(target=self._execute_protocol, args=(protocol,))
                protocol_thread.start()

        elif cmd_type == 'stop_all':
            for pump in self.pumps.values():
                pump.stop()

        elif cmd_type == 'shutdown':
            self._running = False
        
        else:
            print(f"[{self.config['system_name']}] 收到未知指令: {cmd_type}")


    def _publish_status(self):
        """收集所有设备的状态并放入状态队列。"""
        system_status = {
            'timestamp': time.time(),
            'pumps': {}
        }
        for pump_id, pump_obj in self.pumps.items():
            system_status['pumps'][pump_id] = pump_obj.get_status()
        
        self.status_queue.put(system_status)

    def _shutdown(self):
        """安全地关闭所有硬件连接。"""
        print(f"[{self.config['system_name']}] 正在关闭所有设备连接...")
        for pump in self.pumps.values():
            if pump.is_connected:
                pump.stop()
                pump.disconnect()
        print(f"[{self.config['system_name']}] 已安全关闭。")

    def _execute_protocol(self, protocol):
        """
        在独立的线程中按顺序执行协议步骤。
        """
        print(f"[{self.config['system_name']}] 开始执行自动化协议...")
        try:
            for step in protocol:
                command_type = step.get('command')
                if not command_type:
                    continue

                if command_type == 'delay':
                    duration = step.get('duration', 0)
                    print(f" -> 协议步骤：延时 {duration} 秒")
                    time.sleep(duration)
                else:
                    # **优化点**: 直接构建一个与手动操作完全相同的指令字典
                    # 这样可以完美复用 _process_command 的全部逻辑，包括错误检查
                    params = {k: v for k, v in step.items() if k != 'command'}
                    command_to_process = {
                        'type': command_type,
                        'params': params
                    }
                    print(f" -> 协议步骤: {command_to_process}")
                    self._process_command(command_to_process)
            
            self.status_queue.put({'info': '自动化协议执行完毕。'}) # 通过状态队列向GUI发送完成通知
            print(f"[{self.config['system_name']}] 自动化协议执行完毕。")

        except Exception as e:
            error_msg = f"协议执行出错: {e}"
            self.status_queue.put({'error': error_msg}) # 将错误信息发送给GUI
            print(f"[{self.config['system_name']}] {error_msg}")