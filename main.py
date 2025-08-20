# file: main.py (或 gui.py)

import multiprocessing as mp # 多进程库
import time
from system_controller import SystemController
from system_config import SYSTEM_A_CONFIG # 导入系统 A 的配置

def start_system_control_process(config):
    """
    一个工厂函数，用于创建队列、控制器实例和并启动进程。
    
    :param config: 系统配置字典。
    :return: (进程对象, 命令队列, 状态队列)
    """
    command_queue = mp.Queue()
    status_queue = mp.Queue()

    # 1. 创建控制器实例
    controller = SystemController(config, command_queue, status_queue)

    # 2. 创建一个新进程，目标是运行控制器的 run 方法
    process = mp.Process(target=controller.run)
    process.start()
    
    print(f"已为 [{config['system_name']}] 启动后台控制进程，PID: {process.pid}")
    
    return process, command_queue, status_queue

if __name__ == '__main__':
    # ！！！在 Windows 上，多进程代码必须放在 if __name__ == '__main__': 块内
    
    print("--- 启动系统 A 控制 ---")
    process_A, cmd_q_A, status_q_A = start_system_control_process(SYSTEM_A_CONFIG)

    # 主进程 (GUI) 可以像这样与后台进程交互
    try:
        # 等待几秒钟让设备初始化
        print("\n主进程：等待 5 秒让后台完成初始化...")
        time.sleep(5)

        # 从状态队列获取一次初始状态
        print("\n主进程：获取初始状态...")
        initial_status = status_q_A.get(timeout=2)
        print(f" -> 收到状态: {initial_status}")

        # 发送一个启动指令
        print("\n主进程：发送 'start_process' 指令...")
        cmd_q_A.put({
            'type': 'start_process',
            'params': {'flow_rate': 3.5, 'speed': 150.0}
        })

        # 模拟运行，持续获取状态更新
        print("\n主进程：模拟运行 5 秒，并持续打印状态...")
        for _ in range(5):
            try:
                status = status_q_A.get(timeout=2)
                print(f" -> 收到状态: {status['pumps']['plunger_pump']}")
                time.sleep(1)
            except Empty:
                print(" -> 未收到状态更新...")

        # 发送停止指令
        print("\n主进程：发送 'stop_all' 指令...")
        cmd_q_A.put({'type': 'stop_all'})
        time.sleep(2)

    except Exception as e:
        print(f"主进程发生错误: {e}")
    finally:
        # 在程序结束时，发送关闭指令，并等待进程结束
        print("\n主进程：发送 'shutdown' 指令并等待进程结束...")
        cmd_q_A.put({'type': 'shutdown'})
        process_A.join(timeout=5) # 等待进程结束
        if process_A.is_alive():
            print("警告：进程未能正常退出，强制终止。")
            process_A.terminate()
        print("--- 系统 A 控制结束 ---")