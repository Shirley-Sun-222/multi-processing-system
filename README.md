
# 中文版 (Chinese Version)

# 实验流体精密控制系统

这是一个为化学或材料科学实验设计的自动化流体精密控制系统。它提供了一个图形用户界面（GUI），用于实时监控和控制多个蠕动泵、柱塞泵以及多通道直流电源，并支持自动化实验流程协议。

 \#\# ✨ 功能特性

  * **图形化界面**: 基于 PyQt6 构建，直观易用，提供主启动器、分系统控制和独立设备调试三种窗口模式。
  * **多进程架构**: 主界面（UI）与设备控制后台（Controller）在不同进程中运行，确保了界面的流畅响应，即使在设备通信繁忙时也不会卡顿。
  * **实时数据监控**: 使用 `pyqtgraph` 实时绘制各设备（如电源电压、电流，泵的转速、流量）的状态曲线，一目了然。
  * **自动化协议**: 支持创建、编辑、保存和加载自动化实验流程。您可以将一系列操作（如启停泵、设置参数、延时）组合成一个协议并一键执行。
  * **灵活的配置系统**:
      * 所有硬件配置（COM 端口、设备地址等）都存储在外部 `system_config.json` 文件中，无需修改代码即可轻松适配不同的硬件连接。
      * 启动器界面内置了配置编辑器，可以直接在图形界面上修改并保存硬件参数。
  * **模块化设备驱动**: 每种设备（不同型号的泵、电源）都有独立的控制器文件，基于统一的基类接口实现，易于扩展和维护。
  * **一键打包**: 提供 `build.bat` 脚本，可使用 PyInstaller 将整个项目打包成独立的 `.exe` 可执行文件，方便在任何 Windows 电脑上部署和运行。

## 📐 系统架构

系统采用经典的多进程生产者-消费者模型，将前端 UI 和后端设备控制解耦。

```
+--------------------------+      (multiprocessing.Queue)      +-----------------------------+
|        主进程 (UI)       |         Command & Status         |      后台子进程 (Controller)    |
|       (main.py)          |                                  |   (system_controller.py)    |
|                          |                                  |                             |
| +----------------------+ |         [用户指令]                  | +-------------------------+   |
| |  Launcher/Control  | |  ---------------------------->   | |     Command Processor   |   |
| |      Windows       | |                                  | | (处理UI发来的指令)      |   |
| +----------------------+ |         [设备状态]                  | +-------------------------+   |
| |   Real-time Plots  | |  <----------------------------   | |      Status Poller      |   |
| |   (数据可视化)     | |                                  | | (轮询所有设备状态)      |   |
| +----------------------+ |                                  | +-------------------------+   |
|                          |                                  | |     Device Drivers      |   |
|                          |                                  | | (与真实硬件通信)        |   |
|                          |                                  | +--+-----------+--------+   |
+--------------------------+                                  +----|---(PyVISA)---|--------+---+
                                                                   |              |
                                                              +----v----+    +-----v-----+
                                                              |  电源   |    |    泵     |
                                                              +---------+    +-----------+
```

1.  **UI 进程 (`main.py`)**: 负责所有用户交互。当用户点击按钮（如“启动泵”）时，它会将一个指令（如 `{'type': 'start_pump', 'params': ...}`）放入**指令队列 (Command Queue)**。同时，它会持续从**状态队列 (Status Queue)** 中获取最新的设备数据来更新图表和状态标签。
2.  **Controller 进程 (`system_controller.py`)**:
      * 启动后，根据配置初始化并连接所有硬件设备。
      * 在一个循环中，它不断地检查指令队列。一旦收到指令，就调用相应的设备驱动执行操作（如通过 `pymodbus` 或 `pyvisa` 发送串口命令）。
      * 它会定期（例如每秒）轮询所有设备的当前状态（电压、是否在运行等），并将这些状态打包放入状态队列，供 UI 进程消费。

这种设计确保了 I/O 密集型的硬件通信不会阻塞用户界面的操作。

## 📂 文件结构

```
/
├── main.py                     # GUI主程序入口，包含所有窗口和UI逻辑
├── system_controller.py        # 后台设备控制核心逻辑
├── config.py                   # 配置文件加载与保存逻辑
├── system_config.json          # 【重要】用户硬件配置文件
├── system_config.py            # 默认的硬件配置 (作为备份)
|
├── base_pump.py                # 泵设备的抽象基类，定义通用接口
├── kamoer_pump_controller.py   # 卡莫尔蠕动泵的具体实现
├── plunger_pump_controller.py  # 欧世盛柱塞泵的具体实现
├── power_supply_controller.py  # 固纬GPD系列电源的具体实现
|
├── requirements.txt            # 项目依赖库列表
├── build.bat                   # 一键打包成EXE的批处理脚本
├── build.spec                  # PyInstaller的配置文件
├── address.py                  # 用于修改泵地址的独立工具脚本
└── 资源指南.md                 # 关于如何打包的详细中文说明
```

