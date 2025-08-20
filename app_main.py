# file: app_main.py (支持三个泵的最终版)

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
        self.setGeometry(100, 100, 750, 480) # 稍微增加窗口高度以容纳第三个泵

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
        
        # 创建蠕动泵1的所有控件 (kamoer)
        self.p1_label = QLabel(f"蠕动泵 1 ({self.config['pumps'][0]['description']})")
        self.p1_speed_input = QLineEdit("100.0")
        self.p1_set_button = QPushButton("设置转速")
        self.p1_start_button = QPushButton("启动")
        self.p1_stop_button = QPushButton("停止")
        self.p1_status_label = QLabel("状态: 未知")
        
        # *** 新增部分开始 ***
        # 创建蠕动泵2的所有控件 (lange)
        self.p3_label = QLabel(f"蠕动泵 2 ({self.config['pumps'][1]['description']})")
        self.p3_speed_input = QLineEdit("50.0") # 给一个不同的默认值
        self.p3_set_button = QPushButton("设置转速")
        self.p3_start_button = QPushButton("启动")
        self.p3_stop_button = QPushButton("停止")
        self.p3_status_label = QLabel("状态: 未知")
        # *** 新增部分结束 ***

        # 创建柱塞泵的所有控件
        self.p2_label = QLabel(f"柱塞泵 ({self.config['pumps'][2]['description']})")
        self.p2_flow_input = QLineEdit("5.0")
        self.p2_set_button = QPushButton("设置流量")
        self.p2_start_button = QPushButton("启动")
        self.p2_stop_button = QPushButton("停止")
        self.p2_status_label = QLabel("状态: 未知")

        # 将所有控件添加到网格布局中
        grid.addWidget(self.p1_label, 0, 0); grid.addWidget(QLabel("转速(RPM):"), 0, 1); grid.addWidget(self.p1_speed_input, 0, 2); grid.addWidget(self.p1_set_button, 0, 3); grid.addWidget(self.p1_start_button, 0, 4); grid.addWidget(self.p1_stop_button, 0, 5); grid.addWidget(self.p1_status_label, 0, 6)
        
        # *** 新增部分开始 ***
        # 将蠕动泵2的控件添加到第1行
        grid.addWidget(self.p3_label, 1, 0); grid.addWidget(QLabel("转速(RPM):"), 1, 1); grid.addWidget(self.p3_speed_input, 1, 2); grid.addWidget(self.p3_set_button, 1, 3); grid.addWidget(self.p3_start_button, 1, 4); grid.addWidget(self.p3_stop_button, 1, 5); grid.addWidget(self.p3_status_label, 1, 6)
        # *** 新增部分结束 ***
        
        # 将柱塞泵的控件移动到第2行
        grid.addWidget(self.p2_label, 2, 0); grid.addWidget(QLabel("流量(ml/min):"), 2, 1); grid.addWidget(self.p2_flow_input, 2, 2); grid.addWidget(self.p2_set_button, 2, 3); grid.addWidget(self.p2_start_button, 2, 4); grid.addWidget(self.p2_stop_button, 2, 5); grid.addWidget(self.p2_status_label, 2, 6)
        
        grid.setColumnStretch(6, 1) 
        manual_group.setLayout(grid)

        # --- 2. 自动化协议区域 (保持不变) ---
        protocol_group = QGroupBox("自动化协议控制")
        # (协议区域的控件创建和布局与之前完全相同，此处省略)
        protocol_layout = QVBoxLayout()
        self.protocol_editor = QTextEdit()
        self.protocol_editor.setText(json.dumps(auto_protocol, indent=4))
        protocol_button_layout = QHBoxLayout()
        self.load_protocol_button = QPushButton("从文件加载协议...")
        self.run_protocol_button = QPushButton("执行编辑器中的协议")
        protocol_button_layout.addWidget(self.load_protocol_button)
        protocol_button_layout.addWidget(self.run_protocol_button)
        protocol_layout.addWidget(QLabel("协议编辑器 (JSON格式):"))
        protocol_layout.addWidget(self.protocol_editor)
        protocol_layout.addLayout(protocol_button_layout)
        protocol_group.setLayout(protocol_layout)

        # --- 3. 全局控制按钮 (保持不变) ---
        self.stop_all_button = QPushButton("!! 全部紧急停止 !!")
        self.stop_all_button.setStyleSheet("background-color: #d9534f; color: white;")

        # --- 4. 设置窗口主布局 (保持不变) ---
        main_layout = QVBoxLayout()
        main_layout.addWidget(manual_group)
        main_layout.addWidget(protocol_group)
        main_layout.addWidget(self.stop_all_button)
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # --- 5. 连接控件的信号到处理函数(槽) ---
        # 手动控制按钮的连接
        self.p1_start_button.clicked.connect(lambda: self.on_start('peristaltic_1'))
        self.p1_stop_button.clicked.connect(lambda: self.on_stop('peristaltic_1'))
        self.p1_set_button.clicked.connect(lambda: self.on_set_params('peristaltic_1'))
        
        # *** 新增部分开始 ***
        # 连接蠕动泵2的按钮信号
        self.p3_start_button.clicked.connect(lambda: self.on_start('peristaltic_2'))
        self.p3_stop_button.clicked.connect(lambda: self.on_stop('peristaltic_2'))
        self.p3_set_button.clicked.connect(lambda: self.on_set_params('peristaltic_2'))
        # *** 新增部分结束 ***

        self.p2_start_button.clicked.connect(lambda: self.on_start('plunger_pump'))
        self.p2_stop_button.clicked.connect(lambda: self.on_stop('plunger_pump'))
        self.p2_set_button.clicked.connect(lambda: self.on_set_params('plunger_pump'))
        
        # 全局和协议按钮的连接 (保持不变)
        self.stop_all_button.clicked.connect(self.on_stop_all)
        self.load_protocol_button.clicked.connect(self.on_load_protocol_from_file)
        self.run_protocol_button.clicked.connect(self.on_run_protocol)

    def _start_backend(self):
        # (此方法无需改动)
        self.command_queue = multiprocessing.Queue(); self.status_queue = multiprocessing.Queue()
        controller = SystemController(self.config, self.command_queue, self.status_queue)
        self.process = multiprocessing.Process(target=controller.run); self.process.start()
        self.timer = QTimer(self); self.timer.setInterval(500); self.timer.timeout.connect(self.update_status_display); self.timer.start()

    # --- 事件处理函数(槽) ---

    def on_load_protocol_from_file(self):
        # (此方法无需改动)
        file_name, _ = QFileDialog.getOpenFileName(self, "选择协议文件", "", "JSON Files (*.json);;All Files (*)")
        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as f:
                    content = f.read()
                    try: self.protocol_editor.setText(json.dumps(json.loads(content), indent=4))
                    except: self.protocol_editor.setText(content)
            except Exception as e: QMessageBox.critical(self, "文件读取错误", f"无法读取文件: {e}")

    def on_run_protocol(self):
        # (此方法无需改动)
        try:
            protocol_list = json.loads(self.protocol_editor.toPlainText())
            if not isinstance(protocol_list, list): raise ValueError("协议必须是一个列表")
            command = {'type': 'run_protocol', 'params': {'protocol': protocol_list}}
            self.command_queue.put(command)
            QMessageBox.information(self, "协议已启动", "自动化协议已发送到后台执行。")
        except Exception as e: QMessageBox.critical(self, "协议格式或内容错误", str(e))

    def on_start(self, pump_id):
        # *** 核心修改处 ***
        try:
            params = {'pump_id': pump_id}
            if pump_id == 'peristaltic_1':
                params['speed'] = float(self.p1_speed_input.text())
            elif pump_id == 'peristaltic_2': # 新增分支
                params['speed'] = float(self.p3_speed_input.text())
            elif pump_id == 'plunger_pump':
                params['flow_rate'] = float(self.p2_flow_input.text())
            
            self.command_queue.put({'type': 'start_pump', 'params': params})
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数字！")

    def on_stop(self, pump_id):
        # (此方法无需改动)
        self.command_queue.put({'type': 'stop_pump', 'params': {'pump_id': pump_id}})

    def on_set_params(self, pump_id):
        # *** 核心修改处 ***
        try:
            params = {'pump_id': pump_id}
            if pump_id == 'peristaltic_1':
                params['speed'] = float(self.p1_speed_input.text())
            elif pump_id == 'peristaltic_2': # 新增分支
                params['speed'] = float(self.p3_speed_input.text())
            elif pump_id == 'plunger_pump':
                params['flow_rate'] = float(self.p2_flow_input.text())
            
            self.command_queue.put({'type': 'set_pump_params', 'params': params})
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数字！")
    
    def on_stop_all(self):
        # (此方法无需改动)
        self.command_queue.put({'type': 'stop_all'})

    def update_status_display(self):
        # *** 核心修改处 ***
        try:
            status = None
            while not self.status_queue.empty(): status = self.status_queue.get_nowait()
            
            if status:
                if 'error' in status: QMessageBox.critical(self, "后台错误", status['error']); return
                if 'info' in status: QMessageBox.information(self, "后台通知", status['info'])
                
                # 更新蠕动泵1的状态
                p1_status = status['pumps'].get('peristaltic_1', {})
                self.p1_status_label.setText(f"状态: {'运行中' if p1_status.get('is_running') else '已停止'} | 转速: {p1_status.get('speed_rpm', 0.0):.2f}")
                
                # 新增：更新蠕动泵2的状态
                p3_status = status['pumps'].get('peristaltic_2', {})
                self.p3_status_label.setText(f"状态: {'运行中' if p3_status.get('is_running') else '已停止'} | 转速: {p3_status.get('speed_rpm', 0.0):.2f}")

                # 更新柱塞泵的状态
                p2_status = status['pumps'].get('plunger_pump', {})
                self.p2_status_label.setText(f"状态: {'运行中' if p2_status.get('is_running') else '已停止'} | 流量: {p2_status.get('flow_rate_ml_min', 0.0):.3f}")
        except Empty: pass
        except Exception as e: print(f"[{self.config['system_name']}-GUI] 更新状态时出错: {e}")

    def closeEvent(self, event):
        # (此方法无需改动)
        self.timer.stop();
        if self.process and self.process.is_alive():
            self.command_queue.put({'type': 'shutdown'}); self.process.join(timeout=5)
            if self.process.is_alive(): self.process.terminate()
        event.accept()

