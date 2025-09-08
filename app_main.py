# file: app_main.py (最终修正版 - 图形化协议编辑器)

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
                             QMessageBox, QTextEdit, # <--- 在这里添加 QTextEdit
                             QGroupBox, QFileDialog, QSplitter,
                             QListWidget, QListWidgetItem, QDialog, QFormLayout,
                             QComboBox, QDoubleSpinBox, QDialogButtonBox)
from PyQt6.QtCore import QTimer, Qt

from system_controller import SystemController
from system_config import SYSTEM_A_CONFIG, SYSTEM_B_CONFIG
try:
    from protocol import auto_protocol
except ImportError:
    auto_protocol = [{"command": "delay", "duration": 1}]

# --- 自定义参数对话框 ---
class AddStepDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent); self.config = config; self.setWindowTitle("添加协议步骤")
        self.form_layout = QFormLayout()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        main_layout = QVBoxLayout(); main_layout.addLayout(self.form_layout); main_layout.addWidget(self.buttons); self.setLayout(main_layout)

class PumpActionDialog(AddStepDialog):
    def __init__(self, config, parent=None, show_params=True):
        super().__init__(config, parent)
        self.pump_select = QComboBox()
        self.pump_ids = [p['id'] for p in self.config.get('pumps', [])]
        self.pump_select.addItems(self.pump_ids)
        self.form_layout.addRow("选择泵:", self.pump_select)
        
        self.speed_input = QDoubleSpinBox(); self.speed_input.setRange(0, 1000); self.speed_input.setValue(100.0)
        self.flow_input = QDoubleSpinBox(); self.flow_input.setRange(0, 100); self.flow_input.setValue(5.0)
        
        if show_params:
            self.form_layout.addRow("转速 (RPM):", self.speed_input)
            self.form_layout.addRow("流量 (ml/min):", self.flow_input)

class DelayDialog(AddStepDialog):
    def __init__(self, config, parent=None):
        super().__init__(config, parent); self.setWindowTitle("添加延时步骤")
        self.duration_input = QDoubleSpinBox(); self.duration_input.setRange(0.1, 3600); self.duration_input.setValue(5.0)
        self.form_layout.addRow("延时 (秒):", self.duration_input)
    def get_data(self):
        return {'command': 'delay', 'duration': self.duration_input.value()}

