# 第三阶段验收测试报告

日期：2026-11-12（Asia/Shanghai）。范围：桌面界面，不进入第四阶段。

## 环境与结论

macOS Apple Silicon（Darwin / arm64），项目 .venv，Python 3.13.12。
PySide6 6.12.0、openpyxl 3.1.5、Pillow 13.0.0、pytest 9.2.0 导入通过。
最终 pytest 结果：7 passed，1 skipped。桌面原生显示验收尚未完成。

| 验收项 | 结果及边界 |
| --- | --- |
| Python 3.13.12 | 通过，测试断言实际解释器版本及虚拟环境 |
| 必要依赖导入 | 四项均通过；pip check 无依赖冲突 |
| main.py 启动 | 离屏独立进程执行真实入口、进入事件循环，通过 |
| 主窗口显示 | 离屏可见性和非空渲染通过；原生桌面待人工检查 |
| 六页导航 | 逐一点击按钮、检查页面索引及选中状态，通过 |
| 模拟产品数据 | 三行六列逐单元格对照模拟数据，通过 |
| 表格缩放 | 1024×680 与 1440×900 下视口宽度随窗口变化，通过；默认尺寸及最小尺寸通过 |
| 进度条 | 可见、范围 0–100、初始 0、提示尚未执行，通过 |
| 关闭退出 | 独立进程关闭主窗口后事件循环返回 0，通过；有超时保护 |
| 未捕获异常 | 最终通过路径中未发现 Python traceback 或回调异常；不代表所有未来操作无异常 |
| 跨平台依赖 | 当前运行清单无 Windows 专属直接依赖；入口、ui、core 静态检查无指定平台专属或真实自动化导入；Windows 实机未验证 |
| 模拟结果边界 | 演示标识、模拟状态、未连接提示、成功与失败计数为 0、未执行日志、上传记录提示及禁用操作按钮均通过 |

## 执行命令

在项目根目录：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -B -m pytest -v -p no:cacheprovider
.venv/bin/python -m pip check
```

首轮结果为 6 通过、2 失败：测试包装器错误地向 Qt 静态 exec 传入 self，已修正测试；另一次原生 cocoa 尝试因 PasteBoard / macOS 桌面 XPC 服务连接无效而退出（退出码 -6）。后者无法据此判断软件在正常桌面上的表现。原生测试保留为显式启用项，默认跳过并报告原因，未当作通过。
最终离屏启动及关闭测试通过。Qt 曾输出字体别名性能警告，不属于 Python 未捕获异常。

## 人工检查步骤（尚未执行）

1. 在已登录的 macOS 图形桌面终端进入项目目录，激活 .venv，执行 python main.py；确认窗口出现、中文清晰，无乱码或字体缺失。
2. 检查标题、版本、演示模式、未连接状态及四个统计卡片；确认模拟标识清晰，没有真实上传成功提示。
3. 点击六个导航页，检查页面内容、选中样式、切换流畅度；逐一确认未启用功能说明。
4. 从默认 1280×800 缩至最小 1024×680，再放大；检查标题、表头、按钮无重叠或裁切，必要时可滚动查看表格，中文和高 DPI 显示正常。
5. 检查产品三行六列、0% 进度、最近日志；确认底部五个操作按钮均不可执行。
6. 点击窗口关闭按钮，确认终端恢复提示符、无残留软件窗口和 traceback；重复启动关闭。

可在正常桌面终端额外执行原生自动检查：

```sh
RUN_NATIVE_GUI_TESTS=1 .venv/bin/python -B -m pytest -v -p no:cacheprovider tests/test_phase3_acceptance.py -k cocoa
```

## 文件变更与未完成项

新增 tests/test_phase3_acceptance.py 和本报告；未修改业务代码。
尚未完成原生桌面视觉人工验收、Windows 10/11 x64 实机验证、EXE 打包验证。
Excel 导入、任务执行、配置编辑、产品持久化与真实客户端自动化仍未实现，不属于本次验收通过范围。
本次未操作真实客户端或鼠标键盘；Qt 测试事件仅作用于本软件控件。

## 再次复查（2026-11-12，Asia/Shanghai）

重新执行完整离屏测试：7 passed，1 skipped（0.76 秒）；Python 3.13.12，pip check 再次通过。
随后显式启用原生测试，并非仅依据默认跳过结果判断：

```sh
RUN_NATIVE_GUI_TESTS=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_phase3_acceptance.py -k cocoa
```

实际结果：1 failed，4 deselected。原生子进程退出码 -6，stderr 再次出现 PasteBoard -4960 与 com.apple.hiservices-xpcservice 连接无效。
因此本次结论仍为：离屏自动验收通过，原生窗口启动/显示/关闭验收未通过当前执行环境中的测试，须在正常 macOS 图形桌面终端执行上述测试并完成人工步骤。
这属于原生进程异常退出，不能以“没有 Python traceback”宣称所有启动方式无异常；也不能仅凭这些错误确定是应用缺陷或环境限制。
本次仅更新本报告，未修改软件代码或放宽测试断言，未进入第四阶段。

## 原生启动故障定位与处理

在不导入项目任何模块的子进程执行 `QApplication([])`：offscreen 退出码 0；cocoa 退出码 -6，并出现同样 PasteBoard / hiservices-xpcservice 错误。
这将故障定位到当前执行上下文中的 Qt 原生桌面初始化，未发现由主窗口业务代码引起的证据。
新增 `启动软件.command` 作为正常图形桌面会话入口：动态定位项目、校验虚拟环境版本、清除测试后端变量，再执行 main.py。
修正原生测试跳过文案：未启用属于未验证，不应将跳过直接当作环境能力判断。
当前会话不能完成原生桌面连接修复；需从 Finder/本机桌面终端启动并验证。未将测试改成自动离屏回退，未声称原生测试通过。

## 启动入口调整后复测（2026-11-12 16:02，Asia/Shanghai）

- Python 3.13.12；启动软件.command 的 zsh 语法检查通过。
- 完整离屏测试：7 passed，1 skipped，耗时 0.78 秒。
- pip check：No broken requirements found。
- 显式原生 cocoa 测试：1 failed，4 deselected，耗时 0.34 秒；原生子进程退出码 -6，仍出现 PasteBoard -4960 和 hiservices-xpcservice 连接无效。
- 因此新增桌面启动入口并未证明当前执行环境的原生启动故障已解决。该脚本本次仅验证语法，未在 Finder 正常桌面会话中执行。
- 本轮只更新验收报告，没有修改应用或测试代码，未进入第四阶段。原生桌面显示和关闭仍待人工验证。
