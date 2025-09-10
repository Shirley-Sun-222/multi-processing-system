# file: app_main.py (已添加方向控制功能的最终版)

import sys
import multiprocessing
import json
import time
from queue import Empty

# 导入所有必要的第三方库
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
import pandas as pd

# 导入所有必要的PyQt6组件
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, QGridLayout,
                             QMessageBox, QDialog, QFormLayout,
                             QListWidget, QListWidgetItem, QAbstractItemView,
                             QDialogButtonBox, QGroupBox, QFileDialog, QSplitter, QTextEdit,
                             QComboBox)
from PyQt6.QtCore import QTimer, Qt

# 导入我们自己编写的模块
from system_controller import SystemController
from system_config import DEVICE_POOL
try:
    from protocol import auto_protocol
except ImportError:
    auto_protocol = [{"command": "delay", "duration": 1}]


# --- 资源管理器 ---
class ResourceManager:
    """管理全局设备池的状态（空闲/占用）。"""
    def __init__(self, device_pool):
        self.pool = device_pool
        self.locked_devices = set()

    def get_available_devices(self):
        """获取设备池中所有类型（泵、电源等）的可用设备。"""
        available = []
        for device_category in self.pool.values():
            if isinstance(device_category, list):
                for device in device_category:
                    if device.get('id') not in self.locked_devices:
                        available.append(device)
        return available

    def lock_devices(self, device_ids):
        self.locked_devices.update(device_ids)
        print(f"[ResourceManager] 已锁定设备: {device_ids}")

    def release_devices(self, device_ids):
        self.locked_devices.difference_update(device_ids)
        print(f"[ResourceManager] 已释放设备: {device_ids}")


# --- 对话框 ---
class DeviceSelectionDialog(QDialog):
    """从资源池中选择一个或多个设备的通用对话框。"""
    def __init__(self, resource_manager, mode='system', parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择设备")
        self.resource_manager = resource_manager
        
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        
        if mode == 'debug':
            self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            layout.addWidget(QLabel("请选择一个要调试的设备："))
        else:
            self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            layout.addWidget(QLabel("请选择要用于该系统的设备（可多选）："))

        layout.addWidget(self.list_widget)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
        self.populate_list()
        
    def populate_list(self):
        self.list_widget.clear()
        available_devices = self.resource_manager.get_available_devices()
        if not available_devices:
            self.list_widget.addItem("（当前无可用设备）")
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            for config in available_devices:
                item = QListWidgetItem(f"{config['description']} ({config.get('port', 'N/A')})")
                item.setData(Qt.ItemDataRole.UserRole, config)
                self.list_widget.addItem(item)
            
    def get_selected_configs(self):
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.list_widget.selectedItems()]

class PumpActionDialog(QDialog):
    def __init__(self, pump_configs, parent=None, show_params=True):
        super().__init__(parent)
        self.setWindowTitle("设置泵参数")
        self.pump_configs = pump_configs
        
        layout = QFormLayout(self)
        self.pump_select = QComboBox()
        self.pump_select.addItems([p['id'] for p in self.pump_configs])
        layout.addRow("选择泵:", self.pump_select)

        self.speed_input = QLineEdit("100.0")
        self.flow_input = QLineEdit("5.0")
        
        if show_params:
            layout.addRow("转速 (RPM):", self.speed_input)
            layout.addRow("流量 (ml/min):", self.flow_input)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

class DelayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加延时步骤")
        layout = QFormLayout(self)
        self.duration_input = QLineEdit("5.0")
        layout.addRow("延时 (秒):", self.duration_input)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

