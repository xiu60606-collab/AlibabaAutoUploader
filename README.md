# Alibaba Product Auto Uploader

面向 Windows 10/11 x64 的阿里巴巴国际站卖家客户端自动上传产品软件。
默认自动填写并保存产品草稿；正式发布必须经过明确的人工确认。

## 开发环境

- 开发平台：macOS Apple Silicon。
- Python：统一使用 **3.13.12**，开发、测试、GitHub Actions 和 Windows EXE 打包保持一致。
- 运行和实际验证平台：独立 Windows x64 电脑。
- Windows EXE 必须在 Windows 上使用 Python 3.13.12 和 PyInstaller 打包并验证。

所有开发遵循 AGENTS.md。现有虚拟环境是否符合要求须以实际解释器版本为准；版本配置不会自动迁移虚拟环境。

## 启动与测试

在项目根目录激活 Python 3.13.12 虚拟环境后运行：

```sh
python main.py
python -m pytest -q
```

依赖分别由 requirements.txt 和 requirements-dev.txt 管理。
当前界面版本为 0.1.0，提供六个导航页面和只读模拟产品表格。
所有导入、任务控制和客户端连接功能尚未启用，不会执行真实上传。
macOS 离屏界面测试通过；Windows 实机运行、EXE 打包和客户端自动化尚未验证。

## macOS 桌面启动

在 Finder 中双击项目内的 `启动软件.command`，或在正常桌面终端执行 `./启动软件.command`。
入口使用项目自己的 .venv，检查 Python 3.13.12，清除测试用的离屏后端设置。
若自动执行环境报告 PasteBoard / hiservices-xpcservice 连接错误，应在已登录的图形桌面会话启动。
该入口尚未在正常桌面会话中实测，不代表原生显示问题已解决。

## Windows x64 依赖安装（PowerShell）

先进入包含 main.py 和 requirements.txt 的项目根目录。下面路径是示例，请替换为 Windows 上实际项目位置；不要使用 macOS 的 /Users 路径。

```powershell
Set-Location "C:\Projects\AlibabaAutoUploader"
Get-Location
Get-Item .\requirements.txt, .\requirements-dev.txt
py -3.13 -c "import sys, struct; print(sys.version); assert sys.version_info[:3] == (3, 13, 12); assert struct.calcsize('P') == 8"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
# 开发和测试环境额外安装：
.\.venv\Scripts\python.exe -m pip install -r .\requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
```

已有 .venv 时先检查其解释器版本，避免覆盖有效环境；不要复制 macOS 的 .venv 到 Windows。
上面的安装命令不要求激活环境。若在其他目录安装，使用 requirements 文件的完整绝对路径。
若 Get-Item 提示文件不存在，请检查克隆/解压路径、分支和副本完整性；不要通过全局安装解决文件路径错误。
Git 仓库可用 `git ls-files requirements.txt requirements-dev.txt` 检查跟踪状态。

当前运行依赖仅为 PySide6、openpyxl、Pillow，开发测试额外使用 pytest；sqlite3 属于 Python 标准库。
当前没有实际使用 pywin32 等 Windows 专属库，因此不添加无用途依赖。未来确有需要时使用环境标记，例如 `pywin32; sys_platform == "win32"`。
