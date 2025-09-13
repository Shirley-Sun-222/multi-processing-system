# file: config.py
import json
import os
import sys
from system_config import SYSTEM_SETS # 导入默认配置作为备用

# 定义配置文件的名称
CONFIG_FILE = "system_config.json"

# 全局变量，用于在内存中持有当前配置
CURRENT_CONFIG = []

def get_config_path():
    """获取配置文件的绝对路径，确保打包后也能找到"""
    if hasattr(sys, '_MEIPASS'):
        # 如果是在 PyInstaller 打包后的环境中
        base_path = sys._MEIPASS
    else:
        # 在正常的 Python 环境中
        base_path = os.path.abspath(".")
    return os.path.join(base_path, CONFIG_FILE)

def load_config():
    """
    加载配置。
    优先从 system_config.json 文件加载。如果文件不存在或解析失败，
    则加载 system_config.py 中的默认配置 SYSTEM_SETS。
    """
    global CURRENT_CONFIG
    config_path = get_config_path()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                CURRENT_CONFIG = json.load(f)
                print(f"成功从 {config_path} 加载配置。")
                # 校验加载的配置是否与默认结构一致，防止手动修改json导致出错
                if len(CURRENT_CONFIG) != len(SYSTEM_SETS):
                     print("警告: JSON配置文件中的系统数量与默认配置不匹配，可能导致问题。")
                return
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"加载 {config_path} 失败: {e}。将使用默认配置。")
    
    print("未找到或无法解析JSON配置文件，正在加载默认配置。")
    CURRENT_CONFIG = SYSTEM_SETS
    # 首次加载默认配置后，立即保存一份json，方便用户后续修改
    save_config()


def save_config():
    """
    将当前内存中的配置保存到 system_config.json 文件。
    """
    global CURRENT_CONFIG
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            # 使用 ensure_ascii=False 以正确显示中文
            json.dump(CURRENT_CONFIG, f, indent=4, ensure_ascii=False)
            print(f"配置已成功保存到 {config_path}。")
            return True
    except Exception as e:
        print(f"保存配置到 {config_path} 时出错: {e}")
        return False

# 在模块被导入时，立即执行一次加载操作
load_config()