# --- 控制面板 ---
class ControlPanel(QMainWindow):
    def __init__(self, title, device_configs, resource_manager, system_name):
        super().__init__()
        self.setWindowTitle(title)
        self.device_configs = device_configs
        self.resource_manager = resource_manager
        self.system_name = system_name

        self.device_widgets = {}
        self.curves = {}
        self.command_queue, self.status_queue, self.log_queue, self.process = None, None, None, None
        
        self.start_time = time.time()
        self.data = {'time': []}
        for dev_conf in self.device_configs:
            dev_id = dev_conf['id']
            if 'pump' in dev_id:
                self.data[f"{dev_id}_speed"] = []
                self.data[f"{dev_id}_flow"] = []
                # 只为前2个通道创建数据存储
                for i in range(1, 3):
                    self.data[f"{dev_id}_ch{i}_voltage"] = []
                    self.data[f"{dev_id}_ch{i}_current"] = []

        self._init_ui()
        self._start_backend()

    def _init_ui(self):
        manual_group = self._create_manual_group()
        protocol_group = self._create_protocol_group()
        plot_group = self._create_plot_group()
        log_group = self._create_log_group()

        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(manual_group)
        top_splitter.addWidget(protocol_group)
        top_splitter.setSizes([600, 500])

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(plot_group)
        main_splitter.addWidget(log_group)
        main_splitter.setSizes([200, 400, 200])

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(main_splitter)
        self.setCentralWidget(central_widget)
        self._connect_signals()

    def _create_manual_group(self):
        group = QGroupBox("手动独立控制")
        grid = QGridLayout()
        row = 0
        for config in self.device_configs:
            dev_id = config['id']
            # ★★★ 修改点 1：为泵增加方向控制的下拉框 ★★★
            if 'pump' in dev_id:
                is_peristaltic = 'kamoer' in dev_id or 'lange' in dev_id
                
                # 创建方向选择下拉框
                direction_box = QComboBox()
                direction_box.addItems(["正转", "反转"])

                self.device_widgets[dev_id] = {
                    'input': QLineEdit("100.0" if is_peristaltic else "5.0"),
                    'set_btn': QPushButton("设置"),
                    'start_btn': QPushButton("启动"),
                    'stop_btn': QPushButton("停止"),
                    'status': QLabel("状态: 未知"),
                    'direction_box': direction_box  # 将下拉框存入字典
                }
                grid.addWidget(QLabel(f"泵: {config['description']}:"), row, 0)
                # 为新控件增加布局
                grid.addWidget(self.device_widgets[dev_id]['direction_box'], row, 1)
                grid.addWidget(QLabel("转速/流量:"), row, 2)
                grid.addWidget(self.device_widgets[dev_id]['input'], row, 3)
                grid.addWidget(self.device_widgets[dev_id]['set_btn'], row, 4)
                grid.addWidget(self.device_widgets[dev_id]['start_btn'], row, 5)
                grid.addWidget(self.device_widgets[dev_id]['stop_btn'], row, 6)
                grid.addWidget(self.device_widgets[dev_id]['status'], row, 7, 1, 2)
                row += 1
            elif 'power' in dev_id:
                # 电源部分保持不变
                self.device_widgets[dev_id] = {
                    'ch_select': QComboBox(),
                    'volt_input': QLineEdit("5.0"),
                    'curr_input': QLineEdit("1.0"),
                    'set_ch_btn': QPushButton("设置CH"),
                    'output_btn': QPushButton("打开总输出"),
                    'status': QLabel("状态: 未知")
                }
                self.device_widgets[dev_id]['ch_select'].addItems(["1", "2"])
                self.device_widgets[dev_id]['output_btn'].setCheckable(True)
                grid.addWidget(QLabel(f"电源: {config['description']}:"), row, 0)
                grid.addWidget(self.device_widgets[dev_id]['ch_select'], row, 1)
                grid.addWidget(QLabel("V:"), row, 2)
                grid.addWidget(self.device_widgets[dev_id]['volt_input'], row, 3)
                grid.addWidget(QLabel("A:"), row, 4)
                grid.addWidget(self.device_widgets[dev_id]['curr_input'], row, 5)
                grid.addWidget(self.device_widgets[dev_id]['set_ch_btn'], row, 6)
                grid.addWidget(self.device_widgets[dev_id]['output_btn'], row, 7)
                status_row = row + 1
                grid.addWidget(self.device_widgets[dev_id]['status'], status_row, 0, 1, 8)
                row += 2
        
        grid.setColumnStretch(9, 1)
        group.setLayout(grid)
        return group
        
    def _create_protocol_group(self):
        group = QGroupBox("自动化协议编辑器")
        layout = QHBoxLayout()
        toolbox = QVBoxLayout(); toolbox.addWidget(QLabel("1. 添加步骤:"))
        self.add_start_pump_btn = QPushButton("启动/设置泵")
        self.add_stop_pump_btn = QPushButton("停止泵")
        self.add_delay_btn = QPushButton("延时")
        toolbox.addWidget(self.add_start_pump_btn); toolbox.addWidget(self.add_stop_pump_btn)
        toolbox.addWidget(self.add_delay_btn); toolbox.addStretch()
        sequence = QVBoxLayout(); 
        sequence.addWidget(QLabel("2. 编辑流程:")); self.protocol_list_widget = QListWidget()
        edit_buttons = QHBoxLayout(); 
        self.remove_step_btn = QPushButton("删除"); 
        self.move_up_btn = QPushButton("上移"); 
        self.move_down_btn = QPushButton("下移"); 
        edit_buttons.addWidget(self.remove_step_btn); 
        edit_buttons.addStretch(); edit_buttons.addWidget(self.move_up_btn); 
        edit_buttons.addWidget(self.move_down_btn)
        sequence.addWidget(self.protocol_list_widget); 
        sequence.addLayout(edit_buttons)
        actions = QVBoxLayout(); 
        actions.addWidget(QLabel("3. 执行与保存:"))
        self.run_protocol_button = QPushButton("执行协议"); 
        self.load_protocol_button = QPushButton("从文件加载..."); 
        self.save_protocol_button = QPushButton("保存到文件..."); 
        self.save_data_button = QPushButton("保存数据(CSV)"); 
        self.save_chart_button = QPushButton("保存图表(PNG)"); 
        self.stop_all_button = QPushButton("!! 全部紧急停止 !!"); 
        self.stop_all_button.setStyleSheet("background-color: #d9534f; color: white;")
        actions.addWidget(self.run_protocol_button); 
        actions.addWidget(self.load_protocol_button); 
        actions.addWidget(self.save_protocol_button); 
        actions.addStretch(); 
        actions.addWidget(self.save_data_button); 
        actions.addWidget(self.save_chart_button); 
        actions.addStretch(); 
        actions.addWidget(self.stop_all_button)
        layout.addLayout(toolbox, 1); 
        layout.addLayout(sequence, 3); 
        layout.addLayout(actions, 1)
        group.setLayout(layout)
        return group
    
    def _create_plot_group(self):
        group = QGroupBox("实时数据图表")
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()
        p1 = self.plot_widget.getPlotItem()
        p1.setLabel('bottom', '时间 (s)')
        self.p2_viewbox = pg.ViewBox()
        p1.showAxis('right')
        p1.scene().addItem(self.p2_viewbox)
        p1.getAxis('right').linkToView(self.p2_viewbox)
        self.p2_viewbox.setXLink(p1)
        p1.getAxis('left').setLabel('速度 (RPM) / 电压 (V)', color='#0000FF')
        p1.getAxis('right').setLabel('流量 (ml/min)', color='#FF0000')
        pens = {'kamoer': pg.mkPen('b', width=2, style=Qt.PenStyle.SolidLine), 'oushisheng': pg.mkPen('r', width=2, style=Qt.PenStyle.SolidLine), 'power': pg.mkPen('g', width=2, style=Qt.PenStyle.DashLine)}
        for config in self.device_configs:
            dev_id = config['id']
            if 'kamoer' in dev_id or 'lange' in dev_id: self.curves[dev_id] = p1.plot(pen=pens['kamoer'], name=f"{config['description']}-速度")
            elif 'plunger' in dev_id: curve = pg.PlotDataItem(pen=pens['oushisheng'], name=f"{config['description']}-流量"); self.p2_viewbox.addItem(curve); self.curves[dev_id] = curve
            elif 'power' in dev_id: self.curves[dev_id] = p1.plot(pen=pens['power'], name=f"{config['description']}-电压")
        def update_views(): self.p2_viewbox.setGeometry(p1.getViewBox().sceneBoundingRect()); self.p2_viewbox.linkedViewChanged(p1.getViewBox(), self.p2_viewbox.XAxis)
        update_views()
        p1.getViewBox().sigResized.connect(update_views)
        layout = QVBoxLayout(); layout.addWidget(self.plot_widget); group.setLayout(layout)
        return group
    
    def _create_log_group(self):
        group = QGroupBox("后台日志"); self.log_display = QTextEdit(); self.log_display.setReadOnly(True)
        layout = QVBoxLayout(); layout.addWidget(self.log_display); group.setLayout(layout)
        return group

    def _connect_signals(self):
        for dev_id, widgets_dict in self.device_widgets.items():
            if 'pump' in dev_id:
                widgets_dict['start_btn'].clicked.connect(lambda _, p=dev_id: self.on_start_pump(p))
                widgets_dict['stop_btn'].clicked.connect(lambda _, p=dev_id: self.on_stop_pump(p))
                widgets_dict['set_btn'].clicked.connect(lambda _, p=dev_id: self.on_set_pump_params(p))
                # ★★★ 修改点 2：连接下拉框的信号到新的处理函数 ★★★
                widgets_dict['direction_box'].currentTextChanged.connect(lambda _, p=dev_id: self.on_set_direction(p))
            elif 'power' in dev_id:
                widgets_dict['set_ch_btn'].clicked.connect(lambda _, p=dev_id: self.on_set_power_channel(p))
                widgets_dict['output_btn'].clicked.connect(lambda _, p=dev_id: self.on_toggle_power_output(p))
        
        self.add_start_pump_btn.clicked.connect(self.on_add_start_set_pump); self.add_stop_pump_btn.clicked.connect(self.on_add_stop_pump); self.add_delay_btn.clicked.connect(self.on_add_delay); self.remove_step_btn.clicked.connect(self.on_remove_step); self.move_up_btn.clicked.connect(self.on_move_up); self.move_down_btn.clicked.connect(self.on_move_down); self.run_protocol_button.clicked.connect(self.on_run_protocol); self.save_protocol_button.clicked.connect(self.on_save_protocol_to_file); self.load_protocol_button.clicked.connect(self.on_load_protocol_from_file); self.stop_all_button.clicked.connect(self.on_stop_all); self.save_data_button.clicked.connect(self.on_save_data); self.save_chart_button.clicked.connect(self.on_save_chart)

    def _start_backend(self):
        self.command_queue, self.status_queue, self.log_queue = multiprocessing.Queue(), multiprocessing.Queue(), multiprocessing.Queue()
        controller = SystemController(self.device_configs, self.command_queue, self.status_queue, self.log_queue)
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
            status_data = None
            while not self.status_queue.empty(): status_data = self.status_queue.get_nowait()
            if status_data:
                if 'error' in status_data: QMessageBox.critical(self, "后台错误", status_data['error']); return
                if 'info' in status_data: QMessageBox.information(self, "后台通知", status_data['info'])
                
                elapsed_time = time.time() - self.start_time; self.data['time'].append(elapsed_time)
                
                for dev_conf in self.device_configs:
                    dev_id = dev_conf['id']
                    dev_status = status_data['devices'].get(dev_id, {})
                    
                    if 'pump' in dev_id:
                        is_running = dev_status.get('is_running', False)
                        value = dev_status.get('speed_rpm', dev_status.get('flow_rate_ml_min', 0.0))
                        self.device_widgets[dev_id]['status'].setText(f"状态: {'运行中' if is_running else '已停止'} | 值: {value:.2f}")
                        
                        self.data[f"{dev_id}_speed"].append(dev_status.get('speed_rpm', 0.0))
                        self.data[f"{dev_id}_flow"].append(dev_status.get('flow_rate_ml_min', 0.0))
                        
                        if dev_id in self.curves:
                            data_to_plot = self.data[f"{dev_id}_speed"] if 'kamoer' in dev_id or 'lange' in dev_id else self.data[f"{dev_id}_flow"]
                            self.curves[dev_id].setData(self.data['time'], data_to_plot)
                    
                    elif 'power' in dev_id:
                        output_on = dev_status.get('output_on', False)
                        ch1_v = dev_status.get('ch1_voltage', 0.0)
                        ch1_c = dev_status.get('ch1_current', 0.0)
                        status_text = f"CH1 V: {ch1_v:.2f}, A: {ch1_c:.3f} | 输出: {'已打开' if output_on else '已关闭'}"
                        self.device_widgets[dev_id]['status'].setText(status_text)
                        self.device_widgets[dev_id]['output_btn'].setChecked(output_on)
                        self.device_widgets[dev_id]['output_btn'].setText("关闭总输出" if output_on else "打开总输出")
                        self.data[f"{dev_id}_ch1_voltage"].append(ch1_v)
                        self.data[f"{dev_id}_ch1_current"].append(ch1_c)
                        if dev_id in self.curves: self.curves[dev_id].setData(self.data['time'], self.data[f"{dev_id}_ch1_voltage"])
        except Empty: pass
        except Exception as e: print(f"[{self.windowTitle()}] 更新UI时出错: {e}")

    # --- ★★★ 修改点 3：添加新的事件处理函数并修改旧的 ★★★ ---
    def on_start_pump(self, pump_id):
        """处理“启动”按钮点击事件"""
        try:
            widget_set = self.device_widgets[pump_id]
            # 从下拉框读取方向
            direction_text = widget_set['direction_box'].currentText()
            direction_param = 'reverse' if direction_text == '反转' else 'forward'
            
            params = {'pump_id': pump_id, 'direction': direction_param}
            
            # 根据泵类型读取速度或流量
            if 'kamoer' in pump_id or 'lange' in pump_id:
                params['speed'] = float(widget_set['input'].text())
            elif 'plunger' in pump_id:
                params['flow_rate'] = float(widget_set['input'].text())
                
            self.command_queue.put({'type': 'start_pump', 'params': params})
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数字！")

    def on_set_direction(self, pump_id):
        """处理方向下拉框变化事件，用于实时切换方向"""
        widget_set = self.device_widgets[pump_id]
        direction_text = widget_set['direction_box'].currentText()
        direction_param = 'reverse' if direction_text == '反转' else 'forward'
        
        # 使用 set_pump_params 指令来动态改变方向
        params = {'pump_id': pump_id, 'direction': direction_param}
        self.command_queue.put({'type': 'set_pump_params', 'params': params})

    def on_set_pump_params(self, pump_id):
        # 这个函数现在只负责设置速度/流量，方向由独立的下拉框控制
        try:
            widget_set = self.device_widgets[pump_id]
            params = {'pump_id': pump_id}
            if 'kamoer' in pump_id or 'lange' in pump_id:
                params['speed'] = float(widget_set['input'].text())
            elif 'plunger' in pump_id:
                params['flow_rate'] = float(widget_set['input'].text())
            self.command_queue.put({'type': 'set_pump_params', 'params': params})
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数字！")

    def on_stop_pump(self, pump_id):
        self.command_queue.put({'type': 'stop_pump', 'params': {'pump_id': pump_id}})

    def on_set_power_channel(self, device_id):
        try:
            widgets = self.device_widgets[device_id]
            channel = int(widgets['ch_select'].currentText()); voltage = float(widgets['volt_input'].text()); current = float(widgets['curr_input'].text())
            self.command_queue.put({'type': 'set_power_voltage', 'params': {'device_id': device_id, 'channel': channel, 'voltage': voltage}})
            self.command_queue.put({'type': 'set_power_current', 'params': {'device_id': device_id, 'channel': channel, 'current': current}})
        except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的数字！")

    def on_toggle_power_output(self, device_id):
        widgets = self.device_widgets[device_id]; enable = widgets['output_btn'].isChecked()
        self.command_queue.put({'type': 'set_power_output', 'params': {'device_id': device_id, 'enable': enable}})
        
    def on_save_data(self):
        filename, _ = QFileDialog.getSaveFileName(self, "保存数据", "", "CSV Files (*.csv)"); 
        if filename:
            try: pd.DataFrame(self.data).to_csv(filename, index=False); QMessageBox.information(self, "成功", f"数据已保存到 {filename}")
            except Exception as e: QMessageBox.critical(self, "错误", f"保存数据失败: {e}")

    def on_save_chart(self):
        filename, _ = QFileDialog.getSaveFileName(self, "保存图表", "", "PNG Files (*.png);;JPG Files (*.jpg)"); 
        if filename:
            try: ImageExporter(self.plot_widget.getPlotItem()).export(filename); QMessageBox.information(self, "成功", f"图表已保存到 {filename}")
            except Exception as e: QMessageBox.critical(self, "错误", f"保存图表失败: {e}")

    def on_add_start_set_pump(self):
        dialog = PumpActionDialog([c for c in self.device_configs if 'pump' in c['id']], self)
        if dialog.exec():
            pump_id = dialog.pump_select.currentText(); params = {}
            if 'kamoer' in pump_id: params['speed'] = float(dialog.speed_input.text())
            else: params['flow_rate'] = float(dialog.flow_input.text())
            msg_box = QMessageBox(self); msg_box.setText(f"为 {pump_id} 添加什么步骤？"); start_btn = msg_box.addButton("启动泵", QMessageBox.ButtonRole.ActionRole); set_btn = msg_box.addButton("设置参数", QMessageBox.ButtonRole.ActionRole); msg_box.addButton(QMessageBox.StandardButton.Cancel); msg_box.exec()
            if msg_box.clickedButton() == start_btn: self._add_step_to_list({'command': 'start_pump', 'pump_id': pump_id, 'params': params})
            elif msg_box.clickedButton() == set_btn: self._add_step_to_list({'command': 'set_pump_params', 'pump_id': pump_id, 'params': params})
    
    def on_add_stop_pump(self):
        dialog = PumpActionDialog([c for c in self.device_configs if 'pump' in c['id']], self, show_params=False)
        if dialog.exec(): self._add_step_to_list({'command': 'stop_pump', 'pump_id': dialog.pump_select.currentText()})
    
    def on_add_delay(self):
        dialog = DelayDialog(self)
        if dialog.exec():
            try: self._add_step_to_list({'command': 'delay', 'duration': float(dialog.duration_input.text())})
            except ValueError: QMessageBox.warning(self, "输入错误", "请输入有效的数字！")

    def _add_step_to_list(self, command_dict):
        item = QListWidgetItem(self.generate_description_from_command(command_dict)); item.setData(Qt.ItemDataRole.UserRole, command_dict); self.protocol_list_widget.addItem(item)
    
    def on_remove_step(self):
        for item in self.protocol_list_widget.selectedItems(): self.protocol_list_widget.takeItem(self.protocol_list_widget.row(item))
            
    def on_move_up(self):
        row = self.protocol_list_widget.currentRow(); 
        if row > 0: item = self.protocol_list_widget.takeItem(row); self.protocol_list_widget.insertItem(row - 1, item); self.protocol_list_widget.setCurrentRow(row - 1)

    def on_move_down(self):
        row = self.protocol_list_widget.currentRow(); 
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
        target_desc = app.main_window.device_descriptions.get(target_id, target_id)
        if cmd_type in ['start_pump', 'set_pump_params']:
            action = "启动" if cmd_type == 'start_pump' else "设置"; params = command.get('params', {});
            param_str = ", ".join([f"{k}: {v}" for k, v in params.items()]); 
            desc = f"{action}泵: {target_desc}, 参数: {param_str}"
        elif cmd_type == 'stop_pump': desc = f"停止泵: {target_desc}"
        elif cmd_type == 'delay': desc = f"延时: {command.get('duration', 0)} 秒"
        elif cmd_type == 'stop_all': desc = "全部紧急停止"
        return desc
    
    def on_stop_all(self):
        self.command_queue.put({'type': 'stop_all'})

    def closeEvent(self, event):
        device_ids = [c['id'] for c in self.device_configs]
        self.resource_manager.release_devices(device_ids)
        if self.system_name in app.main_window.control_systems:
            del app.main_window.control_systems[self.system_name]
        self.timer.stop()
        if self.process and self.process.is_alive():
            self.command_queue.put({'type': 'shutdown'})
            self.process.join(timeout=3)
            if self.process.is_alive():
                self.process.terminate()
        super().closeEvent(event)


