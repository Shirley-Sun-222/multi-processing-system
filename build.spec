# -*- mode: python ; coding: utf-8 -*-

# build.spec
# 这是为 "控制系统" 项目定制的 PyInstaller 配置文件。

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('system_config.json', '.')],  # 关键：将配置文件包含进来
    hiddenimports=['pyvisa_py'],          # 关键：添加 pyvisa 的后端，防止找不到设备
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='控制系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,         # 关键：这是一个GUI程序，设为 False 以隐藏命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='控制系统'
)
