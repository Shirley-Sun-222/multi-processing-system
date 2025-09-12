# file: app_main.py (V2.6 - 添加图表保存功能并修复协议bug)

import sys
import multiprocessing
import time
import json
from queue import Empty
import pandas as pd
from datetime import datetime

# 导入所有必要的第三方库
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter # 导入图片导出器
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, QGridLayout,
                             QMessageBox, QDialog, QFormLayout, QListWidget, QListWidgetItem,
                             QGroupBox, QFileDialog, QSplitter, QComboBox, QDialogButtonBox,
                             QAbstractItemView)
from PyQt6.QtCore import QTimer, Qt

# 导入我们自己编写的模块
from system_controller import SystemController
from system_config import SYSTEM_SETS

# --- 对话框 (无变化) ---
class PumpActionDialog(QDialog):
    def __init__(self, pump_configs, parent=None, show_params=True):
        super().__init__(parent); self.setWindowTitle("设置泵参数"); layout = QFormLayout(self); self.pump_select = QComboBox(); self.pump_select.addItems([f"{p['description']} ({p['id']})" for p in pump_configs])
        for i, p in enumerate(pump_configs): self.pump_select.setItemData(i, p)
        layout.addRow("选择泵:", self.pump_select); self.speed_input = QLineEdit("100.0"); self.flow_input = QLineEdit("5.0")
        if show_params: layout.addRow("转速 (RPM):", self.speed_input); layout.addRow("流量 (ml/min):", self.flow_input)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject); layout.addRow(self.buttons)
    def get_selected_params(self):
        selected_pump_config = self.pump_select.currentData(); pump_id = selected_pump_config['id']; params = {}
        if 'kamoer' in selected_pump_config.get('type',''): params['speed'] = float(self.speed_input.text())
        else: params['flow_rate'] = float(self.flow_input.text())
        return pump_id, params
class DelayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("添加延时步骤"); layout = QFormLayout(self); self.duration_input = QLineEdit("5.0"); layout.addRow("延时 (秒):", self.duration_input); self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject); layout.addRow(self.buttons)
class DebugDeviceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("选择调试设备"); self.resource_manager = app.launcher.resource_manager; self.all_devices = self.resource_manager.all_devices; self.selected_config = None; layout = QVBoxLayout(self); form_layout = QFormLayout(); self.type_combo = QComboBox(); self.type_combo.addItems(["电源", "蠕动泵", "柱塞泵"]); form_layout.addRow("设备类型:", self.type_combo); self.device_list = QListWidget(); self.device_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); form_layout.addRow("可用设备:", self.device_list); layout.addLayout(form_layout); self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject); layout.addWidget(self.buttons); self.type_combo.currentTextChanged.connect(self.populate_list); self.populate_list(self.type_combo.currentText())
    def populate_list(self, type_str):
        self.device_list.clear(); type_map = {"电源": "gpd_4303s", "蠕动泵": "kamoer", "柱塞泵": "oushisheng"}; target_type = type_map.get(type_str); available_devices = self.resource_manager.get_available_devices_by_type(target_type)
        if not available_devices: self.device_list.addItem("（当前无可用设备）"); self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            for config in available_devices: item_text = f"{config['description']} (Port: {config.get('port', 'N/A')})"; item = QListWidgetItem(item_text); item.setData(Qt.ItemDataRole.UserRole, config); self.device_list.addItem(item)
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
    def accept(self):
        selected_items = self.device_list.selectedItems()
        if selected_items: self.selected_config = selected_items[0].data(Qt.ItemDataRole.UserRole)
        super().accept()

# --- 可复用的UI组件 ---
class ProtocolWidget(QWidget):
    # ... (ProtocolWidget 类代码无变化，为简洁此处省略) ...
    def __init__(self, subsystem_config, parent_window):
        super().__init__(); self.subsystem_config = subsystem_config; self.parent_window = parent_window; self._init_ui()
    def _init_ui(self):
        group = QGroupBox("自动化协议编辑器"); layout = QHBoxLayout(); toolbox = QVBoxLayout(); toolbox.addWidget(QLabel("<b>1. 添加步骤:</b>")); self.add_start_pump_btn = QPushButton("启动/设置泵"); self.add_stop_pump_btn = QPushButton("停止泵"); self.add_delay_btn = QPushButton("延时"); toolbox.addWidget(self.add_start_pump_btn); toolbox.addWidget(self.add_stop_pump_btn); toolbox.addWidget(self.add_delay_btn); toolbox.addStretch(); sequence = QVBoxLayout(); sequence.addWidget(QLabel("<b>2. 编辑流程:</b>")); self.protocol_list_widget = QListWidget(); edit_buttons = QHBoxLayout(); self.remove_step_btn = QPushButton("删除"); self.move_up_btn = QPushButton("上移"); self.move_down_btn = QPushButton("下移"); edit_buttons.addWidget(self.remove_step_btn); edit_buttons.addStretch(); edit_buttons.addWidget(self.move_up_btn); edit_buttons.addWidget(self.move_down_btn); sequence.addWidget(self.protocol_list_widget); sequence.addLayout(edit_buttons); actions = QVBoxLayout(); actions.addWidget(QLabel("<b>3. 执行与保存:</b>")); self.run_protocol_button = QPushButton("执行协议"); self.load_protocol_button = QPushButton("从文件加载..."); self.save_protocol_button = QPushButton("保存到文件..."); actions.addWidget(self.run_protocol_button); actions.addWidget(self.load_protocol_button); actions.addWidget(self.save_protocol_button); actions.addStretch(); layout.addLayout(toolbox, 1); layout.addLayout(sequence, 3); layout.addLayout(actions, 1); group.setLayout(layout); main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.addWidget(group)
    def connect_signals(self):
        self.add_start_pump_btn.clicked.connect(lambda: self.parent_window.on_add_start_set_pump(self)); self.add_stop_pump_btn.clicked.connect(lambda: self.parent_window.on_add_stop_pump(self)); self.add_delay_btn.clicked.connect(lambda: self.parent_window.on_add_delay(self)); self.remove_step_btn.clicked.connect(self.on_remove_step); self.move_up_btn.clicked.connect(self.on_move_up); self.move_down_btn.clicked.connect(self.on_move_down); self.run_protocol_button.clicked.connect(lambda: self.parent_window.on_run_protocol(self)); self.save_protocol_button.clicked.connect(lambda: self.parent_window.on_save_protocol(self)); self.load_protocol_button.clicked.connect(lambda: self.parent_window.on_load_protocol(self))
    def on_remove_step(self):
        for item in self.protocol_list_widget.selectedItems(): self.protocol_list_widget.takeItem(self.protocol_list_widget.row(item))
    def on_move_up(self):
        row = self.protocol_list_widget.currentRow();
        if row > 0: item = self.protocol_list_widget.takeItem(row); self.protocol_list_widget.insertItem(row - 1, item); self.protocol_list_widget.setCurrentRow(row - 1)
    def on_move_down(self):
        row = self.protocol_list_widget.currentRow();
        if row < self.protocol_list_widget.count() - 1: item = self.protocol_list_widget.takeItem(row); self.protocol_list_widget.insertItem(row + 1, item); self.protocol_list_widget.setCurrentRow(row + 1)