# --- 主启动器窗口 ---
class MainWindow(QMainWindow):
    def __init__(self, resource_manager):
        super().__init__()
        self.setWindowTitle("实验控制中心")
        self.resource_manager = resource_manager
        self.control_systems = {}
        self.device_descriptions = {dev['id']: dev['description'] for dev_list in DEVICE_POOL.values() if isinstance(dev_list, list) for dev in dev_list if isinstance(dev, dict) and 'id' in dev}
        self.main_power_config = None
        self.main_power_process = None
        self.main_power_widgets = {}
        if DEVICE_POOL.get('power_supplies'):
            self.main_power_config = DEVICE_POOL['power_supplies'][0]
            self.resource_manager.lock_devices([self.main_power_config['id']])
            self._start_main_power_backend()
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        power_group = self._create_power_group()
        main_layout.addWidget(power_group)
        launcher_group = QGroupBox("系统与调试")
        launcher_layout = QHBoxLayout()
        self.start_sys_a_btn = QPushButton("启动控制系统 A")
        self.start_sys_b_btn = QPushButton("启动控制系统 B")
        self.debug_device_btn = QPushButton("调试单个设备")
        launcher_layout.addWidget(self.start_sys_a_btn)
        launcher_layout.addWidget(self.start_sys_b_btn)
        launcher_layout.addWidget(self.debug_device_btn)
        launcher_group.setLayout(launcher_layout)
        main_layout.addWidget(launcher_group)
        self.start_sys_a_btn.clicked.connect(lambda: self.launch_system('System A'))
        self.start_sys_b_btn.clicked.connect(lambda: self.launch_system('System B'))
        self.debug_device_btn.clicked.connect(self.launch_debugger)

    def _start_main_power_backend(self):
        if not self.main_power_config: return
        self.main_power_command_queue = multiprocessing.Queue()
        self.main_power_status_queue = multiprocessing.Queue()
        self.main_power_log_queue = multiprocessing.Queue()
        controller = SystemController([self.main_power_config], self.main_power_command_queue, self.main_power_status_queue, self.main_power_log_queue)
        self.main_power_process = multiprocessing.Process(target=controller.run)
        self.main_power_process.start()
        self.main_power_timer = QTimer(self)
        self.main_power_timer.setInterval(1000)
        self.main_power_timer.timeout.connect(self.update_main_power_ui)
        self.main_power_timer.start()

    def _create_power_group(self):
        group = QGroupBox("总电源控制")
        layout = QGridLayout()
        if not self.main_power_config:
            layout.addWidget(QLabel("未在 system_config.py 中配置电源设备。"))
            group.setLayout(layout)
            group.setEnabled(False)
            return group
        self.main_power_widgets = {'ch_select': QComboBox(), 'volt_input': QLineEdit("5.0"), 'curr_input': QLineEdit("1.0"), 'set_ch_btn': QPushButton("设置参数"), 'output_btn': QPushButton("打开总电源"), 'status_label': QLabel("状态: 未知")}
        self.main_power_widgets['ch_select'].addItems(["1", "2"])
        self.main_power_widgets['output_btn'].setCheckable(True)
        layout.addWidget(QLabel("通道:"), 0, 0); layout.addWidget(self.main_power_widgets['ch_select'], 0, 1); 
        layout.addWidget(QLabel("电压 (V):"), 0, 2); layout.addWidget(self.main_power_widgets['volt_input'], 0, 3); 
        layout.addWidget(QLabel("电流 (A):"), 0, 4); layout.addWidget(self.main_power_widgets['curr_input'], 0, 5); 
        layout.addWidget(self.main_power_widgets['set_ch_btn'], 0, 6); 
        layout.addWidget(self.main_power_widgets['output_btn'], 0, 7); 
        layout.addWidget(self.main_power_widgets['status_label'], 1, 0, 1, 8); 
        layout.setColumnStretch(8, 1)
        self.main_power_widgets['set_ch_btn'].clicked.connect(self.on_set_main_power_params)
        self.main_power_widgets['output_btn'].clicked.connect(self.on_toggle_main_power)
        group.setLayout(layout)
        return group

    def update_main_power_ui(self):
        try:
            status_data = None
            while not self.main_power_status_queue.empty(): status_data = self.main_power_status_queue.get_nowait()
            if status_data and self.main_power_config['id'] in status_data['devices']:
                power_status = status_data['devices'][self.main_power_config['id']]
                print(f"[UI] 收到电源状态: {power_status}") # 调试输出
                output_on = power_status.get('output_on', False)
                status_text_parts = []
                for i in range(1, 3): v = power_status.get(f'ch{i}_voltage', 0.0); c = power_status.get(f'ch{i}_current', 0.0); status_text_parts.append(f"CH{i}: {v:.2f}V/{c:.3f}A")
                status_text = " | ".join(status_text_parts) + f" | 总输出: {'打开' if output_on else '关闭'}"
                self.main_power_widgets['status_label'].setText(status_text)
                self.main_power_widgets['output_btn'].setChecked(output_on)
                self.main_power_widgets['output_btn'].setText("关闭总电源" if output_on else "打开总电源")
                if output_on: self.main_power_widgets['output_btn'].setStyleSheet("background-color: #5cb85c;")
                else: self.main_power_widgets['output_btn'].setStyleSheet("")
        except Empty: pass
        except Exception as e: print(f"[主窗口] 更新总电源UI失败: {e}")

    def on_set_main_power_params(self):
        try:
            dev_id = self.main_power_config['id']; 
            channel = int(self.main_power_widgets['ch_select'].currentText()); 
            voltage = float(self.main_power_widgets['volt_input'].text()); 
            current = float(self.main_power_widgets['curr_input'].text())
            self.main_power_command_queue.put({'type': 'set_power_voltage', 'params': {'device_id': dev_id, 'channel': channel, 'voltage': voltage}})
            self.main_power_command_queue.put({'type': 'set_power_current', 'params': {'device_id': dev_id, 'channel': channel, 'current': current}})
        except (ValueError, KeyError) as e: QMessageBox.warning(self, "输入错误", f"请输入有效的数字！错误: {e}")

    def on_toggle_main_power(self, checked):
        if self.main_power_config:
            dev_id = self.main_power_config['id']
            self.main_power_command_queue.put({'type': 'set_power_output', 'params': {'device_id': dev_id, 'enable': checked}})
    
    def closeEvent(self, event):
        if self.main_power_process and self.main_power_process.is_alive():
            print("正在关闭总电源控制器...")
            self.main_power_command_queue.put({'type': 'shutdown'})
            self.main_power_process.join(timeout=2)
            if self.main_power_process.is_alive(): self.main_power_process.terminate()
        super().closeEvent(event)
        
    def launch_system(self, system_name):
        if system_name in self.control_systems: self.control_systems[system_name].activateWindow(); return
        dialog = DeviceSelectionDialog(self.resource_manager, mode='system', parent=self)
        if dialog.exec():
            selected_configs = dialog.get_selected_configs()
            if not selected_configs: QMessageBox.warning(self, "未选择", "您没有选择任何设备。"); return
            self.resource_manager.lock_devices([c['id'] for c in selected_configs])
            title = f"{system_name} ({', '.join([c['id'] for c in selected_configs])})"
            control_panel = ControlPanel(title, selected_configs, self.resource_manager, system_name)
            self.control_systems[system_name] = control_panel; control_panel.show()
            
    def launch_debugger(self):
        dialog = DeviceSelectionDialog(self.resource_manager, mode='debug', parent=self)
        if dialog.exec():
            selected_configs = dialog.get_selected_configs(); 
            if not selected_configs: return
            config = selected_configs[0]; device_id = config['id']; debug_id = f"debug_{device_id}"
            if debug_id in self.control_systems: self.control_systems[debug_id].activateWindow(); return
            self.resource_manager.lock_devices([device_id])
            title = f"设备调试: {config['description']}"
            control_panel = ControlPanel(title, [config], self.resource_manager, debug_id)
            self.control_systems[debug_id] = control_panel; control_panel.show()

# --- 程序主入口 ---
if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    resource_manager = ResourceManager(DEVICE_POOL)
    app.main_window = MainWindow(resource_manager)
    app.main_window.show()
    sys.exit(app.exec())