## 🚀 如何运行

### 1\. 环境准备

  * **Python**: 确保您已安装 Python 3.8 或更高版本。
  * **克隆仓库**: `git clone https://github.com/Shirley-Sun-222/multi-processing-system.git`
  * **安装依赖**: 强烈建议在虚拟环境中进行。
    ```bash
    # 创建并激活虚拟环境 (可选但推荐)
    python -m venv venv
    source venv/bin/activate  # on Windows: venv\Scripts\activate
    
    # 安装所有必要的库
    pip install -r requirements.txt
    ```

### 2\. 硬件配置

这是最关键的一步。

1.  打开 `system_config.json` 文件。
2.  根据您的实际硬件连接情况，修改每个设备的 `port` 和 `address`。
      * 对于电源，`port` 通常是 `ASRL6::INSTR` 这样的 VISA 资源名。
      * 对于泵，`port` 是 COM 端口号（如 `COM9`），`address` 是其 Modbus 地址。
      * 确保每个设备的 `id` 都是唯一的。

### 3\. 从源码运行

完成配置后，在项目根目录运行主程序：

```bash
python main.py
```

程序会首先显示一个启动器窗口，您可以从中选择要控制的系统或调试单个设备。

### 4\. 打包成 EXE 文件运行

如果您想在没有安装 Python 环境的电脑上运行，可以将其打包成 `.exe` 文件。

1.  确保项目根目录下有 `build.bat` 和 `build.spec` 文件。
2.  **双击运行 `build.bat` 脚本**。
3.  脚本会自动安装 `pyinstaller` 并执行打包命令。
4.  等待打包过程完成。成功后，您会在项目目录下看到一个 `dist` 文件夹。
5.  进入 `dist` 文件夹，找到 `控制系统.exe`，这就是您的独立应用程序。直接双击即可运行。

## 📖 操作指南

1.  **启动器**:

      * 程序启动后首先看到的是启动器窗口。
      * 点击 **“启动 控制电源系统 X”** 按钮来打开对应系统的完整控制界面。
      * 点击 **“调试单个设备”** 按钮，可以选择一个设备（如某个泵或电源）进入专门的调试窗口，进行独立操作和测试。
      * 展开 **“硬件配置”** 面板，可以直接修改设备的端口和地址，点击右下角的 **“保存所有配置”** 按钮即可将更改写入 `system_config.json` 文件。

    <img src=image/主界面.png alt="主界面" style="zoom:50%" />

2.  **系统控制窗口**:

      * 界面分为左右两个子系统（A 和 B），分别对应电源的两个通道。
      * **电源控制**: 可以设置目标电压、电流，并独立开关每个通道的输出。支持定时关闭功能。
      * **泵控制**: 对于每个泵，可以设置其参数（转速/流量），选择方向，并单独启动或停止。
      * **实时图表**: 下方图表会实时显示电压、电流和泵的运行参数。可以导出图表为图片或将数据导出为 Excel。
      * **协议编辑器**:
          * 点击“启动/设置泵”、“停止泵”、“延时”来添加步骤到流程列表中。
          * 可以对列表中的步骤进行删除、上移、下移操作。
          * 点击 **“执行协议”** 来运行整个自动化流程。
          * 使用 **“保存到文件...”** 和 **“从文件加载...”** 来复用您的实验协议。

    <img src=image/电源系统界面.png alt="电源系统界面" style="zoom:50%" />

## 🔧 如何修改与扩展

### 添加一种新的设备

本项目的模块化设计让添加新硬件变得简单。假设您要添加一种新的 "ABC 牌" 泵：

1.  **创建控制器文件**: 在项目中新建一个 `abc_pump_controller.py` 文件。
2.  **继承基类**: 在新文件中，创建一个类 `ABCPump`，让它继承自 `base_pump.py` 中的 `BasePump` 类。
3.  **实现接口**: 您必须实现 `BasePump` 类中定义的所有方法，如 `connect`, `disconnect`, `start`, `stop`, `set_parameters`, `get_status`。在这些方法内部，编写通过串口（或其它方式）与 ABC 泵通信的实际代码。
4.  **注册到工厂**: 打开 `system_controller.py` 文件，在 `device_factory` 函数中，添加一个新的 `elif` 条件：
    ```python
    # in system_controller.py -> device_factory()
    ...
    elif device_type == 'abc_pump':
        from abc_pump_controller import ABCPump # 别忘了导入
        return ABCPump(port=config['port'], unit_address=config['address'])
    ...
    ```
