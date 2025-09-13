@echo off
REM =================================================================
REM  一键打包脚本 (build.bat) - V2 (解决中文乱码)
REM  功能: 自动安装依赖并使用 build.spec 文件打包 Python 程序。
REM  使用: 将此文件放在项目根目录 (与 main.py 同级)，然后双击运行。
REM =================================================================

REM 关键改动：将命令行的代码页切换为 UTF-8 (65001)，以防止显示中文时出现乱码。
chcp 65001 > nul

echo [1/3] 正在检查并安装项目依赖库 (从 requirements.txt)...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo 依赖库安装失败，请检查网络连接或 pip 配置。
    pause
    exit /b %errorlevel%
)

echo.
echo [2/3] 正在检查并安装 PyInstaller...
pip install pyinstaller
if %errorlevel% neq 0 (
    echo.
    echo PyInstaller 安装失败。
    pause
    exit /b %errorlevel%
)


echo.
echo [3/3] 开始使用 PyInstaller 进行打包 (根据 build.spec 配置)...
pyinstaller build.spec

echo.
echo =================================================================
echo.
echo  打包完成!
echo.
echo  您的可执行文件位于本目录下的 `dist` 文件夹中。
echo  文件名: 控制系统.exe
echo.
echo =================================================================
echo.
pause

