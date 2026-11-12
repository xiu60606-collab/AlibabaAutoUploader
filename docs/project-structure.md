# 基础结构与路径约定

- ui：PySide6 桌面界面。
- core：产品管理与任务管理。
- automation：未来的 Windows 自动化模块。
- config：随软件分发的非敏感默认配置。
- resources：图标与静态资源。
- templates：界面识别模板。
- tests：自动化测试。
- docs：开发文档。
- main.py：软件启动入口，启动 PySide6 主窗口。

## 路径与数据存储

所有文件系统路径使用 pathlib.Path，不依赖当前工作目录或硬编码用户目录。
config/settings.json 为分发默认值，不应在运行时写入安装目录。
未来运行数据（用户配置、数据库、日志等）使用 PySide6.QtCore.QStandardPaths
的 AppLocalDataLocation 获取用户可写目录，再转换为 pathlib.Path。
使用前应设置稳定的应用名称、检查返回路径并创建所需目录。
本阶段不创建运行数据目录，也不实现配置读写或存储模块。
账号密码不得明文保存，产品资料和个人数据不得提交到 Git。
正式发布必须在实际操作前获得明确人工确认，不能仅凭配置值授权。

## 当前范围

已实现界面框架及模拟产品展示；尚未实现产品持久化、任务管理、客户端自动化或 Windows 打包。