class SubsystemWidget(QWidget):
    """一个独立的子系统UI面板 (系统A或系统B)。"""
    def __init__(self, subsystem_config, parent_window):
        super().__init__(); self.config = subsystem_config; self.parent_window = parent_window; self.pump_widgets = {}; self._init_ui()
    def _init_ui(self):
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(5, 5, 5, 5); splitter = QSplitter(Qt.Orientation.Vertical); top_widget = QWidget(); top_layout = QVBoxLayout(top_widget); top_layout.setContentsMargins(0,0,0,0); pumps_group = QGroupBox("泵控制"); pumps_layout = QGridLayout(); row = 0
        for pump_conf in self.config['pumps']:
            pump_id = pump_conf['id']; is_peristaltic = 'kamoer' in pump_conf.get('type','')
            self.pump_widgets[pump_id] = {'input': QLineEdit("100.0" if is_peristaltic else "5.0"),'start_btn': QPushButton("启动"),'stop_btn': QPushButton("停止"),'status_label': QLabel("状态: 未知"),'value_label': QLabel("当前值: 0.00"),'direction_box': QComboBox()}
            self.pump_widgets[pump_id]['direction_box'].addItems(["正转", "反转"]); pumps_layout.addWidget(QLabel(f"<b>{pump_conf['description']}</b>"), row, 0, 1, 2); pumps_layout.addWidget(QLabel("方向:"), row, 2); pumps_layout.addWidget(self.pump_widgets[pump_id]['direction_box'], row, 3); param_label = "转速(RPM):" if is_peristaltic else "流量(ml/min):"; pumps_layout.addWidget(QLabel(param_label), row + 1, 0); pumps_layout.addWidget(self.pump_widgets[pump_id]['input'], row + 1, 1); pumps_layout.addWidget(self.pump_widgets[pump_id]['value_label'], row + 1, 2); pumps_layout.addWidget(self.pump_widgets[pump_id]['start_btn'], row + 1, 3); pumps_layout.addWidget(self.pump_widgets[pump_id]['stop_btn'], row + 1, 4); pumps_layout.addWidget(self.pump_widgets[pump_id]['status_label'], row + 2, 0, 1, 5); row += 3
        pumps_group.setLayout(pumps_layout); top_layout.addWidget(pumps_group)
        
        # ★★★ 核心修改 1: 在子系统UI中增加保存图表的按钮 ★★★
        chart_group = QGroupBox("实时数据")
        chart_layout = QVBoxLayout()
        self.plot_widget = pg.PlotWidget(); self.plot_widget.setBackground('w'); self.plot_widget.showGrid(x=True, y=True); self.plot_widget.addLegend()
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        self.export_data_button = QPushButton("导出Excel数据")
        self.export_chart_button = QPushButton("保存图表为PNG") # 新增按钮
        button_layout.addWidget(self.export_data_button)
        button_layout.addWidget(self.export_chart_button)

        chart_layout.addWidget(self.plot_widget)
        chart_layout.addLayout(button_layout) # 添加按钮布局
        chart_group.setLayout(chart_layout)
        
        top_layout.addWidget(chart_group, 1); splitter.addWidget(top_widget); self.protocol_widget = ProtocolWidget(self.config, self.parent_window); splitter.addWidget(self.protocol_widget); splitter.setSizes([500, 300]); main_layout.addWidget(splitter)
    def connect_signals(self):
        for pump_id, widgets in self.pump_widgets.items():
            widgets['start_btn'].clicked.connect(lambda _, p=pump_id: self.parent_window.on_start_pump(p)); widgets['stop_btn'].clicked.connect(lambda _, p=pump_id: self.parent_window.on_stop_pump(p)); widgets['input'].returnPressed.connect(lambda p=pump_id: self.parent_window.on_set_pump_params(p)); widgets['direction_box'].currentTextChanged.connect(lambda _, p=pump_id: self.parent_window.on_set_pump_params(p))
        self.protocol_widget.connect_signals()