# --- 主控制面板 ---
class ControlPanel(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowTitle(f"{config['system_name']} 控制面板")
        self.setGeometry(100, 100, 950, 800)

        self.device_descriptions = {dev['id']: dev['description'] 
                                    for dev_list in config.values() if isinstance(dev_list, list) 
                                    for dev in dev_list if isinstance(dev, dict) and 'id' in dev}

        self.process = None; self.command_queue = None; self.status_queue = None; self.log_queue = None
        
        self.start_time = time.time()
        self.data = {'time': []}
        for pump in self.config.get('pumps', []):
            self.data[f"{pump['id']}_speed"] = []; self.data[f"{pump['id']}_flow"] = []
        for ps in self.config.get('power_supplies', []):
            for i in range(1, 5):
                 self.data[f"{ps['id']}_ch{i}_voltage"] = []; self.data[f"{ps['id']}_ch{i}_current"] = []

        self._init_ui()
        self._start_backend()

    def _init_ui(self):
        # --- 1. 创建所有UI区域 ---
        manual_group = self._create_manual_group()
        protocol_group = self._create_protocol_group()
        plot_group = self._create_plot_group()
        log_group = self._create_log_group()

        # --- 2. 使用可拖拽的分隔栏进行主布局 ---
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(manual_group)
        top_splitter.addWidget(protocol_group)
        top_splitter.setSizes([500, 450])

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(plot_group)
        main_splitter.addWidget(log_group)
        main_splitter.setSizes([200, 400, 200])

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(main_splitter)
        self.setCentralWidget(central_widget)

        # --- 3. 连接所有信号与槽 ---
        self._connect_signals()

    def _create_manual_group(self):
        manual_group = QGroupBox("手动独立控制")
        grid = QGridLayout()
        self.device_widgets = {}
        row = 0
        for pump_conf in self.config.get('pumps', []):
            p_id = pump_conf['id']
            is_peristaltic = 'peristaltic' in p_id
            self.device_widgets[p_id] = {'input': QLineEdit("100.0" if is_peristaltic else "5.0"),'set_btn': QPushButton("设置"),'start_btn': QPushButton("启动"),'stop_btn': QPushButton("停止"),'status': QLabel("状态: 未知")}
            grid.addWidget(QLabel(f"泵: {pump_conf['description']}"), row, 0)
            grid.addWidget(QLabel("转速(RPM):" if is_peristaltic else "流量(ml/min):"), row, 1)
            grid.addWidget(self.device_widgets[p_id]['input'], row, 2); grid.addWidget(self.device_widgets[p_id]['set_btn'], row, 3); grid.addWidget(self.device_widgets[p_id]['start_btn'], row, 4); grid.addWidget(self.device_widgets[p_id]['stop_btn'], row, 5); grid.addWidget(self.device_widgets[p_id]['status'], row, 6)
            row += 1
        for ps_conf in self.config.get('power_supplies', []):
            ps_id = ps_conf['id']
            self.device_widgets[ps_id] = {'v_input': QLineEdit("5.0"),'i_input': QLineEdit("1.0"),'set_btn': QPushButton("设置CH1"),'out_btn': QPushButton("打开总输出"),'status': QLabel("状态: 未知")}
            ps_layout = QHBoxLayout(); ps_layout.addWidget(QLabel("CH1 V:")); ps_layout.addWidget(self.device_widgets[ps_id]['v_input']); ps_layout.addWidget(QLabel("CH1 A:")); ps_layout.addWidget(self.device_widgets[ps_id]['i_input'])
            grid.addWidget(QLabel(f"电源: {ps_conf['description']}"), row, 0); grid.addLayout(ps_layout, row, 1, 1, 2); grid.addWidget(self.device_widgets[ps_id]['set_btn'], row, 3); grid.addWidget(self.device_widgets[ps_id]['out_btn'], row, 4, 1, 2); grid.addWidget(self.device_widgets[ps_id]['status'], row, 6)
            row += 1
        grid.setColumnStretch(6, 1)
        manual_group.setLayout(grid)
        return manual_group

    def _create_protocol_group(self):
        protocol_group = QGroupBox("自动化协议编辑器")
        layout = QHBoxLayout()
        toolbox = QVBoxLayout(); toolbox.addWidget(QLabel("1. 添加步骤:")); self.add_start_pump_btn = QPushButton("启动/设置 泵"); self.add_stop_pump_btn = QPushButton("停止 泵"); self.add_delay_btn = QPushButton("延时"); toolbox.addWidget(self.add_start_pump_btn); toolbox.addWidget(self.add_stop_pump_btn); toolbox.addWidget(self.add_delay_btn); toolbox.addStretch()
        sequence = QVBoxLayout(); sequence.addWidget(QLabel("2. 编辑流程:")); self.protocol_list_widget = QListWidget()
        edit_buttons = QHBoxLayout(); self.remove_step_btn = QPushButton("删除"); self.move_up_btn = QPushButton("上移"); self.move_down_btn = QPushButton("下移"); edit_buttons.addWidget(self.remove_step_btn); edit_buttons.addStretch(); edit_buttons.addWidget(self.move_up_btn); edit_buttons.addWidget(self.move_down_btn)
        sequence.addWidget(self.protocol_list_widget); sequence.addLayout(edit_buttons)
        action_buttons = QVBoxLayout(); action_buttons.addWidget(QLabel("3. 执行与保存:")); self.run_protocol_button = QPushButton("执行协议"); self.load_protocol_button = QPushButton("从文件加载..."); self.save_protocol_button = QPushButton("保存到文件..."); self.stop_all_button = QPushButton("!! 全部紧急停止 !!"); self.stop_all_button.setStyleSheet("background-color: #d9534f; color: white;")
        action_buttons.addWidget(self.run_protocol_button); action_buttons.addWidget(self.load_protocol_button); action_buttons.addWidget(self.save_protocol_button); action_buttons.addStretch(); action_buttons.addWidget(self.stop_all_button)
        layout.addLayout(toolbox, 1); layout.addLayout(sequence, 3); layout.addLayout(action_buttons, 1)
        protocol_group.setLayout(layout)
        return protocol_group

    def _create_plot_group(self):
        plot_group = QGroupBox("实时数据图表"); self.plot_widget = pg.PlotWidget(); self.plot_widget.setBackground('w'); self.plot_widget.setLabel('left', '数值'); self.plot_widget.setLabel('bottom', '时间 (s)'); self.plot_widget.addLegend(); self.plot_widget.showGrid(x=True, y=True)
        self.curves = {'kamoer_pump_speed': self.plot_widget.plot(pen=pg.mkPen('b', width=2), name="泵1-速度"),'lange_pump_speed': self.plot_widget.plot(pen=pg.mkPen('g', width=2), name="泵2-速度"),'plunger_pump_flow': self.plot_widget.plot(pen=pg.mkPen('r', width=2), name="泵3-流量"),'gpd_power_1_ch1_voltage': self.plot_widget.plot(pen=pg.mkPen('c', width=2), name="电源-CH1电压")}
        layout = QVBoxLayout(); layout.addWidget(self.plot_widget); plot_group.setLayout(layout)
        return plot_group
    
    def _create_log_group(self):
        log_group = QGroupBox("后台日志"); self.log_display = QTextEdit(); self.log_display.setReadOnly(True)
        layout = QVBoxLayout(); layout.addWidget(self.log_display); log_group.setLayout(layout)
        return log_group

    def _connect_signals(self):
        for pump_conf in self.config.get('pumps', []):
            p_id = pump_conf['id']
            self.device_widgets[p_id]['start_btn'].clicked.connect(lambda _, p=p_id: self.on_start(p))
            self.device_widgets[p_id]['stop_btn'].clicked.connect(lambda _, p=p_id: self.on_stop(p))
            self.device_widgets[p_id]['set_btn'].clicked.connect(lambda _, p=p_id: self.on_set_params(p))
        for ps_conf in self.config.get('power_supplies', []):
            ps_id = ps_conf['id']
            self.device_widgets[ps_id]['set_btn'].clicked.connect(lambda _, p=ps_id: self.on_set_power_ch1(p))
            self.device_widgets[ps_id]['out_btn'].clicked.connect(lambda _, p=ps_id: self.on_toggle_power_output(p))
        self.add_start_pump_btn.clicked.connect(self.on_add_start_set_pump); self.add_stop_pump_btn.clicked.connect(self.on_add_stop_pump); self.add_delay_btn.clicked.connect(self.on_add_delay); self.remove_step_btn.clicked.connect(self.on_remove_step); self.move_up_btn.clicked.connect(self.on_move_up); self.move_down_btn.clicked.connect(self.on_move_down); self.run_protocol_button.clicked.connect(self.on_run_protocol); self.save_protocol_button.clicked.connect(self.on_save_protocol_to_file); self.load_protocol_button.clicked.connect(self.on_load_protocol_from_file); self.stop_all_button.clicked.connect(self.on_stop_all)
    
    # ... (所有事件处理函数和后台管理函数，与上一版本基本相同，但需要确保它们存在)
    def on_add_start_set_pump(self):
        dialog = PumpActionDialog(self.config, self)
        if dialog.exec():
            pump_id = dialog.pump_select.currentText()
            params = {}; desc_param = ""
            if 'peristaltic' in pump_id or 'lange' in pump_id: params['speed'] = dialog.speed_input.value(); desc_param = f"速度: {params['speed']}"
            else: params['flow_rate'] = dialog.flow_input.value(); desc_param = f"流量: {params['flow_rate']}"
            
            msg_box = QMessageBox(self); msg_box.setText(f"为 {pump_id} 添加什么步骤？"); start_btn = msg_box.addButton("启动泵", QMessageBox.ButtonRole.ActionRole); set_btn = msg_box.addButton("设置参数", QMessageBox.ButtonRole.ActionRole); msg_box.addButton(QMessageBox.StandardButton.Cancel); msg_box.exec()
            
            if msg_box.clickedButton() == start_btn: self._add_step_to_list({'command': 'start_pump', 'pump_id': pump_id, 'params': params})
            elif msg_box.clickedButton() == set_btn: self._add_step_to_list({'command': 'set_pump_params', 'pump_id': pump_id, 'params': params})

    def on_add_stop_pump(self):
        dialog = PumpActionDialog(self.config, self, show_params=False)
        if dialog.exec(): self._add_step_to_list({'command': 'stop_pump', 'pump_id': dialog.pump_select.currentText()})

    def on_add_delay(self):
        dialog = DelayDialog(self.config, self)
        if dialog.exec(): self._add_step_to_list(dialog.get_data())

    def _add_step_to_list(self, command_dict):
        item = QListWidgetItem(self.generate_description_from_command(command_dict))
        item.setData(Qt.ItemDataRole.UserRole, command_dict)
        self.protocol_list_widget.addItem(item)
    
    def on_remove_step(self):
        for item in self.protocol_list_widget.selectedItems(): self.protocol_list_widget.takeItem(self.protocol_list_widget.row(item))
            
    def on_move_up(self):
        row = self.protocol_list_widget.currentRow()
        if row > 0: item = self.protocol_list_widget.takeItem(row); self.protocol_list_widget.insertItem(row - 1, item); self.protocol_list_widget.setCurrentRow(row - 1)

    def on_move_down(self):
        row = self.protocol_list_widget.currentRow()
        if row < self.protocol_list_widget.count() - 1: item = self.protocol_list_widget.takeItem(row); self.protocol_list_widget.insertItem(row + 1, item); self.protocol_list_widget.setCurrentRow(row + 1)
            
    def on_run_protocol(self):
        if self.protocol_list_widget.count() == 0: return
        protocol_list = [self.protocol_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.protocol_list_widget.count())]
        self.command_queue.put({'type': 'run_protocol', 'params': {'protocol': protocol_list}}); QMessageBox.information(self, "协议已启动", "自动化协议已发送到后台执行。")

    def on_save_protocol_to_file(self):
        protocol_list = [self.protocol_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.protocol_list_widget.count())]
        if not protocol_list: return
        filename, _ = QFileDialog.getSaveFileName(self, "保存协议文件", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f: json.dump(protocol_list, f, indent=4)
                QMessageBox.information(self, "成功", "协议已保存。")
            except Exception as e: QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def on_load_protocol_from_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "加载协议文件", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f: protocol_list = json.load(f)
                self.protocol_list_widget.clear()
                for step in protocol_list: self._add_step_to_list(step)
                QMessageBox.information(self, "成功", "协议已加载。")
            except Exception as e: QMessageBox.critical(self, "错误", f"加载或解析文件失败: {e}")

    def generate_description_from_command(self, command):
        cmd_type = command.get('command'); desc = f"未知指令: {cmd_type}"
        pump_id = command.get('pump_id'); device_id = command.get('device_id'); target_id = pump_id or device_id
        target_desc = self.device_descriptions.get(target_id, target_id)
        if cmd_type in ['start_pump', 'set_pump_params']:
            action = "启动" if cmd_type == 'start_pump' else "设置"; params = command.get('params', {}); param_str = ", ".join([f"{k}: {v}" for k, v in params.items()]); desc = f"{action}泵: {target_desc}, 参数: {param_str}"
        elif cmd_type == 'stop_pump': desc = f"停止泵: {target_desc}"
        elif cmd_type == 'delay': desc = f"延时: {command.get('duration', 0)} 秒"
        elif cmd_type in ['set_power_voltage', 'set_power_current']:
            action = "电压" if 'voltage' in cmd_type else "电流"; unit = "V" if action == "电压" else "A"; value = command.get('params', {}).get(action.lower(), 0); channel = command.get('params', {}).get('channel', 0); desc = f"设置电源 {action}: {target_desc}, CH{channel}, {value}{unit}"
        elif cmd_type == 'set_power_output': state = "打开" if command.get('params', {}).get('enable') else "关闭"; desc = f"{state}电源总输出: {target_desc}"
        elif cmd_type == 'stop_all': desc = "全部紧急停止"
        return desc

    def _start_backend(self):
        self.command_queue = multiprocessing.Queue(); self.status_queue = multiprocessing.Queue(); self.log_queue = multiprocessing.Queue()
        controller = SystemController(self.config, self.command_queue, self.status_queue, self.log_queue)
        self.process = multiprocessing.Process(target=controller.run); self.process.start()
        self.timer = QTimer(self); self.timer.setInterval(500); self.timer.timeout.connect(self.update_ui); self.timer.start()

    def update_ui(self):
        try:
            while not self.log_queue.empty():
                message = self.log_queue.get_nowait()
                if message == "STOP": self.log_display.append("<font color='red'>--- 后台进程已停止 ---</font>"); self.timer.stop(); break
                self.log_display.append(message); self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())
        except Empty: pass
        try:
            status = None
            while not self.status_queue.empty(): status = self.status_queue.get_nowait()
            if status:
                if 'error' in status: QMessageBox.critical(self, "后台错误", status['error']); return
                if 'info' in status: QMessageBox.information(self, "后台通知", status['info'])
                elapsed_time = time.time() - self.start_time; self.data['time'].append(elapsed_time)
                for p_conf in self.config.get('pumps', []):
                    p_id = p_conf['id']; p_status = status['pumps'].get(p_id, {}); self.device_widgets[p_id]['status'].setText(f"状态: {'运行中' if p_status.get('is_running') else '已停止'} | 值: {p_status.get('speed_rpm', p_status.get('flow_rate_ml_min', 0.0)):.2f}"); self.data[f"{p_id}_speed"].append(p_status.get('speed_rpm', 0.0)); self.data[f"{p_id}_flow"].append(p_status.get('flow_rate_ml_min', 0.0))
                for ps_conf in self.config.get('power_supplies', []):
                    ps_id = ps_conf['id']; ps_status = status['power_supplies'].get(ps_id, {})
                    if ps_status:
                        output_on = ps_status.get('output_on', False); ch1_v = ps_status.get('ch1_voltage', 0.0); ch1_i = ps_status.get('ch1_current', 0.0)
                        self.device_widgets[ps_id]['out_btn'].setText("关闭总输出" if output_on else "打开总输出"); self.device_widgets[ps_id]['out_btn'].setStyleSheet("background-color: #5cb85c;" if output_on else ""); self.device_widgets[ps_id]['status'].setText(f"总输出: {'ON' if output_on else 'OFF'} | CH1: {ch1_v:.3f}V / {ch1_i:.3f}A")
                        self.data[f"{ps_id}_ch1_voltage"].append(ch1_v); self.data[f"{ps_id}_ch1_current"].append(ch1_i)
                self.curves['kamoer_pump_speed'].setData(self.data['time'], self.data['kamoer_pump_speed'])
                self.curves['lange_pump_speed'].setData(self.data['time'], self.data['lange_pump_speed'])
                self.curves['plunger_pump_flow'].setData(self.data['time'], self.data['plunger_pump_flow'])
                self.curves['gpd_power_1_ch1_voltage'].setData(self.data['time'], self.data['gpd_power_1_ch1_voltage'])
        except Empty: pass
        except Exception as e: print(f"[{self.config['system_name']}-GUI] 更新UI时出错: {e}")

    # --- Other slots ---
    def on_save_data(self):
        filename, _ = QFileDialog.getSaveFileName(self, "保存数据", "", "CSV Files (*.csv)"); 
        if filename:
            try: pd.DataFrame(self.data).to_csv(filename, index=False); QMessageBox.information(self, "成功", f"数据已保存到 {filename}")
            except Exception as e: QMessageBox.critical(self, "错误", f"保存数据失败: {e}")
    def on_save_chart(self):
        filename, _ = QFileDialog.getSaveFileName(self, "保存图表", "", "PNG Files (*.png);;JPG Files (*.jpg)"); 
        if filename:
            try: ImageExporter(self.plot_widget.plotItem).export(filename); QMessageBox.information(self, "成功", f"图表已保存到 {filename}")
            except Exception as e: QMessageBox.critical(self, "错误", f"保存图表失败: {e}")
    def on_start(self, pump_id):
        try:
            params = {'pump_id': pump_id}; widget_set = self.device_widgets[pump_id]
            if 'peristaltic' in pump_id: params['speed'] = float(widget_set['input'].text())
            elif 'plunger' in pump_id: params['flow_rate'] = float(widget_set['input'].text())
            self.command_queue.put({'type': 'start_pump', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的数字！")
    def on_stop(self, pump_id): self.command_queue.put({'type': 'stop_pump', 'params': {'pump_id': pump_id}})
    def on_set_params(self, pump_id):
        try:
            params = {'pump_id': pump_id}; widget_set = self.device_widgets[pump_id]
            if 'peristaltic' in pump_id: params['speed'] = float(widget_set['input'].text())
            elif 'plunger' in pump_id: params['flow_rate'] = float(widget_set['input'].text())
            self.command_queue.put({'type': 'set_pump_params', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的数字！")
    def on_stop_all(self): self.command_queue.put({'type': 'stop_all'})
    def on_set_power_ch1(self, ps_id):
        try:
            widget_set = self.device_widgets[ps_id]; voltage = float(widget_set['v_input'].text()); current = float(widget_set['i_input'].text())
            self.command_queue.put({'type': 'set_power_voltage','params': {'device_id': ps_id, 'channel': 1, 'voltage': voltage}})
            self.command_queue.put({'type': 'set_power_current','params': {'device_id': ps_id, 'channel': 1, 'current': current}})
        except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的电压和电流值！")
    def on_toggle_power_output(self, ps_id):
        widget_set = self.device_widgets[ps_id]; enable = widget_set['out_btn'].text() == "打开总输出"
        self.command_queue.put({'type': 'set_power_output','params': {'device_id': ps_id, 'enable': enable}})

    def closeEvent(self, event):
        self.timer.stop()
        if self.process and self.process.is_alive():
            self.command_queue.put({'type': 'shutdown'}); self.process.join(timeout=5)
            if self.process.is_alive(): self.process.terminate()
        event.accept()

# --- MainApp and Entry Point (unchanged) ---
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