5.  **更新配置**: 现在，您就可以在 `system_config.json` 中添加一个新设备，并将其 `type` 设置为 `"abc_pump"`。程序将能自动识别并创建它。

-----

# English Version

# Automated Fluid Control System

This is an automated fluid control system designed for chemistry or materials science experiments. It provides a graphical user interface (GUI) for real-time monitoring and control of multiple peristaltic pumps, plunger pumps, and multi-channel DC power supplies, and supports automated experimental protocols.

 \#\# ✨ Features

  * **Graphical User Interface**: Built with PyQt6, intuitive and easy to use. Provides three window modes: a main launcher, a sub-system control panel, and an individual device debugger.
  * **Multi-Process Architecture**: The main UI and the device control backend run in separate processes. This ensures a smooth and responsive interface that won't freeze, even during intensive device communication.
  * **Real-time Data Monitoring**: Uses `pyqtgraph` to plot the status of each device (e.g., power supply voltage/current, pump speed/flow rate) in real-time.
  * **Automation Protocol**: Supports creating, editing, saving, and loading automated experimental workflows. You can combine a series of actions (start/stop pump, set parameters, delay) into a protocol and execute it with one click.
  * **Flexible Configuration System**:
      * All hardware configurations (COM ports, device addresses, etc.) are stored in an external `system_config.json` file, making it easy to adapt to different hardware setups without changing the code.
      * The launcher includes a built-in configuration editor to modify and save hardware parameters directly from the GUI.
  * **Modular Device Drivers**: Each device type has its own controller file, implemented based on a unified base class interface, making the system easy to maintain and extend.
  * **One-Click Packaging**: A `build.bat` script is provided to package the entire project into a standalone `.exe` executable using PyInstaller, allowing for easy deployment on any Windows computer.

## 📐 System Architecture

The system employs a classic multi-process producer-consumer model to decouple the front-end UI from the back-end device control.

```
+--------------------------+      (multiprocessing.Queue)      +-----------------------------+
|     Main Process (UI)    |         Command & Status         |   Background Process (Controller) |
|        (main.py)         |                                  |   (system_controller.py)    |
|                          |                                  |                             |
| +----------------------+ |           [User Commands]        | +-------------------------+   |
| |  Launcher/Control  | |  ---------------------------->   | |     Command Processor   |   |
| |      Windows       | |                                  | | (Handles commands from UI)|
| +----------------------+ |           [Device Status]        | +-------------------------+   |
| |   Real-time Plots  | |  <----------------------------   | |      Status Poller      |   |
| |  (Data Visualization)| |                                  | | (Polls status from all) |
| +----------------------+ |                                  | +-------------------------+   |
|                          |                                  | |     Device Drivers      |   |
|                          |                                  | | (Communicate w/ hardware) |
|                          |                                  | +--+-----------+--------+   |
+--------------------------+                                  +----|---(PyVISA)---|--------+---+
                                                                   |              |
                                                              +----v----+    +-----v-----+
                                                              |  Power  |    |   Pumps   |
                                                              | Supply  |    |           |
                                                              +---------+    +-----------+
```

1.  **UI Process (`main.py`)**: Responsible for all user interactions. When a user clicks a button (e.g., "Start Pump"), it puts a command dictionary (e.g., `{'type': 'start_pump', 'params': ...}`) into the **Command Queue**. Concurrently, it continuously fetches the latest device data from the **Status Queue** to update plots and status labels.
2.  **Controller Process (`system_controller.py`)**:
      * Upon startup, it initializes and connects to all hardware devices based on the configuration.
      * In a main loop, it constantly checks the Command Queue. When a command is received, it invokes the appropriate device driver to perform the action (e.g., sending serial commands via `pymodbus` or `pyvisa`).
      * It periodically polls the current status of all devices (voltage, running state, etc.) and puts the aggregated status data into the Status Queue for the UI process to consume.

This design ensures that I/O-intensive hardware communication does not block the user interface.

## 📂 File Structure

```
/
├── main.py                     # Main application entry point, contains all window and UI logic
├── system_controller.py        # Core backend logic for device control
├── config.py                   # Logic for loading and saving configuration files
├── system_config.json          # IMPORTANT: User hardware configuration file
├── system_config.py            # Default hardware configuration (as a fallback)
|
├── base_pump.py                # Abstract base class for pumps, defining a common interface
├── kamoer_pump_controller.py   # Implementation for Kamoer peristaltic pumps
├── plunger_pump_controller.py  # Implementation for Oushisheng plunger pumps
├── power_supply_controller.py  # Implementation for GW Instek GPD-series power supplies
|
├── requirements.txt            # List of project dependencies
├── build.bat                   # Batch script for one-click packaging into an EXE
├── build.spec                  # Configuration file for PyInstaller
├── address.py                  # A standalone utility script to change pump Modbus addresses
└── 资源指南.md                 # A detailed guide on packaging (in Chinese)
```