class ControlSystemWindow(QMainWindow):
    """主控制窗口，包含左右两个子系统。"""
    def __init__(self, system_config):
        super().__init__(); self.config = system_config; self.setWindowTitle(self.config['set_description']); self.resize(1600, 900); self.device_descriptions = {dev['id']: dev['description'] for dev in [self.config['power_supply']] + self.config['subsystem_A']['pumps'] + self.config['subsystem_B']['pumps']}; self.start_time = time.time(); self.data_log_A = self._init_data_log(self.config['subsystem_A']); self.data_log_B = self._init_data_log(self.config['subsystem_B']); self.command_queue, self.status_queue, self.log_queue, self.process = None, None, None, None; self._init_ui(); self._connect_signals(); self._start_backend()
    def _init_data_log(self, subsystem_config):
        log = {'time': []}; log[f"ch{subsystem_config['channel']}_voltage"] = []; log[f"ch{subsystem_config['channel']}_current"] = [];
        for pump in subsystem_config['pumps']: log[f"{pump['id']}_speed"] = []; log[f"{pump['id']}_flow"] = []
        return log
    def _init_ui(self):
        central_widget = QWidget(); main_layout = QVBoxLayout(central_widget); shared_controls_group = self._create_shared_controls(); main_layout.addWidget(shared_controls_group); splitter = QSplitter(Qt.Orientation.Horizontal); self.subsystem_A_widget = SubsystemWidget(self.config['subsystem_A'], self); self.subsystem_B_widget = SubsystemWidget(self.config['subsystem_B'], self); splitter.addWidget(self.subsystem_A_widget); splitter.addWidget(self.subsystem_B_widget); splitter.setSizes([800, 800]); main_layout.addWidget(splitter, 1); self.setCentralWidget(central_widget)
        self._setup_plots() # 初始化图表曲线
    def _create_shared_controls(self):
        group = QGroupBox("总控制"); layout = QGridLayout(); ch1_conf = self.config['subsystem_A']; ch2_conf = self.config['subsystem_B']; self.power_widgets = {f"ch{ch1_conf['channel']}": {'volt_input': QLineEdit("5.0"), 'curr_input': QLineEdit("1.0"), 'set_btn': QPushButton(f"设置CH{ch1_conf['channel']}")}, f"ch{ch2_conf['channel']}": {'volt_input': QLineEdit("5.0"), 'curr_input': QLineEdit("1.0"), 'set_btn': QPushButton(f"设置CH{ch2_conf['channel']}")}, 'output_btn': QPushButton("打开总电源"), 'status_label': QLabel("电源状态: 未知"), 'auto_off_input': QLineEdit("0"), 'log_interval_input': QLineEdit("30")}; self.power_widgets['output_btn'].setCheckable(True); layout.addWidget(QLabel("<b>CH1:</b> V/A"), 0, 0); layout.addWidget(self.power_widgets['ch1']['volt_input'], 0, 1); layout.addWidget(self.power_widgets['ch1']['curr_input'], 0, 2); layout.addWidget(self.power_widgets['ch1']['set_btn'], 0, 3); layout.addWidget(QLabel("<b>CH2:</b> V/A"), 1, 0); layout.addWidget(self.power_widgets['ch2']['volt_input'], 1, 1); layout.addWidget(self.power_widgets['ch2']['curr_input'], 1, 2); layout.addWidget(self.power_widgets['ch2']['set_btn'], 1, 3); layout.addWidget(self.power_widgets['status_label'], 0, 4, 2, 1); layout.addWidget(QLabel("定时关闭(秒):"), 0, 5); layout.addWidget(self.power_widgets['auto_off_input'], 0, 6); layout.addWidget(QLabel("采样间隔(秒):"), 1, 5); layout.addWidget(self.power_widgets['log_interval_input'], 1, 6); self.emergency_stop_btn = QPushButton("!! 紧急停止 !!"); self.emergency_stop_btn.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold;"); layout.addWidget(self.power_widgets['output_btn'], 0, 7); layout.addWidget(self.emergency_stop_btn, 1, 7); layout.setColumnStretch(4, 1); group.setLayout(layout); return group
    
    def _setup_plots(self):
        """初始化系统A和B的图表"""
        self._setup_subsystem_plot(self.subsystem_A_widget, self.config['subsystem_A'])
        self._setup_subsystem_plot(self.subsystem_B_widget, self.config['subsystem_B'])

    def _setup_subsystem_plot(self, subsystem_widget, subsystem_config):
        plot_item = subsystem_widget.plot_widget.getPlotItem()
        plot_item.setLabel('bottom', '时间 (s)')
        plot_item.setLabel('left', '电压 (V) / 转速 (RPM)', color='b')
        plot_item.setLabel('right', '电流 (A) / 流量 (ml/min)', color='r')
        plot_item.showAxis('right')

        p2 = pg.ViewBox()
        plot_item.scene().addItem(p2)
        plot_item.getAxis('right').linkToView(p2)
        p2.setXLink(plot_item)
        plot_item.getViewBox().sigResized.connect(lambda: p2.setGeometry(plot_item.getViewBox().sceneBoundingRect()))

        # 电源曲线
        ch = subsystem_config['channel']
        subsystem_widget.curves = {}
        subsystem_widget.curves['voltage'] = plot_item.plot(pen=pg.mkPen('b', width=2), name=f"CH{ch} Voltage")
        subsystem_widget.curves['current'] = pg.PlotDataItem(pen=pg.mkPen('r', width=2, style=Qt.PenStyle.DashLine), name=f"CH{ch} Current")
        p2.addItem(subsystem_widget.curves['current'])

        # 泵的曲线
        pump_pens = [pg.mkPen('g', width=2), pg.mkPen('m', width=2), pg.mkPen('y', width=2)]
        for i, pump in enumerate(subsystem_config['pumps']):
            pen = pump_pens[i % len(pump_pens)]
            if 'kamoer' in pump['type']:
                subsystem_widget.curves[pump['id']] = plot_item.plot(pen=pen, name=pump['description'])
            else:
                curve = pg.PlotDataItem(pen=pen, name=pump['description'])
                p2.addItem(curve)
                subsystem_widget.curves[pump['id']] = curve

    def _connect_signals(self):
        self.power_widgets['ch1']['set_btn'].clicked.connect(lambda: self.on_set_power_channel(1)); self.power_widgets['ch2']['set_btn'].clicked.connect(lambda: self.on_set_power_channel(2)); self.power_widgets['output_btn'].clicked.connect(self.on_toggle_power_output); self.emergency_stop_btn.clicked.connect(self.on_emergency_stop); self.power_widgets['log_interval_input'].returnPressed.connect(self.on_set_log_interval); self.subsystem_A_widget.connect_signals(); self.subsystem_B_widget.connect_signals(); self.subsystem_A_widget.export_data_button.clicked.connect(lambda: self.on_export_data('A')); self.subsystem_B_widget.export_data_button.clicked.connect(lambda: self.on_export_data('B'))
        # ★★★ 核心修改 2: 连接新的保存图表按钮的信号 ★★★
        self.subsystem_A_widget.export_chart_button.clicked.connect(lambda: self.on_save_chart('A'))
        self.subsystem_B_widget.export_chart_button.clicked.connect(lambda: self.on_save_chart('B'))

    def _start_backend(self):
        all_devices = [self.config['power_supply']] + self.config['subsystem_A']['pumps'] + self.config['subsystem_B']['pumps']; self.command_queue = multiprocessing.Queue(); self.status_queue = multiprocessing.Queue(); self.log_queue = multiprocessing.Queue(); controller = SystemController(all_devices, self.command_queue, self.status_queue, self.log_queue); self.process = multiprocessing.Process(target=controller.run, daemon=True); self.process.start(); self.ui_timer = QTimer(self); self.ui_timer.setInterval(500); self.ui_timer.timeout.connect(self.update_ui); self.ui_timer.start()
    def update_ui(self):
        try:
            status_data = None
            while not self.status_queue.empty(): status_data = self.status_queue.get_nowait()
            if status_data:
                if 'error' in status_data: QMessageBox.critical(self, "后台错误", status_data['error']); return
                if status_data.get('loggable', False): self._log_data_point(status_data)
                devices_status = status_data.get('devices', {}); self._update_power_status(devices_status); self._update_subsystem_status(self.subsystem_A_widget, self.config['subsystem_A'], self.data_log_A, devices_status); self._update_subsystem_status(self.subsystem_B_widget, self.config['subsystem_B'], self.data_log_B, devices_status)
        except Empty: pass
        except Exception as e: print(f"UI更新时发生错误: {e}")
    def _update_power_status(self, devices_status):
        power_id = self.config['power_supply']['id']; power_status = devices_status.get(power_id, {});
        if not power_status: return
        output_on = power_status.get('output_on', False); ch1_v = power_status.get('ch1_voltage', 0.0); ch1_c = power_status.get('ch1_current', 0.0); ch2_v = power_status.get('ch2_voltage', 0.0); ch2_c = power_status.get('ch2_current', 0.0); status_text = f"CH1: {ch1_v:.3f}V/{ch1_c:.3f}A | CH2: {ch2_v:.3f}V/{ch2_c:.3f}A | 总输出: {'打开' if output_on else '关闭'}"; self.power_widgets['status_label'].setText(status_text); self.power_widgets['output_btn'].setChecked(output_on); self.power_widgets['output_btn'].setText("关闭总电源" if output_on else "打开总电源")
    def _update_subsystem_status(self, subsystem_widget, subsystem_config, data_log, devices_status):
        # 更新电源曲线
        power_id = self.config['power_supply']['id']; power_status = devices_status.get(power_id, {})
        ch = subsystem_config['channel']; voltage = power_status.get(f'ch{ch}_voltage', 0); current = power_status.get(f'ch{ch}_current', 0)
        subsystem_widget.curves['voltage'].setData(data_log['time'], data_log[f'ch{ch}_voltage'])
        subsystem_widget.curves['current'].setData(data_log['time'], data_log[f'ch{ch}_current'])

        # 更新泵的状态和曲线
        for pump_conf in subsystem_config['pumps']:
            pump_id = pump_conf['id']; pump_status = devices_status.get(pump_id, {});
            if pump_status: 
                is_running = pump_status.get('is_running', False); speed = pump_status.get('speed_rpm', 0.0); flow = pump_status.get('flow_rate_ml_min', 0.0); subsystem_widget.pump_widgets[pump_id]['status_label'].setText(f"状态: {'运行中' if is_running else '已停止'}"); is_peristaltic = 'kamoer' in pump_conf.get('type',''); current_value = speed if is_peristaltic else flow; subsystem_widget.pump_widgets[pump_id]['value_label'].setText(f"当前: {current_value:.2f}")
                
                # 更新泵的曲线
                if is_peristaltic: subsystem_widget.curves[pump_id].setData(data_log['time'], data_log[f"{pump_id}_speed"])
                else: subsystem_widget.curves[pump_id].setData(data_log['time'], data_log[f"{pump_id}_flow"])

    def _log_data_point(self, status_data):
        elapsed_time = status_data['timestamp'] - self.start_time; devices_status = status_data.get('devices', {}); power_status = devices_status.get(self.config['power_supply']['id'], {}); self.data_log_A['time'].append(elapsed_time); self.data_log_A[f"ch1_voltage"].append(power_status.get('ch1_voltage', 0)); self.data_log_A[f"ch1_current"].append(power_status.get('ch1_current', 0));
        for pump in self.config['subsystem_A']['pumps']: pump_status = devices_status.get(pump['id'], {}); self.data_log_A[f"{pump['id']}_speed"].append(pump_status.get('speed_rpm', 0)); self.data_log_A[f"{pump['id']}_flow"].append(pump_status.get('flow_rate_ml_min', 0))
        self.data_log_B['time'].append(elapsed_time); self.data_log_B[f"ch2_voltage"].append(power_status.get('ch2_voltage', 0)); self.data_log_B[f"ch2_current"].append(power_status.get('ch2_current', 0));
        for pump in self.config['subsystem_B']['pumps']: pump_status = devices_status.get(pump['id'], {}); self.data_log_B[f"{pump['id']}_speed"].append(pump_status.get('speed_rpm', 0)); self.data_log_B[f"{pump['id']}_flow"].append(pump_status.get('flow_rate_ml_min', 0))
    def on_set_power_channel(self, channel):
        try: widgets = self.power_widgets[f'ch{channel}']; params = {'device_id': self.config['power_supply']['id'], 'channel': channel, 'voltage': float(widgets['volt_input'].text()), 'current': float(widgets['curr_input'].text())}; self.command_queue.put({'type': 'set_power_voltage', 'params': params}); self.command_queue.put({'type': 'set_power_current', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", f"CH{channel} 的电压或电流值无效。")
    def on_toggle_power_output(self, checked):
        try:
            params = {'device_id': self.config['power_supply']['id'], 'enable': checked}
            if checked: auto_off_seconds = float(self.power_widgets['auto_off_input'].text());
            if auto_off_seconds > 0: params['auto_off_seconds'] = auto_off_seconds
            self.command_queue.put({'type': 'set_power_output', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", "定时关闭时间必须是有效的数字！"); self.power_widgets['output_btn'].setChecked(not checked)
    def on_emergency_stop(self): self.command_queue.put({'type': 'stop_all'})
    def on_set_log_interval(self):
        try:
            interval = float(self.power_widgets['log_interval_input'].text())
            if interval > 0: self.command_queue.put({'type': 'set_log_interval', 'params': {'interval': interval}})
            else: QMessageBox.warning(self, "输入错误", "采样间隔必须大于0。")
        except ValueError: QMessageBox.warning(self, "输入错误", "采样间隔必须是有效的数字！")
    def on_start_pump(self, pump_id):
        widget_set = self._find_pump_widgets(pump_id);
        if not widget_set: return
        try:
            direction = 'reverse' if widget_set['direction_box'].currentText() == '反转' else 'forward'; params = {'pump_id': pump_id, 'direction': direction}
            if 'kamoer' in self._get_pump_config(pump_id).get('type',''): params['speed'] = float(widget_set['input'].text())
            else: params['flow_rate'] = float(widget_set['input'].text())
            self.command_queue.put({'type': 'start_pump', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", "泵的转速/流量值无效。")
    def on_stop_pump(self, pump_id): self.command_queue.put({'type': 'stop_pump', 'params': {'pump_id': pump_id}})
    def on_set_pump_params(self, pump_id):
        widget_set = self._find_pump_widgets(pump_id);
        if not widget_set: return
        try:
            direction = 'reverse' if widget_set['direction_box'].currentText() == '反转' else 'forward'; params = {'pump_id': pump_id, 'direction': direction}
            if 'kamoer' in self._get_pump_config(pump_id).get('type',''): params['speed'] = float(widget_set['input'].text())
            else: params['flow_rate'] = float(widget_set['input'].text())
            self.command_queue.put({'type': 'set_pump_params', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", "泵的转速/流量值无效。")
    def on_export_data(self, subsystem_letter):
        data_log = self.data_log_A if subsystem_letter == 'A' else self.data_log_B
        if not data_log['time']: QMessageBox.warning(self, "无数据", f"系统 {subsystem_letter} 没有可导出的数据。"); return
        default_filename = f"System_{subsystem_letter}_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filename, _ = QFileDialog.getSaveFileName(self, f"导出系统 {subsystem_letter} 数据", default_filename, "Excel Files (*.xlsx)")
        if filename:
            try: df = pd.DataFrame(data_log); df.to_excel(filename, index=False, engine='openpyxl'); QMessageBox.information(self, "成功", f"数据已成功导出到:\n{filename}")
            except Exception as e: QMessageBox.critical(self, "导出失败", f"无法保存文件: {e}")
    
    # ★★★ 核心修改 3: 新增保存图表的槽函数 ★★★
    def on_save_chart(self, subsystem_letter):
        subsystem_widget = self.subsystem_A_widget if subsystem_letter == 'A' else self.subsystem_B_widget
        default_filename = f"System_{subsystem_letter}_Chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filename, _ = QFileDialog.getSaveFileName(self, f"保存系统 {subsystem_letter} 图表", default_filename, "PNG Files (*.png);;JPG Files (*.jpg)")
        if filename:
            try:
                exporter = ImageExporter(subsystem_widget.plot_widget.getPlotItem())
                exporter.export(filename)
                QMessageBox.information(self, "成功", f"图表已成功保存到:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"无法保存图表: {e}")

    def on_add_start_set_pump(self, protocol_widget):
        pump_configs = protocol_widget.subsystem_config['pumps']; dialog = PumpActionDialog(pump_configs, self)
        if dialog.exec():
            try:
                pump_id, params = dialog.get_selected_params(); msg_box = QMessageBox(self); msg_box.setText(f"为 {self.device_descriptions[pump_id]} 添加什么步骤？"); start_btn = msg_box.addButton("启动泵", QMessageBox.ButtonRole.ActionRole); set_btn = msg_box.addButton("仅设置参数", QMessageBox.ButtonRole.ActionRole); msg_box.addButton(QMessageBox.StandardButton.Cancel); msg_box.exec()
                if msg_box.clickedButton() == start_btn: self._add_step_to_protocol(protocol_widget, {'command': 'start_pump', 'pump_id': pump_id, **params})
                elif msg_box.clickedButton() == set_btn: self._add_step_to_protocol(protocol_widget, {'command': 'set_pump_params', 'pump_id': pump_id, **params})
            except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的数字！")
    def on_add_stop_pump(self, protocol_widget):
        pump_configs = protocol_widget.subsystem_config['pumps']; dialog = PumpActionDialog(pump_configs, self, show_params=False)
        if dialog.exec(): pump_id, _ = dialog.get_selected_params(); self._add_step_to_protocol(protocol_widget, {'command': 'stop_pump', 'pump_id': pump_id})
    def on_add_delay(self, protocol_widget):
        dialog = DelayDialog(self)
        if dialog.exec():
            try: duration = float(dialog.duration_input.text()); self._add_step_to_protocol(protocol_widget, {'command': 'delay', 'duration': duration})
            except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的数字！")
    def on_run_protocol(self, protocol_widget):
        if protocol_widget.protocol_list_widget.count() == 0: return
        protocol_list = [protocol_widget.protocol_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(protocol_widget.protocol_list_widget.count())]; self.command_queue.put({'type': 'run_protocol', 'params': {'protocol': protocol_list}}); QMessageBox.information(self, "协议已启动", "自动化协议已发送到后台执行。")
    def on_save_protocol(self, protocol_widget):
        protocol_list = [protocol_widget.protocol_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(protocol_widget.protocol_list_widget.count())];
        if not protocol_list: return
        filename, _ = QFileDialog.getSaveFileName(self, "保存协议文件", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f: json.dump(protocol_list, f, indent=4); QMessageBox.information(self, "成功", "协议已保存。")
            except Exception as e: QMessageBox.critical(self, "错误", f"保存失败: {e}")
    def on_load_protocol(self, protocol_widget):
        filename, _ = QFileDialog.getOpenFileName(self, "加载协议文件", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f: protocol_list = json.load(f); protocol_widget.protocol_list_widget.clear()
                for step in protocol_list: self._add_step_to_protocol(protocol_widget, step)
                QMessageBox.information(self, "成功", "协议已加载。")
            except Exception as e: QMessageBox.critical(self, "错误", f"加载或解析文件失败: {e}")
    def _add_step_to_protocol(self, protocol_widget, command_dict):
        desc = self.generate_description_from_command(command_dict); item = QListWidgetItem(desc); item.setData(Qt.ItemDataRole.UserRole, command_dict); protocol_widget.protocol_list_widget.addItem(item)
    def generate_description_from_command(self, command):
        cmd_type = command.get('command'); desc = f"未知指令: {cmd_type}"; pump_id = command.get('pump_id'); target_desc = self.device_descriptions.get(pump_id, pump_id)
        if cmd_type == 'start_pump' or cmd_type == 'set_pump_params':
            action = "启动" if cmd_type == 'start_pump' else "设置"; params = {k: v for k, v in command.items() if k not in ['command', 'pump_id']}; param_str = ", ".join([f"{k}: {v}" for k, v in params.items()]); desc = f"{action}泵: {target_desc}, 参数: {param_str}"
        elif cmd_type == 'stop_pump': desc = f"停止泵: {target_desc}"
        elif cmd_type == 'delay': desc = f"延时: {command.get('duration', 0)} 秒"
        return desc
    def _find_pump_widgets(self, pump_id):
        if pump_id in self.subsystem_A_widget.pump_widgets: return self.subsystem_A_widget.pump_widgets[pump_id]
        if pump_id in self.subsystem_B_widget.pump_widgets: return self.subsystem_B_widget.pump_widgets[pump_id]
        return None
    def _get_pump_config(self, pump_id):
        for p in self.config['subsystem_A']['pumps']:
            if p['id'] == pump_id: return p
        for p in self.config['subsystem_B']['pumps']:
            if p['id'] == pump_id: return p
        return None
    def closeEvent(self, event):
        self.ui_timer.stop()
        if self.process and self.process.is_alive():
            self.command_queue.put({'type': 'shutdown'}); self.process.join(timeout=3)
            if self.process.is_alive(): self.process.terminate()
        if self.config['set_id'] in app.launcher.open_windows:
            del app.launcher.open_windows[self.config['set_id']]
        super().closeEvent(event)

class ResourceManager:
    # ... (ResourceManager 类代码无变化，为简洁此处省略) ...
    def __init__(self, system_sets):
        self.all_devices = [];
        for system_set in system_sets: self.all_devices.append(system_set['power_supply']); self.all_devices.extend(system_set['subsystem_A']['pumps']); self.all_devices.extend(system_set['subsystem_B']['pumps'])
        self.locked_devices = set()
    def get_available_devices_by_type(self, device_type):
        available = []
        for device in self.all_devices:
            if device['type'] == device_type and device['id'] not in self.locked_devices: available.append(device)
        return available
    def lock_devices(self, device_ids): self.locked_devices.update(device_ids)
    def release_devices(self, device_ids): self.locked_devices.difference_update(device_ids)

class DebugWindow(QMainWindow):
    # ... (DebugWindow 类代码无变化，为简洁此处省略) ...
    def __init__(self, device_config):
        super().__init__(); self.config = device_config; self.setWindowTitle(f"调试: {self.config['description']}"); self.resize(1200, 800); self.widgets = {}; self.command_queue, self.status_queue, self.log_queue, self.process = None, None, None, None; self.start_time = time.time(); self.data_log = self._init_data_log(); self.curves = {}; self._init_ui(); self._connect_signals(); self._start_backend()
    def _init_data_log(self):
        log = {'time': []}; dev_type = self.config['type']
        if dev_type == 'gpd_4303s': log['ch1_voltage'] = []; log['ch1_current'] = []; log['ch2_voltage'] = []; log['ch2_current'] = []
        else: log['speed'] = []; log['flow'] = []
        return log
    def _init_ui(self):
        central_widget = QWidget(); self.setCentralWidget(central_widget); main_layout = QVBoxLayout(central_widget); splitter = QSplitter(Qt.Orientation.Vertical); top_widget = QWidget(); top_layout = QHBoxLayout(top_widget); manual_group = QGroupBox("手动控制"); manual_layout = QGridLayout(); dev_type = self.config['type']
        if dev_type == 'gpd_4303s': self._create_power_debug_ui(manual_layout)
        else: self._create_pump_debug_ui(manual_layout, 'kamoer' in dev_type)
        self.status_label = QLabel("状态: 未知"); manual_layout.addWidget(self.status_label, 3, 0, 1, 5); manual_group.setLayout(manual_layout); top_layout.addWidget(manual_group)
        if 'pump' in self.config['id']:
            mock_subsystem_config = {'pumps': [self.config]}; self.protocol_widget = ProtocolWidget(mock_subsystem_config, self); top_layout.addWidget(self.protocol_widget); top_splitter = QSplitter(Qt.Orientation.Horizontal); top_splitter.addWidget(manual_group); top_splitter.addWidget(self.protocol_widget); top_splitter.setSizes([400, 600]); top_layout.addWidget(top_splitter)
        else: top_layout.addWidget(manual_group)
        splitter.addWidget(top_widget); chart_group = self._create_chart_group(); splitter.addWidget(chart_group); splitter.setSizes([300, 500]); main_layout.addWidget(splitter)
    def _create_power_debug_ui(self, layout):
        self.widgets = {'ch1_v': QLineEdit("5.0"), 'ch1_c': QLineEdit("1.0"), 'ch1_set': QPushButton("设置CH1"), 'ch2_v': QLineEdit("5.0"), 'ch2_c': QLineEdit("1.0"), 'ch2_set': QPushButton("设置CH2"), 'output': QPushButton("打开输出")}; self.widgets['output'].setCheckable(True); layout.addWidget(QLabel("CH1 V/A:"), 0, 0); layout.addWidget(self.widgets['ch1_v'], 0, 1); layout.addWidget(self.widgets['ch1_c'], 0, 2); layout.addWidget(self.widgets['ch1_set'], 0, 3); layout.addWidget(QLabel("CH2 V/A:"), 1, 0); layout.addWidget(self.widgets['ch2_v'], 1, 1); layout.addWidget(self.widgets['ch2_c'], 1, 2); layout.addWidget(self.widgets['ch2_set'], 1, 3); layout.addWidget(self.widgets['output'], 2, 0, 1, 4)
    def _create_pump_debug_ui(self, layout, is_peristaltic):
        self.widgets = {'input': QLineEdit("100.0" if is_peristaltic else "5.0"), 'start': QPushButton("启动"), 'stop': QPushButton("停止"), 'direction': QComboBox()}; self.widgets['direction'].addItems(["正转", "反转"]); label = "转速 (RPM):" if is_peristaltic else "流量 (ml/min):"; layout.addWidget(QLabel(label), 0, 0); layout.addWidget(self.widgets['input'], 0, 1); layout.addWidget(QLabel("方向:"), 1, 0); layout.addWidget(self.widgets['direction'], 1, 1); layout.addWidget(self.widgets['start'], 2, 0); layout.addWidget(self.widgets['stop'], 2, 1)
    def _create_chart_group(self):
        group = QGroupBox("实时数据"); layout = QVBoxLayout(); self.plot_widget = pg.PlotWidget(); self.plot_widget.setBackground('w'); self.plot_widget.showGrid(x=True, y=True); self.plot_widget.addLegend(); plot_item = self.plot_widget.getPlotItem(); plot_item.setLabel('bottom', '时间 (s)'); dev_type = self.config['type']
        if dev_type == 'gpd_4303s':
            plot_item.setLabel('left', '电压 (V)', color='b'); plot_item.setLabel('right', '电流 (A)', color='r'); plot_item.showAxis('right'); self.curves['ch1_v'] = plot_item.plot(pen=pg.mkPen('b'), name="CH1 Voltage"); self.curves['ch2_v'] = plot_item.plot(pen=pg.mkPen('c'), name="CH2 Voltage"); p2 = pg.ViewBox(); plot_item.scene().addItem(p2); plot_item.getAxis('right').linkToView(p2); p2.setXLink(plot_item); self.curves['ch1_c'] = pg.PlotDataItem(pen=pg.mkPen('r', style=Qt.PenStyle.DashLine), name="CH1 Current"); p2.addItem(self.curves['ch1_c']); self.curves['ch2_c'] = pg.PlotDataItem(pen=pg.mkPen('m', style=Qt.PenStyle.DashLine), name="CH2 Current"); p2.addItem(self.curves['ch2_c']); plot_item.getViewBox().sigResized.connect(lambda: p2.setGeometry(plot_item.getViewBox().sceneBoundingRect()))
        else: 
            plot_item.setLabel('left', '转速 (RPM)', color='b'); plot_item.setLabel('right', '流量 (ml/min)', color='r'); plot_item.showAxis('right'); self.curves['speed'] = plot_item.plot(pen=pg.mkPen('b'), name="Speed"); p2 = pg.ViewBox(); plot_item.scene().addItem(p2); plot_item.getAxis('right').linkToView(p2); p2.setXLink(plot_item); self.curves['flow'] = pg.PlotDataItem(pen=pg.mkPen('r'), name="Flow"); p2.addItem(self.curves['flow']); plot_item.getViewBox().sigResized.connect(lambda: p2.setGeometry(plot_item.getViewBox().sceneBoundingRect()))
        self.export_button = QPushButton("导出Excel数据"); layout.addWidget(self.plot_widget); layout.addWidget(self.export_button); group.setLayout(layout); return group
    def _connect_signals(self):
        self.export_button.clicked.connect(self.on_export_data); dev_type = self.config['type']
        if dev_type == 'gpd_4303s': self.widgets['ch1_set'].clicked.connect(lambda: self.on_set_power(1)); self.widgets['ch2_set'].clicked.connect(lambda: self.on_set_power(2)); self.widgets['output'].clicked.connect(self.on_toggle_output)
        else: self.widgets['start'].clicked.connect(self.on_start_pump); self.widgets['stop'].clicked.connect(self.on_stop_pump); self.widgets['input'].returnPressed.connect(self.on_set_pump); self.widgets['direction'].currentTextChanged.connect(self.on_set_pump)
        if hasattr(self, 'protocol_widget'): self.protocol_widget.connect_signals()
    def _start_backend(self):
        self.command_queue = multiprocessing.Queue(); self.status_queue = multiprocessing.Queue(); self.log_queue = multiprocessing.Queue(); controller = SystemController([self.config], self.command_queue, self.status_queue, self.log_queue); self.process = multiprocessing.Process(target=controller.run, daemon=True); self.process.start(); self.ui_timer = QTimer(self); self.ui_timer.setInterval(500); self.ui_timer.timeout.connect(self.update_ui); self.ui_timer.start()
    def update_ui(self):
        try:
            status_data = self.status_queue.get_nowait(); status = status_data.get('devices', {}).get(self.config['id'], {})
            if not status: return
            elapsed_time = status_data['timestamp'] - self.start_time; self.data_log['time'].append(elapsed_time); dev_type = self.config['type']
            if dev_type == 'gpd_4303s':
                on = status.get('output_on', False); v1 = status.get('ch1_voltage', 0); c1 = status.get('ch1_current', 0); v2 = status.get('ch2_voltage', 0); c2 = status.get('ch2_current', 0); self.status_label.setText(f"CH1: {v1:.3f}V/{c1:.3f}A | CH2: {v2:.3f}V/{c2:.3f}A | 输出: {'开' if on else '关'}"); self.widgets['output'].setChecked(on); self.data_log['ch1_voltage'].append(v1); self.data_log['ch1_current'].append(c1); self.data_log['ch2_voltage'].append(v2); self.data_log['ch2_current'].append(c2); self.curves['ch1_v'].setData(self.data_log['time'], self.data_log['ch1_voltage']); self.curves['ch1_c'].setData(self.data_log['time'], self.data_log['ch1_current']); self.curves['ch2_v'].setData(self.data_log['time'], self.data_log['ch2_voltage']); self.curves['ch2_c'].setData(self.data_log['time'], self.data_log['ch2_current'])
            else:
                run = status.get('is_running', False); s = status.get('speed_rpm', 0); f = status.get('flow_rate_ml_min', 0); self.status_label.setText(f"状态: {'运行中' if run else '停止'} | 转速: {s:.2f} | 流量: {f:.2f}"); self.data_log['speed'].append(s); self.data_log['flow'].append(f); self.curves['speed'].setData(self.data_log['time'], self.data_log['speed']); self.curves['flow'].setData(self.data_log['time'], self.data_log['flow'])
        except Empty: pass
        except Exception as e: print(f"Debug window UI update error: {e}")
    def on_export_data(self):
        if not self.data_log['time']: QMessageBox.warning(self, "无数据", "没有可导出的数据。"); return
        default_filename = f"Debug_{self.config['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filename, _ = QFileDialog.getSaveFileName(self, "导出调试数据", default_filename, "Excel Files (*.xlsx)")
        if filename:
            try: pd.DataFrame(self.data_log).to_excel(filename, index=False, engine='openpyxl'); QMessageBox.information(self, "成功", f"数据已成功导出到:\n{filename}")
            except Exception as e: QMessageBox.critical(self, "导出失败", f"无法保存文件: {e}")
    def on_set_power(self, channel):
        try:
            v_in, c_in = (self.widgets['ch1_v'], self.widgets['ch1_c']) if channel == 1 else (self.widgets['ch2_v'], self.widgets['ch2_c'])
            params = {'device_id': self.config['id'], 'channel': channel, 'voltage': float(v_in.text()), 'current': float(c_in.text())}; self.command_queue.put({'type': 'set_power_voltage', 'params': params}); self.command_queue.put({'type': 'set_power_current', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", "电压或电流值无效。")
    def on_toggle_output(self, checked): self.command_queue.put({'type': 'set_power_output', 'params': {'device_id': self.config['id'], 'enable': checked}})
    def on_start_pump(self):
        try:
            params = {'pump_id': self.config['id'], 'direction': 'reverse' if self.widgets['direction'].currentText() == '反转' else 'forward'}
            if 'kamoer' in self.config['type']: params['speed'] = float(self.widgets['input'].text())
            else: params['flow_rate'] = float(self.widgets['input'].text())
            self.command_queue.put({'type': 'start_pump', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", "值无效。")
    def on_stop_pump(self): self.command_queue.put({'type': 'stop_pump', 'params': {'pump_id': self.config['id']}})
    def on_set_pump(self):
        try:
            params = {'pump_id': self.config['id'], 'direction': 'reverse' if self.widgets['direction'].currentText() == '反转' else 'forward'}
            if 'kamoer' in self.config['type']: params['speed'] = float(self.widgets['input'].text())
            else: params['flow_rate'] = float(self.widgets['input'].text())
            self.command_queue.put({'type': 'set_pump_params', 'params': params})
        except ValueError: QMessageBox.warning(self, "输入错误", "值无效。")
    def on_add_start_set_pump(self, protocol_widget):
        pump_configs = protocol_widget.subsystem_config['pumps']; dialog = PumpActionDialog(pump_configs, self)
        if dialog.exec():
            try:
                pump_id, params = dialog.get_selected_params(); msg_box = QMessageBox(self); msg_box.setText(f"为 {self.config['description']} 添加什么步骤？"); start_btn = msg_box.addButton("启动泵", QMessageBox.ButtonRole.ActionRole); set_btn = msg_box.addButton("仅设置参数", QMessageBox.ButtonRole.ActionRole); msg_box.addButton(QMessageBox.StandardButton.Cancel); msg_box.exec()
                if msg_box.clickedButton() == start_btn: self._add_step_to_protocol(protocol_widget, {'command': 'start_pump', 'pump_id': pump_id, **params})
                elif msg_box.clickedButton() == set_btn: self._add_step_to_protocol(protocol_widget, {'command': 'set_pump_params', 'pump_id': pump_id, **params})
            except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的数字！")
    def on_add_stop_pump(self, protocol_widget):
        pump_configs = protocol_widget.subsystem_config['pumps']; dialog = PumpActionDialog(pump_configs, self, show_params=False)
        if dialog.exec(): pump_id, _ = dialog.get_selected_params(); self._add_step_to_protocol(protocol_widget, {'command': 'stop_pump', 'pump_id': pump_id})
    def on_add_delay(self, protocol_widget):
        dialog = DelayDialog(self)
        if dialog.exec():
            try: duration = float(dialog.duration_input.text()); self._add_step_to_protocol(protocol_widget, {'command': 'delay', 'duration': duration})
            except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的数字！")
    def on_run_protocol(self, protocol_widget):
        if protocol_widget.protocol_list_widget.count() == 0: return
        protocol_list = [protocol_widget.protocol_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(protocol_widget.protocol_list_widget.count())]; self.command_queue.put({'type': 'run_protocol', 'params': {'protocol': protocol_list}}); QMessageBox.information(self, "协议已启动", "自动化协议已发送到后台执行。")
    def on_save_protocol(self, protocol_widget):
        protocol_list = [protocol_widget.protocol_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(protocol_widget.protocol_list_widget.count())];
        if not protocol_list: return
        filename, _ = QFileDialog.getSaveFileName(self, "保存协议文件", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f: json.dump(protocol_list, f, indent=4); QMessageBox.information(self, "成功", "协议已保存。")
            except Exception as e: QMessageBox.critical(self, "错误", f"保存失败: {e}")
    def on_load_protocol(self, protocol_widget):
        filename, _ = QFileDialog.getOpenFileName(self, "加载协议文件", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f: protocol_list = json.load(f); protocol_widget.protocol_list_widget.clear()
                for step in protocol_list: self._add_step_to_protocol(protocol_widget, step)
                QMessageBox.information(self, "成功", "协议已加载。")
            except Exception as e: QMessageBox.critical(self, "错误", f"加载或解析文件失败: {e}")
    def _add_step_to_protocol(self, protocol_widget, command_dict):
        desc = self.generate_description_from_command(command_dict); item = QListWidgetItem(desc); item.setData(Qt.ItemDataRole.UserRole, command_dict); protocol_widget.protocol_list_widget.addItem(item)
    def generate_description_from_command(self, command):
        cmd_type = command.get('command'); desc = f"未知指令: {cmd_type}"; pump_id = command.get('pump_id'); target_desc = self.config['description']
        if cmd_type == 'start_pump' or cmd_type == 'set_pump_params':
            action = "启动" if cmd_type == 'start_pump' else "设置"; params = {k: v for k, v in command.items() if k not in ['command', 'pump_id']}; param_str = ", ".join([f"{k}: {v}" for k, v in params.items()]); desc = f"{action}泵: {target_desc}, 参数: {param_str}"
        elif cmd_type == 'stop_pump': desc = f"停止泵: {target_desc}"
        elif cmd_type == 'delay': desc = f"延时: {command.get('duration', 0)} 秒"
        return desc
    def closeEvent(self, event):
        self.ui_timer.stop()
        if self.process and self.process.is_alive():
            self.command_queue.put({'type': 'shutdown'}); self.process.join(timeout=2)
            if self.process.is_alive(): self.process.terminate()
        app.launcher.resource_manager.release_devices([self.config['id']])
        if self.config['id'] in app.launcher.open_windows:
            del app.launcher.open_windows[self.config['id']]
        super().closeEvent(event)

class LauncherWindow(QMainWindow):
    """程序启动器窗口。"""
    def __init__(self, system_sets):
        super().__init__()
        self.setWindowTitle("实验控制系统启动器")
        self.system_sets = system_sets
        self.resource_manager = ResourceManager(system_sets)
        self.open_windows = {}

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.addWidget(QLabel("<h2>请选择要启动的控制系统：</h2>"))
        for config in self.system_sets:
            btn = QPushButton(config['set_description'])
            btn.clicked.connect(lambda _, c=config: self.launch_system(c))
            layout.addWidget(btn)
        
        layout.addStretch()
        self.debug_button = QPushButton("调试单个设备")
        self.debug_button.setStyleSheet("background-color: #f0ad4e;")
        self.debug_button.clicked.connect(self.launch_debugger)
        layout.addWidget(self.debug_button)
        
        self.setCentralWidget(main_widget)

    def launch_system(self, config):
        set_id = config['set_id']
        if set_id in self.open_windows and self.open_windows[set_id].isVisible():
            self.open_windows[set_id].activateWindow()
        else:
            control_window = ControlSystemWindow(config)
            self.open_windows[set_id] = control_window
            control_window.show()

    def launch_debugger(self):
        dialog = DebugDeviceDialog(self)
        if dialog.exec() and dialog.selected_config:
            config = dialog.selected_config
            dev_id = config['id']
            # 使用设备ID作为唯一标识符
            if dev_id in self.open_windows and self.open_windows[dev_id].isVisible():
                self.open_windows[dev_id].activateWindow()
            else:
                self.resource_manager.lock_devices([dev_id])
                debug_window = DebugWindow(config)
                self.open_windows[dev_id] = debug_window
                debug_window.show()


# --- 程序主入口 ---
if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    app.launcher = LauncherWindow(SYSTEM_SETS)
    app.launcher.show()
    sys.exit(app.exec())

