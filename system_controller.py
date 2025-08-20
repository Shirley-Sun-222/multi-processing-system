# file: system_controller.py

import time
from queue import Empty

# 导入我们之前定义的泵的子类
from kamoer_pump_controller import KamoerPeristalticPump
from plunger_pump_controller import OushishengPlungerPump
# from another_pump_controller import AnotherPeristalticPump # 导入您的第二个蠕动泵类

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

        :param config: 描述此系统所有硬件的配置字典 (例如 SYSTEM_A_CONFIG)。
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
                    # 如果有任何一个设备连接失败，则设置失败
                    raise ConnectionError(f"设备 {pump_id} 连接失败。")
            
            print(f"[{self.config['system_name']}] 所有设备已连接并准备就绪。")
            return True
        except Exception as e:
            print(f"[{self.config['system_name']}] 设备设置失败: {e}")
            self._shutdown() # 失败时尝试关闭已连接的设备
            return False

    def run(self):
        """
        控制器的主循环。这将是进程启动后执行的函数。
        """
        if not self._setup_devices():
            # 如果设备初始化失败，则进程直接退出
            return

        status_update_interval = 1.0 # 每隔1秒更新一次状态
        last_status_time = time.time()

        while self._running:
            # 1. 处理来自 GUI 的指令
            try:
                # 使用 get_nowait() 避免阻塞，让循环可以继续
                command = self.command_queue.get_nowait()
                self._process_command(command)
            except Empty:
                # 队列为空，是正常情况，什么都不做
                pass
            
            # 2. 定期向 GUI 发送状态更新
            if time.time() - last_status_time > status_update_interval:
                self._publish_status()
                last_status_time = time.time()

            time.sleep(0.05) # 短暂休眠，避免 CPU 占用过高

        # 循环结束后，执行清理工作
        self._shutdown()

    def _process_command(self, command):
        """解析并执行单个指令。"""
        cmd_type = command.get('type')
        params = command.get('params', {})
        print(f"[{self.config['system_name']}] 收到指令: {cmd_type}，参数: {params}")

        if cmd_type == 'start_process':
            # --- 连接检查逻辑 ---
            all_connected = True
            error_message = ""
            for pump_id, pump_obj in self.pumps.items():
                if not pump_obj.is_connected:
                    all_connected = False
                    error_message = f"启动失败：设备 '{pump_id}' 未连接或初始化失败。"
                    break # 发现一个未连接的就足够了

            if not all_connected:
                print(f"[{self.config['system_name']}] 错误: {error_message}")
                # 将错误信息发送回 GUI
                self.status_queue.put({'error': error_message})
                return # 中断执行，不启动泵
            # --- 检查结束 ---

            # 如果所有设备都已连接，则正常执行
            print(f"[{self.config['system_name']}] 连接检查通过，正在执行启动流程...")
            plunger = self.pumps.get('plunger_pump')
            peristaltic = self.pumps.get('peristaltic_1')
            if plunger and peristaltic:
                plunger.start(flow_rate=params.get('flow_rate', 1.0))
                peristaltic.start(speed=params.get('speed', 100.0))

        elif cmd_type == 'stop_all':
            for pump in self.pumps.values():
                pump.stop()

        elif cmd_type == 'shutdown':
            print(f"[{self.config['system_name']}] 收到关闭指令，准备退出...")
            self._running = False
            
    def _publish_status(self):
        """收集所有设备的状态并放入状态队列。"""
        system_status = {
            'timestamp': time.time(),
            'pumps': {}
        }
        for pump_id, pump_obj in self.pumps.items():
            system_status['pumps'][pump_id] = pump_obj.get_status()
        
        # 将整个状态字典放入队列
        self.status_queue.put(system_status)

    def _shutdown(self):
        """安全地关闭所有硬件连接。"""
        print(f"[{self.config['system_name']}] 正在关闭所有设备连接...")
        for pump in self.pumps.values():
            if pump.is_connected:
                pump.stop()
                pump.disconnect()
        print(f"[{self.config['system_name']}] 已安全关闭。")