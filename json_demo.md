
详细讲解如何编写自动化协议（JSON 文件），并提供几个实用的例子

-----

### Part 1: 如何编写协议 (JSON 文件) 及实例

协议文件本质上是一个 **JSON (JavaScript Object Notation)** 文件。您可以把它看成是一个 Python 的列表（List），列表中的每一个元素是一个 Python 字典（Dictionary），代表自动化流程中的一个步骤。

#### 编写规则：

1.  **严格的 JSON 格式**：

      * 所有字符串（包括键和值）都必须使用**双引号 `"`**，不能用单引号 `'`。
      * 每个键值对 `"key": "value"` 之后用逗号 `,` 分隔，但列表或字典的**最后一个元素后面不能有逗号**。
      * 整个文件内容必须被一个方括号 `[` ... `]` 包围，代表一个列表。
      * 纯数据格式：JSON 文件只能包含数据（对象、数组、字符串、数字、布尔值、null），不能包含函数、变量或注释。

2.  **步骤字典的结构**：
    每个步骤（字典）必须包含一个 `"command"` 键，用来告诉控制器要执行什么操作。根据指令不同，还可能需要其他键：

      * `"pump_id"`: (对于大多数指令) 指定要操作的泵的ID，这个ID必须与 `system_config.py` 文件中定义的 `id` 完全一致。
      * `"params"`: (对于需要参数的指令) 一个嵌套的字典，包含要传递给泵的参数，例如 `"speed"` 或 `"flow_rate"`。
      * `"duration"`: (只用于 `"delay"` 指令) 指定延时的秒数。

-----




#### 实例讲解

这里提供三个从简单到复杂的协议实例，您可以将它们保存为 `.json` 文件后直接加载使用。

**实例 1：顺序清洗流程 (Sequential Flush)**

这个协议模拟了一个简单的清洗过程：先用蠕动泵快速冲洗5秒，然后停止；接着用柱塞泵以低流速推送液体10秒。两个泵完全按顺序工作。

`protocol_sequential_flush.json`:

```json
[
    {
        "command": "start_pump",
        "pump_id": "peristaltic_1",
        "params": {
            "speed": 300
        }
    },
    {
        "command": "delay",
        "duration": 5
    },
    {
        "command": "stop_pump",
        "pump_id": "peristaltic_1"
    },
    {
        "command": "delay",
        "duration": 2
    },
    {
        "command": "start_pump",
        "pump_id": "plunger_pump",
        "params": {
            "flow_rate": 1.0
        }
    },
    {
        "command": "delay",
        "duration": 10
    },
    {
        "command": "stop_pump",
        "pump_id": "plunger_pump"
    }
]
```

**实例 2：混合与动态变速 (Mixing and Ramping)**

这个协议模拟了一个混合反应：先启动柱塞泵输送溶剂，3秒后启动蠕动泵加入反应物。两者同时运行一段时间后，动态提高蠕动泵的加入速度，以加快反应。最后同时停止。

`protocol_mixing_ramp.json`:

```json
[
    {
        "command": "start_pump",
        "pump_id": "plunger_pump",
        "params": {
            "flow_rate": 5.0
        }
    },
    {
        "command": "delay",
        "duration": 3
    },
    {
        "command": "start_pump",
        "pump_id": "peristaltic_1",
        "params": {
            "speed": 80
        }
    },
    {
        "command": "delay",
        "duration": 15
    },
    {
        "command": "set_pump_params",
        "pump_id": "peristaltic_1",
        "params": {
            "speed": 150
        }
    },
    {
        "command": "delay",
        "duration": 10
    },
    {
        "command": "stop_all"
    }
]
```

**实例 3：脉冲式加料 (Pulsing Feed)**

这个协议通过重复的“启动-延时-停止”步骤，模拟蠕动泵的脉冲式加料，常用于需要精确控制少量多次加入的场景。

`protocol_pulsing_feed.json`:

```json
[
    {
        "command": "start_pump",
        "pump_id": "peristaltic_1",
        "params": { "speed": 250 }
    },
    {
        "command": "delay",
        "duration": 1
    },
    {
        "command": "stop_pump",
        "pump_id": "peristaltic_1"
    },
    {
        "command": "delay",
        "duration": 3
    },
    {
        "command": "start_pump",
        "pump_id": "peristaltic_1",
        "params": { "speed": 250 }
    },
    {
        "command": "delay",
        "duration": 1
    },
    {
        "command": "stop_pump",
        "pump_id": "peristaltic_1"
    },
    {
        "command": "delay",
        "duration": 3
    },
    {
        "command": "start_pump",
        "pump_id": "peristaltic_1",
        "params": { "speed": 250 }
    },
    {
        "command": "delay",
        "duration": 1
    },
    {
        "command": "stop_pump",
        "pump_id": "peristaltic_1"
    }
]

