# file: app_main.py

import sys
import multiprocessing as mp
import time
from queue import Empty

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, QGridLayout,
                             QMessageBox)
from PyQt6.QtCore import QTimer

# 导入我们之前创建的控制器和配置
from system_controller import SystemController
from system_config import SYSTEM_A_CONFIG, SYSTEM_B_CONFIG

class ControlPanel(QMainWindow):
    """
    一个用于控制单个硬件系统的 GUI 窗口。
    """
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowTitle(f"{config['system_name']} 控制面板")
        self.setGeometry(100, 100, 500, 300) # x, y, width, height

        # 后台进程和通信队列
        self.process = None
        self.command_queue = None
        self.status_queue = None
        
        # 初始化 UI 和后台
        self._init_ui()
        self._start_backend()

    def _init_ui(self):
        """创建所有界面控件。"""
        # --- 创建控件 ---
        # 蠕动泵 1 (Kamoer)
        self.peristaltic1_label = QLabel(f"蠕动泵 1 ({self.config['pumps'][0]['description']})")
        self.peristaltic1_speed_input = QLineEdit("100.0")
        self.peristaltic1_status_label = QLabel("状态: 未知")
        
        # 柱塞泵
        self.plunger_label = QLabel(f"柱塞泵 ({self.config['pumps'][2]['description']})")
        self.plunger_flow_input = QLineEdit("5.0")
        self.plunger_status_label = QLabel("状态: 未知")
        
        # 控制按钮
        self.start_button = QPushButton("启动流程")
        self.stop_button = QPushButton("全部停止")

        # --- 布局 ---
        main_layout = QVBoxLayout()
        grid_layout = QGridLayout()
        
        grid_layout.addWidget(self.peristaltic1_label, 0, 0)
        grid_layout.addWidget(QLabel("转速 (RPM):"), 0, 1)
        grid_layout.addWidget(self.peristaltic1_speed_input, 0, 2)
        grid_layout.addWidget(self.peristaltic1_status_label, 0, 3)

        grid_layout.addWidget(self.plunger_label, 1, 0)
        grid_layout.addWidget(QLabel("流量 (ml/min):"), 1, 1)
        grid_layout.addWidget(self.plunger_flow_input, 1, 2)
        grid_layout.addWidget(self.plunger_status_label, 1, 3)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)

        main_layout.addLayout(grid_layout)
        main_layout.addLayout(button_layout)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # --- 连接信号与槽 ---
        self.start_button.clicked.connect(self.on_start_process)
        self.stop_button.clicked.connect(self.on_stop_all)

    def _start_backend(self):
        """启动后台的 SystemController 进程。"""
        self.command_queue = mp.Queue()
        self.status_queue = mp.Queue()

        controller = SystemController(self.config, self.command_queue, self.status_queue)
        self.process = mp.Process(target=controller.run)
        self.process.start()

        # 创建一个定时器，定期检查状态队列
        self.timer = QTimer(self)
        self.timer.setInterval(500) # 每 500 毫秒
        self.timer.timeout.connect(self.update_status_display)
        self.timer.start()

    # --- GUI 事件处理函数 (槽) ---
    def on_start_process(self):
        """当“启动流程”按钮被点击时调用。"""
        try:
            speed = float(self.peristaltic1_speed_input.text())
            flow = float(self.plunger_flow_input.text())
            
            # 构建指令并放入命令队列
            command = {
                'type': 'start_process',
                'params': {
                    'speed': speed,
                    'flow_rate': flow
                }
            }
            self.command_queue.put(command)
            print(f"[{self.config['system_name']}-GUI] 已发送指令: {command}")
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数字！")

    def on_stop_all(self):
        """当“全部停止”按钮被点击时调用。"""
        command = {'type': 'stop_all'}
        self.command_queue.put(command)
        print(f"[{self.config['system_name']}-GUI] 已发送指令: {command}")

    def update_status_display(self):
        """由 QTimer 定期调用，用于更新界面状态或显示错误。"""
        try:
            status = None
            while not self.status_queue.empty():
                status = self.status_queue.get_nowait()
            
            if status:
                # --- 错误处理逻辑 ---
                if 'error' in status:
                    # 如果状态字典中包含 'error' 键，则显示错误弹窗
                    error_msg = status['error']
                    QMessageBox.critical(self, "操作失败", error_msg)
                    return # 显示错误后，不再执行下面的状态更新
                # --- 错误处理结束 ---

                # (如果没有错误，则执行常规的状态更新)
                # 更新蠕动泵 1 的状态
                p1_status = status['pumps'].get('peristaltic_1', {})
                p1_running = p1_status.get('is_running', False)
                p1_speed = p1_status.get('speed_rpm', 0.0)
                self.peristaltic1_status_label.setText(f"状态: {'运行中' if p1_running else '已停止'} | 转速: {p1_speed:.2f}")

                # 更新柱塞泵的状态
                pl_status = status['pumps'].get('plunger_pump', {})
                pl_running = pl_status.get('is_running', False)
                pl_flow = pl_status.get('flow_rate_ml_min', 0.0)
                self.plunger_status_label.setText(f"状态: {'运行中' if pl_running else '已停止'} | 流量: {pl_flow:.3f}")

        except Empty:
            pass
        except Exception as e:
            print(f"[{self.config['system_name']}-GUI] 更新状态时出错: {e}")

    def closeEvent(self, event):
        """重写窗口关闭事件，以确保后台进程被安全关闭。"""
        print(f"[{self.config['system_name']}-GUI] 正在关闭窗口...")
        self.timer.stop() # 停止定时器
        
        # 发送关闭指令给后台进程
        if self.process and self.process.is_alive():
            print(" -> 发送 shutdown 指令给后台...")
            self.command_queue.put({'type': 'shutdown'})
            self.process.join(timeout=5) # 等待最多5秒
            if self.process.is_alive():
                print(" -> 后台进程未能正常退出，强制终止。")
                self.process.terminate()
        
        event.accept() # 接受关闭事件

class MainApp(QMainWindow):
    """程序的主入口窗口，用于启动各个系统的控制面板。"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("多系统泵控制程序")
        self.setGeometry(300, 300, 300, 150)
        self.control_windows = {} # 存储已打开的控制窗口

        layout = QVBoxLayout()
        
        self.btn_sys_a = QPushButton("打开 系统 A 控制面板")
        self.btn_sys_a.clicked.connect(lambda: self.open_control_panel('A', SYSTEM_A_CONFIG))
        
        self.btn_sys_b = QPushButton("打开 系统 B 控制面板")
        self.btn_sys_b.clicked.connect(lambda: self.open_control_panel('B', SYSTEM_B_CONFIG))
        
        layout.addWidget(self.btn_sys_a)
        layout.addWidget(self.btn_sys_b)
        
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def open_control_panel(self, system_id, config):
        # 如果窗口已经打开，则激活它，否则创建新窗口
        if system_id in self.control_windows and self.control_windows[system_id].isVisible():
            self.control_windows[system_id].activateWindow()
        else:
            self.control_windows[system_id] = ControlPanel(config)
            self.control_windows[system_id].show()

if __name__ == '__main__':
    # ！！！在 Windows 上，多进程代码必须放在 if __name__ == '__main__': 块内
    mp.freeze_support() # 对打包成 exe 很重要

    app = QApplication(sys.argv)
    main_window = MainApp()
    main_window.show()
    sys.exit(app.exec())