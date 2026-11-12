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
