# file: app_main.py (支持从文件加载协议的最终注释版)

# 导入必要的系统和多进程库
import sys
import multiprocessing
import json # 用于解析协议文件
from queue import Empty

# 导入PyQt6的核心组件
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, QGridLayout,
                             QMessageBox, QTextEdit, QGroupBox, QFileDialog)
from PyQt6.QtCore import QTimer

# 导入我们自己编写的控制器、配置和示例协议
from system_controller import SystemController
from system_config import SYSTEM_A_CONFIG, SYSTEM_B_CONFIG
from protocol import auto_protocol

class ControlPanel(QMainWindow):
    """
    主控制面板窗口类。
    每个实例都管理着一套独立的硬件系统（通过一个独立的后台进程）。
    """
    def __init__(self, config):
        super().__init__()
        # 保存传入的系统配置 (SYSTEM_A_CONFIG 或 SYSTEM_B_CONFIG)
        self.config = config
        self.setWindowTitle(f"{config['system_name']} 控制面板")
        self.setGeometry(100, 100, 750, 450) # 设置窗口初始位置和大小

        # 初始化后台进程和通信队列的占位符
        self.process = None
        self.command_queue = None
        self.status_queue = None
        
        # 调用方法来构建界面和启动后台
        self._init_ui()
        self._start_backend()

    def _init_ui(self):
        """
        初始化并布局窗口中的所有UI控件。
        """
        # --- 1. 创建手动控制区域 ---
        manual_group = QGroupBox("手动独立控制")
        grid = QGridLayout()
        
        # 创建蠕动泵1的所有控件
        self.p1_label = QLabel(f"蠕动泵 1 ({self.config['pumps'][0]['description']})")
        self.p1_speed_input = QLineEdit("100.0")
        self.p1_set_button = QPushButton("设置转速")
        self.p1_start_button = QPushButton("启动")
        self.p1_stop_button = QPushButton("停止")
        self.p1_status_label = QLabel("状态: 未知")
        
        # 创建柱塞泵的所有控件
        self.p2_label = QLabel(f"柱塞泵 ({self.config['pumps'][2]['description']})")
        self.p2_flow_input = QLineEdit("5.0")
        self.p2_set_button = QPushButton("设置流量")
        self.p2_start_button = QPushButton("启动")
        self.p2_stop_button = QPushButton("停止")
        self.p2_status_label = QLabel("状态: 未知")

        # 将控件添加到网格布局中
        grid.addWidget(self.p1_label, 0, 0); grid.addWidget(QLabel("转速(RPM):"), 0, 1); grid.addWidget(self.p1_speed_input, 0, 2); grid.addWidget(self.p1_set_button, 0, 3); grid.addWidget(self.p1_start_button, 0, 4); grid.addWidget(self.p1_stop_button, 0, 5); grid.addWidget(self.p1_status_label, 0, 6)
        grid.addWidget(self.p2_label, 1, 0); grid.addWidget(QLabel("流量(ml/min):"), 1, 1); grid.addWidget(self.p2_flow_input, 1, 2); grid.addWidget(self.p2_set_button, 1, 3); grid.addWidget(self.p2_start_button, 1, 4); grid.addWidget(self.p2_stop_button, 1, 5); grid.addWidget(self.p2_status_label, 1, 6)
        grid.setColumnStretch(6, 1) # 让状态标签列自动伸展
        manual_group.setLayout(grid)

        # --- 2. 创建自动化协议区域 ---
        protocol_group = QGroupBox("自动化协议控制")
        protocol_layout = QVBoxLayout()
        self.protocol_editor = QTextEdit()
        # 将导入的示例协议格式化后，作为默认内容显示在编辑器中
        self.protocol_editor.setText(json.dumps(auto_protocol, indent=4))
        
        protocol_button_layout = QHBoxLayout()
        self.load_protocol_button = QPushButton("从文件加载协议...") # 加载文件按钮
        self.run_protocol_button = QPushButton("执行编辑器中的协议")  # 执行按钮
        protocol_button_layout.addWidget(self.load_protocol_button)
        protocol_button_layout.addWidget(self.run_protocol_button)

        protocol_layout.addWidget(QLabel("协议编辑器 (JSON格式):"))
        protocol_layout.addWidget(self.protocol_editor)
        protocol_layout.addLayout(protocol_button_layout)
        protocol_group.setLayout(protocol_layout)

        # --- 3. 创建全局控制按钮 ---
        self.stop_all_button = QPushButton("!! 全部紧急停止 !!")
        self.stop_all_button.setStyleSheet("background-color: #d9534f; color: white;") # 设置红色警告样式

        # --- 4. 设置窗口主布局 ---
        main_layout = QVBoxLayout()
        main_layout.addWidget(manual_group)
        main_layout.addWidget(protocol_group)
        main_layout.addWidget(self.stop_all_button)
        
        # 将主布局应用到窗口的中央控件
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # --- 5. 连接控件的信号到处理函数(槽) ---
        # 手动控制按钮的连接
        self.p1_start_button.clicked.connect(lambda: self.on_start('peristaltic_1'))
        self.p1_stop_button.clicked.connect(lambda: self.on_stop('peristaltic_1'))
        self.p1_set_button.clicked.connect(lambda: self.on_set_params('peristaltic_1'))
        self.p2_start_button.clicked.connect(lambda: self.on_start('plunger_pump'))
        self.p2_stop_button.clicked.connect(lambda: self.on_stop('plunger_pump'))
        self.p2_set_button.clicked.connect(lambda: self.on_set_params('plunger_pump'))
        
        # 全局和协议按钮的连接
        self.stop_all_button.clicked.connect(self.on_stop_all)
        self.load_protocol_button.clicked.connect(self.on_load_protocol_from_file)
        self.run_protocol_button.clicked.connect(self.on_run_protocol)

    def _start_backend(self):
        """
        启动后台独立的 SystemController 进程。
        """
        # 创建用于进程间通信的队列
        self.command_queue = multiprocessing.Queue()
        self.status_queue = multiprocessing.Queue()
        
        # 创建控制器实例，并将队列传递给它
        controller = SystemController(self.config, self.command_queue, self.status_queue)
        
        # 创建一个新进程，指定其任务是运行 controller.run() 方法
        self.process = multiprocessing.Process(target=controller.run)
        self.process.start() # 启动进程

        # 创建一个定时器，定期调用 update_status_display 方法来刷新UI
        self.timer = QTimer(self)
        self.timer.setInterval(500) # 设置周期为500毫秒
        self.timer.timeout.connect(self.update_status_display)
        self.timer.start()

    # --- 事件处理函数(槽) ---

    def on_load_protocol_from_file(self):
        """当“从文件加载协议”按钮被点击时，弹出文件选择对话框。"""
        file_name, _ = QFileDialog.getOpenFileName(self, "选择协议文件", "", "JSON Files (*.json);;All Files (*)")
        
        if file_name: # 如果用户选择了文件
            try:
                with open(file_name, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 尝试美化JSON格式后显示
                    try: self.protocol_editor.setText(json.dumps(json.loads(content), indent=4))
                    except: self.protocol_editor.setText(content) # 如果不是标准JSON，直接显示原文
            except Exception as e:
                QMessageBox.critical(self, "文件读取错误", f"无法读取文件: {e}")

    def on_run_protocol(self):
        """当“执行协议”按钮被点击时，解析编辑器内容并发送指令。"""
        try:
            protocol_list = json.loads(self.protocol_editor.toPlainText())
            if not isinstance(protocol_list, list): raise ValueError("协议必须是一个列表")
            
            # 将解析后的协议列表发送到后台
            command = {'type': 'run_protocol', 'params': {'protocol': protocol_list}}
            self.command_queue.put(command)
            QMessageBox.information(self, "协议已启动", "自动化协议已发送到后台执行。")
        except Exception as e:
            QMessageBox.critical(self, "协议格式或内容错误", str(e))

    def on_start(self, pump_id):
        """处理单个泵的“启动”按钮点击事件。"""
        try:
            params = {'pump_id': pump_id}
            if pump_id == 'peristaltic_1': params['speed'] = float(self.p1_speed_input.text())
            elif pump_id == 'plunger_pump': params['flow_rate'] = float(self.p2_flow_input.text())
            # 发送 'start_pump' 指令到命令队列
            self.command_queue.put({'type': 'start_pump', 'params': params})
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数字！")

    def on_stop(self, pump_id):
        """处理单个泵的“停止”按钮点击事件。"""
        self.command_queue.put({'type': 'stop_pump', 'params': {'pump_id': pump_id}})

    def on_set_params(self, pump_id):
        """处理单个泵的“设置”按钮点击事件。"""
        try:
            params = {'pump_id': pump_id}
            if pump_id == 'peristaltic_1': params['speed'] = float(self.p1_speed_input.text())
            elif pump_id == 'plunger_pump': params['flow_rate'] = float(self.p2_flow_input.text())
            self.command_queue.put({'type': 'set_pump_params', 'params': params})
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数字！")
    
    def on_stop_all(self):
        """处理“全部紧急停止”按钮点击事件。"""
        self.command_queue.put({'type': 'stop_all'})

    def update_status_display(self):
        """
        定时器触发此函数，从状态队列中获取最新数据并更新UI。
        """
        try:
            status = None
            # 循环读取，确保处理的是最新的状态信息
            while not self.status_queue.empty(): status = self.status_queue.get_nowait()
            
            if status:
                # 检查后台是否发来错误或通知信息
                if 'error' in status: QMessageBox.critical(self, "后台错误", status['error']); return
                if 'info' in status: QMessageBox.information(self, "后台通知", status['info'])
                
                # 更新各个泵的状态显示
                p1_status = status['pumps'].get('peristaltic_1', {})
                self.p1_status_label.setText(f"状态: {'运行中' if p1_status.get('is_running') else '已停止'} | 转速: {p1_status.get('speed_rpm', 0.0):.2f}")
                
                p2_status = status['pumps'].get('plunger_pump', {})
                self.p2_status_label.setText(f"状态: {'运行中' if p2_status.get('is_running') else '已停止'} | 流量: {p2_status.get('flow_rate_ml_min', 0.0):.3f}")
        except Empty: pass # 队列为空是正常情况
        except Exception as e: print(f"[{self.config['system_name']}-GUI] 更新状态时出错: {e}")

    def closeEvent(self, event):
        """重写窗口关闭事件，确保后台进程能被安全地关闭。"""
        self.timer.stop() # 停止UI刷新
        if self.process and self.process.is_alive():
            self.command_queue.put({'type': 'shutdown'}) # 发送关闭指令
            self.process.join(timeout=5) # 等待后台进程退出
            if self.process.is_alive(): self.process.terminate() # 如果超时仍未退出，则强制终止
        event.accept()

class MainApp(QMainWindow):
    """
    程序的主入口窗口，用于启动各个系统的控制面板。
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("多系统泵控制程序"); self.setGeometry(300, 300, 300, 150)
        self.control_windows = {} # 用来存储已打开的控制窗口，避免重复打开

        layout = QVBoxLayout()
        self.btn_sys_a = QPushButton("打开 系统 A 控制面板")
        self.btn_sys_a.clicked.connect(lambda: self.open_control_panel('A', SYSTEM_A_CONFIG))
        self.btn_sys_b = QPushButton("打开 系统 B 控制面板")
        self.btn_sys_b.clicked.connect(lambda: self.open_control_panel('B', SYSTEM_B_CONFIG))
        layout.addWidget(self.btn_sys_a); layout.addWidget(self.btn_sys_b)
        
        central_widget = QWidget(); central_widget.setLayout(layout); self.setCentralWidget(central_widget)

    def open_control_panel(self, system_id, config):
        """打开一个控制面板，如果已打开则激活，否则创建新的。"""
        if system_id in self.control_windows and self.control_windows[system_id].isVisible():
            self.control_windows[system_id].activateWindow()
        else: 
            self.control_windows[system_id] = ControlPanel(config)
            self.control_windows[system_id].show()

# --- 程序主入口 ---
if __name__ == '__main__':
    # 在Windows和macOS上，多进程代码必须放在这个保护块内
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    main_window = MainApp()
    main_window.show()
    sys.exit(app.exec())