## 🚀 How to Run

### 1\. Environment Setup

  * **Python**: Ensure you have Python 3.8 or newer installed.
  * **Clone the repository**: `git clone https://github.com/your-username/your-repo-name.git`
  * **Install Dependencies**: It's highly recommended to use a virtual environment.
    ```bash
    # Create and activate a virtual environment (optional but recommended)
    python -m venv venv
    source venv/bin/activate  # on Windows: venv\Scripts\activate
    
    # Install all required libraries
    pip install -r requirements.txt
    ```

### 2\. Hardware Configuration

This is the most crucial step.

1.  Open the `system_config.json` file.
2.  Modify the `port` and `address` for each device according to your actual hardware connections.
      * For the power supply, the `port` is typically a VISA resource name like `ASRL6::INSTR`.
      * For pumps, the `port` is the COM port name (e.g., `COM9`), and the `address` is its Modbus address.
      * Ensure that every device `id` is unique.

### 3\. Run from Source

After configuration is complete, run the main program from the project's root directory:

```bash
python main.py
```

The application will start with a launcher window, from which you can open control panels or debug individual devices.

### 4\. Run as a Packaged EXE

If you want to run the application on a computer without a Python environment, you can package it into an `.exe` file.

1.  Make sure `build.bat` and `build.spec` are in the project root directory.
2.  **Double Click `build.bat` script**.
3.  The script will automatically install `pyinstaller` and execute the packaging process.
4.  Wait for the process to finish. Upon success, a `dist` folder will appear in your project directory.
5.  Navigate into the `dist` folder and find `控制系统.exe`. This is your standalone application. Double-click to run.


## 📖 How to Use

1. **Launcher**:

     * The launcher window appears on startup.
     * Click a **"Launch Control Power System X"** button to open the full control interface for that system.
     * Click **"Debug a Single Device"** to select one device (like a specific pump or the power supply) and open a dedicated debugging window for isolated testing.
     * Expand the **"Hardware Configuration"** panel to modify device ports and addresses directly. Click the **"Save All Configurations"** button in the bottom-right corner to write your changes to `system_config.json`.

   <img src=image/主界面.png alt="主界面" style="zoom:40%" />

   

2. **System Control Window**:

     * The interface is split into two sub-systems (A and B), corresponding to the two channels of the power supply.
     * **Power Control**: Set the target voltage and current, and toggle the output for each channel. A timed-off feature is available.
     * **Pump Control**: For each pump, set its parameters (speed/flow rate), direction, and start/stop it individually.
     * **Real-time Charts**: The plots at the bottom display voltage, current, and pump parameters in real-time. You can export the chart as a PNG image or export the data as an Excel file.
     * **Protocol Editor**:
         * Click "Start/Set Pump", "Stop Pump", or "Add Delay" to add steps to the workflow list.
         * You can select steps in the list to remove them or move them up/down.
         * Click **"Run Protocol"** to execute the entire automated sequence.
         * Use **"Save to File..."** and **"Load from File..."** to reuse your experimental protocols.

   <img src=image/电源系统界面.png alt="电源系统界面" style="zoom:40%" />

## 🔧 How to Modify and Extend

### Adding a New Device

The project's modular design makes it straightforward to add new hardware. For example, to add a new "ABC" brand pump:

1.  **Create a Controller File**: Create a new file named `abc_pump_controller.py` in the project.
2.  **Inherit from the Base Class**: In the new file, create a class `ABCPump` that inherits from the `BasePump` class in `base_pump.py`.
3.  **Implement the Interface**: You must implement all methods defined in the `BasePump` interface, such as `connect`, `disconnect`, `start`, `stop`, `set_parameters`, and `get_status`. Inside these methods, write the actual code to communicate with the ABC pump via serial (or other protocols).
4.  **Register in the Factory**: Open `system_controller.py` and, within the `device_factory` function, add a new `elif` condition:
    ```python
    # in system_controller.py -> device_factory()
    ...
    elif device_type == 'abc_pump':
        from abc_pump_controller import ABCPump # Don't forget to import
        return ABCPump(port=config['port'], unit_address=config['address'])
    ...
    ```
5.  **Update Configuration**: You can now add a new device in `system_config.json` and set its `type` to `"abc_pump"`. The program will now be able to recognize and create it.