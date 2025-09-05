# file: app_main.py (日志、绘图、保存、电源UI最终版)

import sys
import multiprocessing
import json
import time
from queue import Empty
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, QGridLayout,
                             QMessageBox, QTextEdit, QGroupBox, QFileDialog, QSplitter)
from PyQt6.QtCore import QTimer, Qt

from system_controller import SystemController
from system_config import SYSTEM_A_CONFIG, SYSTEM_B_CONFIG
# 确保你有一个 protocol.py 文件，或者直接在这里定义一个示例
try:
    from protocol import auto_protocol
except ImportError:
    auto_protocol = [{"command": "delay", "duration": 1}]

class ControlPanel(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowTitle(f"{config['system_name']} 控制面板")
        self.setGeometry(100, 100, 900, 700)

        self.process = None
        self.command_queue = None
        self.status_queue = None
        self.log_queue = None
        
        self.start_time = time.time()
        # 初始化数据存储结构
        self.data = {'time': []}
        for pump in self.config.get('pumps', []):
            self.data[f"{pump['id']}_speed"] = []
            self.data[f"{pump['id']}_flow"] = []
        for ps in self.config.get('power_supplies', []):
            for i in range(1, 5): # 假设最多4通道
                 self.data[f"{ps['id']}_ch{i}_voltage"] = []
                 self.data[f"{ps['id']}_ch{i}_current"] = []

        self._init_ui()
        self._start_backend()

    def _init_ui(self):
        """重新布局UI以容纳日志和绘图。"""
        # --- 创建控件 ---
        # 手动控制区域
        manual_group = QGroupBox("手动独立控制")
        manual_layout = QGridLayout()
        
        # 动态创建设备UI
        self.device_widgets = {}
        row = 0
        for pump_conf in self.config.get('pumps', []):
            p_id = pump_conf['id']
            self.device_widgets[p_id] = {
                'label': QLabel(f"泵: {pump_conf['description']}"),
                'input': QLineEdit("100.0" if 'peristaltic' in p_id else "5.0"),
                'set_btn': QPushButton("设置"),
                'start_btn': QPushButton("启动"),
                'stop_btn': QPushButton("停止"),
                'status': QLabel("状态: 未知")
            }
            manual_layout.addWidget(self.device_widgets[p_id]['label'], row, 0)
            manual_layout.addWidget(QLabel("转速/流量:"), row, 1)
            manual_layout.addWidget(self.device_widgets[p_id]['input'], row, 2)
            manual_layout.addWidget(self.device_widgets[p_id]['set_btn'], row, 3)
            manual_layout.addWidget(self.device_widgets[p_id]['start_btn'], row, 4)
            manual_layout.addWidget(self.device_widgets[p_id]['stop_btn'], row, 5)
            manual_layout.addWidget(self.device_widgets[p_id]['status'], row, 6)
            row += 1

        for ps_conf in self.config.get('power_supplies', []):
            ps_id = ps_conf['id']
            self.device_widgets[ps_id] = {
                'label': QLabel(f"电源: {ps_conf['description']}"),
                'v_input': QLineEdit("5.0"),
                'i_input': QLineEdit("1.0"),
                'set_btn': QPushButton("设置CH1"),
                'out_btn': QPushButton("打开总输出"),
                'status': QLabel("状态: 未知")
            }
            ps_ch1_layout = QHBoxLayout()
            ps_ch1_layout.addWidget(QLabel("CH1 V:")); ps_ch1_layout.addWidget(self.device_widgets[ps_id]['v_input'])
            ps_ch1_layout.addWidget(QLabel("CH1 A:")); ps_ch1_layout.addWidget(self.device_widgets[ps_id]['i_input'])
            manual_layout.addWidget(self.device_widgets[ps_id]['label'], row, 0)
            manual_layout.addLayout(ps_ch1_layout, row, 1, 1, 2)
            manual_layout.addWidget(self.device_widgets[ps_id]['set_btn'], row, 3)
            manual_layout.addWidget(self.device_widgets[ps_id]['out_btn'], row, 4)
            manual_layout.addWidget(self.device_widgets[ps_id]['status'], row, 6)
            row += 1

        manual_layout.setColumnStretch(6, 1)
        manual_group.setLayout(manual_layout)

        # 协议区域
        protocol_group = QGroupBox("自动化协议控制")
        protocol_layout = QHBoxLayout()
        self.protocol_editor = QTextEdit(); self.protocol_editor.setText(json.dumps(auto_protocol, indent=4))
        protocol_buttons_layout = QVBoxLayout()
        self.load_protocol_button = QPushButton("从文件加载..."); self.run_protocol_button = QPushButton("执行协议")
        self.save_data_button = QPushButton("保存数据 (CSV)"); self.save_chart_button = QPushButton("保存图表 (PNG)")
        self.stop_all_button = QPushButton("!! 全部紧急停止 !!")
        self.stop_all_button.setStyleSheet("background-color: #d9534f; color: white;")
        protocol_buttons_layout.addWidget(self.load_protocol_button); protocol_buttons_layout.addWidget(self.run_protocol_button)
        protocol_buttons_layout.addStretch(); protocol_buttons_layout.addWidget(self.save_data_button); protocol_buttons_layout.addWidget(self.save_chart_button); protocol_buttons_layout.addStretch(); protocol_buttons_layout.addWidget(self.stop_all_button)
        protocol_layout.addWidget(self.protocol_editor); protocol_layout.addLayout(protocol_buttons_layout)
        protocol_group.setLayout(protocol_layout)

        # 绘图区域
        plot_group = QGroupBox("实时数据图表")
        self.plot_widget = pg.PlotWidget(); self.plot_widget.setBackground('w'); self.plot_widget.setLabel('left', '数值'); self.plot_widget.setLabel('bottom', '时间 (s)'); self.plot_widget.addLegend(); self.plot_widget.showGrid(x=True, y=True)
        self.curves = {}
        self.curves['p1_speed'] = self.plot_widget.plot(pen=pg.mkPen('b', width=2), name="泵1-速度")
        self.curves['p2_speed'] = self.plot_widget.plot(pen=pg.mkPen('g', width=2), name="泵2-速度")
        self.curves['p3_flow'] = self.plot_widget.plot(pen=pg.mkPen('r', width=2), name="泵3-流量")
        self.curves['ps1_volt'] = self.plot_widget.plot(pen=pg.mkPen('c', width=2), name="电源-电压")
        plot_layout = QVBoxLayout(); plot_layout.addWidget(self.plot_widget)
        plot_group.setLayout(plot_layout)

        # 日志区域
        log_group = QGroupBox("后台日志")
        self.log_display = QTextEdit(); self.log_display.setReadOnly(True)
        log_layout = QVBoxLayout(); log_layout.addWidget(self.log_display)
        log_group.setLayout(log_layout)

        # --- 主布局 ---
        top_splitter = QSplitter(Qt.Orientation.Horizontal); top_splitter.addWidget(manual_group); top_splitter.addWidget(protocol_group)
        main_splitter = QSplitter(Qt.Orientation.Vertical); main_splitter.addWidget(top_splitter); main_splitter.addWidget(plot_group); main_splitter.addWidget(log_group); main_splitter.setSizes([150, 400, 150])
        central_widget = QWidget(); layout = QVBoxLayout(central_widget); layout.addWidget(main_splitter)
        self.setCentralWidget(central_widget)

        # --- 连接信号与槽 ---
        for pump_conf in self.config.get('pumps', []):
            p_id = pump_conf['id']
            self.device_widgets[p_id]['start_btn'].clicked.connect(lambda _, p=p_id: self.on_start(p))
            self.device_widgets[p_id]['stop_btn'].clicked.connect(lambda _, p=p_id: self.on_stop(p))
            self.device_widgets[p_id]['set_btn'].clicked.connect(lambda _, p=p_id: self.on_set_params(p))
        
        for ps_conf in self.config.get('power_supplies', []):
            ps_id = ps_conf['id']
            self.device_widgets[ps_id]['set_btn'].clicked.connect(self.on_set_power_ch1)
            self.device_widgets[ps_id]['out_btn'].clicked.connect(self.on_toggle_power_output)

        self.stop_all_button.clicked.connect(self.on_stop_all)
        self.load_protocol_button.clicked.connect(self.on_load_protocol_from_file)
        self.run_protocol_button.clicked.connect(self.on_run_protocol)
        self.save_data_button.clicked.connect(self.on_save_data)
        self.save_chart_button.clicked.connect(self.on_save_chart)

    def _start_backend(self):
        """启动后台进程，并传入所有三个队列。"""
        self.command_queue = multiprocessing.Queue()
        self.status_queue = multiprocessing.Queue()
        self.log_queue = multiprocessing.Queue()
        
        controller = SystemController(self.config, self.command_queue, self.status_queue, self.log_queue)
        self.process = multiprocessing.Process(target=controller.run)
        self.process.start()

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start()
        
    def update_ui(self):
        """由定时器定期调用，更新所有UI元素。"""
        # 1. 更新日志
        try:
            while not self.log_queue.empty():
                message = self.log_queue.get_nowait()
                if message == "STOP":
                    self.log_display.append("<font color='red'>--- 后台进程已停止 ---</font>")
                    self.timer.stop(); break
                self.log_display.append(message)
                self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())
        except Empty: pass

        # 2. 更新状态和图表
        try:
            status = None
            while not self.status_queue.empty(): status = self.status_queue.get_nowait()
            if status:
                if 'error' in status: QMessageBox.critical(self, "后台错误", status['error']); return
                if 'info' in status: QMessageBox.information(self, "后台通知", status['info'])
                
                elapsed_time = time.time() - self.start_time
                self.data['time'].append(elapsed_time)

                # 更新泵
                for pump_conf in self.config.get('pumps', []):
                    p_id = pump_conf['id']
                    p_status = status['pumps'].get(p_id, {})
                    self.device_widgets[p_id]['status'].setText(f"状态: {'运行中' if p_status.get('is_running') else '已停止'} | 值: {p_status.get('speed_rpm', p_status.get('flow_rate_ml_min', 0.0)):.2f}")
                    self.data[f"{p_id}_speed"].append(p_status.get('speed_rpm', 0.0))
                    self.data[f"{p_id}_flow"].append(p_status.get('flow_rate_ml_min', 0.0))

                # 更新电源
                for ps_conf in self.config.get('power_supplies', []):
                    ps_id = ps_conf['id']
                    ps_status = status['power_supplies'].get(ps_id, {})
                    if ps_status:
                        output_on = ps_status.get('output_on', False)
                        ch1_v = ps_status.get('ch1_voltage', 0.0)
                        ch1_i = ps_status.get('ch1_current', 0.0)
                        self.device_widgets[ps_id]['out_btn'].setText("关闭总输出" if output_on else "打开总输出")
                        self.device_widgets[ps_id]['out_btn'].setStyleSheet("background-color: #5cb85c; color: white;" if output_on else "")
                        self.device_widgets[ps_id]['status'].setText(f"总输出: {'ON' if output_on else 'OFF'} | CH1: {ch1_v:.3f}V / {ch1_i:.3f}A")
                        self.data[f"{ps_id}_ch1_voltage"].append(ch1_v)
                        self.data[f"{ps_id}_ch1_current"].append(ch1_i)

                # 更新图表
                self.curves['p1_speed'].setData(self.data['time'], self.data['peristaltic_1_speed'])
                self.curves['p2_speed'].setData(self.data['time'], self.data['peristaltic_2_speed'])
                self.curves['p3_flow'].setData(self.data['time'], self.data['plunger_pump_flow'])
                self.curves['ps1_volt'].setData(self.data['time'], self.data['gpd_power_1_ch1_voltage'])

        except Empty: pass
        except Exception as e: print(f"[{self.config['system_name']}-GUI] 更新UI时出错: {e}")

    # --- 其他槽函数 ---
    def on_save_data(self):
        filename, _ = QFileDialog.getSaveFileName(self, "保存数据", "", "CSV Files (*.csv)")
        if filename:
            try: pd.DataFrame(self.data).to_csv(filename, index=False); QMessageBox.information(self, "成功", f"数据已保存到 {filename}")
            except Exception as e: QMessageBox.critical(self, "错误", f"保存数据失败: {e}")

    def on_save_chart(self):
        filename, _ = QFileDialog.getSaveFileName(self, "保存图表", "", "PNG Files (*.png);;JPG Files (*.jpg)")
        if filename:
            try: ImageExporter(self.plot_widget.plotItem).export(filename); QMessageBox.information(self, "成功", f"图表已保存到 {filename}")
            except Exception as e: QMessageBox.critical(self, "错误", f"保存图表失败: {e}")
            
    # ... (其他槽函数 on_start, on_stop 等保持不变) ...
    def on_load_protocol_from_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "选择协议文件", "", "JSON Files (*.json);;All Files (*)")
        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as f:
                    content = f.read()
                    try: self.protocol_editor.setText(json.dumps(json.loads(content), indent=4))
                    except: self.protocol_editor.setText(content)
            except Exception as e: QMessageBox.critical(self, "文件读取错误", f"无法读取文件: {e}")

    def on_run_protocol(self):
        try:
            protocol_list = json.loads(self.protocol_editor.toPlainText())
            if not isinstance(protocol_list, list): raise ValueError("协议必须是一个列表")
            command = {'type': 'run_protocol', 'params': {'protocol': protocol_list}}
            self.command_queue.put(command)
            QMessageBox.information(self, "协议已启动", "自动化协议已发送到后台执行。")
        except Exception as e: QMessageBox.critical(self, "协议格式或内容错误", str(e))

    def on_start(self, pump_id):
        try:
            params = {'pump_id': pump_id}
            widget_set = self.device_widgets[pump_id]
            if 'speed' in pump_id: params['speed'] = float(widget_set['input'].text())
            elif 'plunger' in pump_id: params['flow_rate'] = float(widget_set['input'].text())
            self.command_queue.put({'type': 'start_pump', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的数字！")

    def on_stop(self, pump_id): self.command_queue.put({'type': 'stop_pump', 'params': {'pump_id': pump_id}})

    def on_set_params(self, pump_id):
        try:
            params = {'pump_id': pump_id}
            widget_set = self.device_widgets[pump_id]
            if 'speed' in pump_id: params['speed'] = float(widget_set['input'].text())
            elif 'plunger' in pump_id: params['flow_rate'] = float(widget_set['input'].text())
            self.command_queue.put({'type': 'set_pump_params', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的数字！")
    
    def on_stop_all(self): self.command_queue.put({'type': 'stop_all'})

    def on_set_power_ch1(self):
        try:
            ps_id = self.config['power_supplies'][0]['id']
            widget_set = self.device_widgets[ps_id]
            voltage = float(widget_set['v_input'].text())
            current = float(widget_set['i_input'].text())
            self.command_queue.put({'type': 'set_power_voltage','params': {'device_id': ps_id, 'channel': 1, 'voltage': voltage}})
            self.command_queue.put({'type': 'set_power_current','params': {'device_id': ps_id, 'channel': 1, 'current': current}})
        except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的电压和电流值！")

    def on_toggle_power_output(self):
        ps_id = self.config['power_supplies'][0]['id']
        widget_set = self.device_widgets[ps_id]
        enable = widget_set['out_btn'].text() == "打开总输出"
        self.command_queue.put({'type': 'set_power_output','params': {'device_id': ps_id, 'enable': enable}})

    def closeEvent(self, event):
        self.timer.stop()
        if self.process and self.process.is_alive():
            self.command_queue.put({'type': 'shutdown'}); self.process.join(timeout=5)
            if self.process.is_alive(): self.process.terminate()
        event.accept()

# --- MainApp 和主程序入口 (保持不变) ---
class MainApp(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("多系统泵控制程序"); self.setGeometry(300, 300, 300, 150); self.control_windows = {}
        layout = QVBoxLayout(); self.btn_sys_a = QPushButton("打开 系统 A 控制面板"); self.btn_sys_a.clicked.connect(lambda: self.open_control_panel('A', SYSTEM_A_CONFIG)); self.btn_sys_b = QPushButton("打开 系统 B 控制面板"); self.btn_sys_b.clicked.connect(lambda: self.open_control_panel('B', SYSTEM_B_CONFIG)); layout.addWidget(self.btn_sys_a); layout.addWidget(self.btn_sys_b)
        central_widget = QWidget(); central_widget.setLayout(layout); self.setCentralWidget(central_widget)
    def open_control_panel(self, system_id, config):
        if system_id in self.control_windows and self.control_windows[system_id].isVisible(): self.control_windows[system_id].activateWindow()
        else: self.control_windows[system_id] = ControlPanel(config); self.control_windows[system_id].show()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    main_window = MainApp()
    main_window.show()
    sys.exit(app.exec())