class MainApp(QMainWindow):
    # (此类无需改动)
    def __init__(self):
        super().__init__(); self.setWindowTitle("多系统泵控制程序"); self.setGeometry(300, 300, 300, 150); self.control_windows = {}
        layout = QVBoxLayout(); self.btn_sys_a = QPushButton("打开 系统 A 控制面板"); self.btn_sys_a.clicked.connect(lambda: self.open_control_panel('A', SYSTEM_A_CONFIG)); self.btn_sys_b = QPushButton("打开 系统 B 控制面板"); self.btn_sys_b.clicked.connect(lambda: self.open_control_panel('B', SYSTEM_B_CONFIG)); layout.addWidget(self.btn_sys_a); layout.addWidget(self.btn_sys_b)
        central_widget = QWidget(); central_widget.setLayout(layout); self.setCentralWidget(central_widget)
    def open_control_panel(self, system_id, config):
        if system_id in self.control_windows and self.control_windows[system_id].isVisible(): self.control_windows[system_id].activateWindow()
        else: self.control_windows[system_id] = ControlPanel(config); self.control_windows[system_id].show()

# --- 程序主入口 ---
if __name__ == '__main__':
    # (此部分无需改动)
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    main_window = MainApp()
    main_window.show()
    sys.exit(app.exec())