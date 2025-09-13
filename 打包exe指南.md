Python 项目打包为 EXE 指南
本指南将引导您如何使用 PyInstaller 将您的“控制系统”项目打包成一个独立的 Windows 可执行文件 (.exe)。

简介
PyInstaller 是一个流行的 Python 程序打包工具。它可以将 Python 应用程序及其所有依赖项捆绑到一个包中。用户无需安装 Python 解释器或任何模块即可运行打包好的程序。

我们将使用一个 .spec 配置文件的方法，这是最可靠、最灵活的打包方式。

步骤一：准备环境
首先，您需要安装 PyInstaller 和项目所需的所有依赖库。为了方便，我已经将这个步骤写在了 build.bat 脚本中。它会自动读取 requirements.txt 文件并安装所有必要的库。

步骤二：理解配置文件 (build.spec)
.spec 文件是 PyInstaller 的“配方”，它告诉 PyInstaller 如何打包您的应用。我已经为您创建了一个 build.spec 文件，其中包含了针对您项目的重要配置：

Analysis 部分:

scripts=['main.py']: 指定了程序的主入口文件是 main.py。

datas=[('system_config.json', '.')]: 这是非常关键的一步。它告诉 PyInstaller 需要将 system_config.json 这个数据文件也包含进来，并放在最终生成目录的根目录下。您的代码经过特殊设计，可以在打包后正确找到这个文件。

hiddenimports=['pyvisa_py']: 有时 PyInstaller 无法自动检测到某些“隐藏”的依赖。pyvisa 库依赖 pyvisa-py 作为后端，我们在这里明确告诉 PyInstaller 要包含它，以防止运行时出错。

pathex: 指定了项目的根目录。

EXE 部分:

name='控制系统': 设置生成的 .exe 文件的主文件名。

console=False: 因为您的程序是一个图形用户界面（GUI）应用，设置为 False 可以在运行时不显示黑色的命令行窗口。这对应于命令行中的 --windowed 或 --noconsole 参数。

步骤三：执行打包
这是最简单的一步。

确保 build.bat, build.spec 这两个文件和您的 main.py 及其他所有项目文件都放在同一个文件夹下。

双击运行 build.bat 文件。

脚本会自动执行以下操作：

安装 requirements.txt 中列出的所有库。

安装 pyinstaller。

调用 pyinstaller 并使用 build.spec 文件中的配置来执行打包。

打包过程可能需要几分钟，请耐心等待。您会在命令行窗口看到大量的输出信息。

步骤四：找到并测试您的 .exe 文件
打包成功后，您的项目文件夹中会多出几个新文件夹，其中最重要的是 dist 文件夹。

进入 dist 文件夹。

您会在这里找到一个名为 控制系统.exe 的文件。

这个 .exe 文件就是最终的成品。您可以将它复制到任何其他 Windows 电脑上运行，而无需再进行任何安装。

故障排除
程序闪退：如果双击 .exe 后程序一闪而过就退出了，通常意味着程序在启动时遇到了错误。您可以打开一个命令行窗口（CMD 或 PowerShell），拖动 .exe 文件进去并回车运行。这样如果程序出错，错误信息会显示在命令行窗口中，方便您定位问题。

文件未找到：如果提示找不到 system_config.json，请检查 build.spec 文件中的 datas 配置是否正确。

模块缺失 (ModuleNotFoundError)：如果提示缺少某个模块，您可以尝试在 build.spec 文件的 hiddenimports 列表中添加这个模块的名称，然后重新运行 build.bat。

命令行出现中文乱码：如果在运行 build.bat 时，窗口中的中文字符显示为乱码，这是由于 Windows 命令行默认的编码页不是 UTF-8 导致的。新版的 build.bat 脚本已在开头添加 chcp 65001 命令来自动解决此问题。