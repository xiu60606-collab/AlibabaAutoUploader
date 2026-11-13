# 第五阶段任务一：Windows 窗口识别

## 范围

自动上传页 → 自动化调试 · Windows 窗口识别。
仅在用户触发时枚举当前交互桌面的可见顶层窗口（包括无标题窗口），表格展示标题、句柄、PID、进程路径、窗口位置/尺寸及最小化状态。
标题关键词不区分大小写，仅用于候选过滤；空关键词列出全部可见窗口。必须手动核对并选择目标。
目标由 HWND 和 PID 标识，每次状态/激活前重新检查；目标关闭或句柄被其他 PID 复用会拒绝。
同一进程中句柄复用无法仅靠 HWND/PID 完全排除，操作前仍须核对。
选择窗口不代表真实客户端已建立业务连接，主界面未连接状态保持不变。

后台线程执行枚举、状态及激活操作，期间按钮禁用并暂缓关闭调试窗口。
恢复最小化窗口后尝试 SetForegroundWindow，最多等待 2 秒并核对实际前台句柄；Windows 可因前台权限限制拒绝，不绕过限制、不强制管理员运行。
进程路径读取权限不足会在日志记录原因，显示不可读取，仍允许显示其余信息。
无鼠标键盘输入、自动填写、阿里巴巴 API、草稿保存或发布操作。
macOS 可以导入模块并打开提示界面，但不能实例化 Windows 服务，按钮禁用。pywin32 使用延迟导入。

## 依赖

requirements.txt 新增 pywin32==312; sys_platform == "win32"。PyPI 提供 CPython 3.13 Windows 包：
https://pypi.org/project/pywin32/
Windows 前台激活限制说明：
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow

## Windows PowerShell 验收

在已登录 Windows 10/11 x64 桌面打开 PowerShell，切换实际项目根目录：

```powershell
Set-Location "C:\Projects\AlibabaAutoUploader"
py -3.13 -c "import sys,struct; print(sys.version); assert sys.version_info[:3] == (3,13,12); assert struct.calcsize('P') == 8"
# 仅当还没有有效虚拟环境时创建；不要复制 macOS 的 .venv
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import win32gui,win32api,win32process; print('pywin32 imports OK')"
.\.venv\Scripts\python.exe -m pytest -q tests\test_windows.py
.\.venv\Scripts\python.exe -c "from automation.windows import WindowService; print(*WindowService().enumerate(), sep='\n')"
.\.venv\Scripts\python.exe main.py
```

test_windows.py 通过替身检查逻辑，不能视作真实 Win32 通过。既有完整套件包含明确要求 macOS 的历史验收测试，Windows 本次使用上述定向测试和人工验收。

人工验收：
1. 打开记事本和卖家客户端，进入自动上传页调试入口，枚举全部窗口，核对标题、PID、矩形、尺寸；显示权限不足信息属于可接受降级。
2. 用实际客户端标题关键词筛选，不假定固定窗口标题。修改关键词应得到对应候选，无匹配时列表为空。
3. 选择客户端窗口，检测存在及最小化状态；最小化后再检测，点击尝试激活。成功应实际前置，否则应显示拒绝/未激活，不能伪报成功。
4. 关闭选定窗口再检测，必须报告失效，不能自动改选其他窗口。多候选必须由人工选择。
5. 检查调试窗口关闭、六页导航、第四阶段导入/查询仍正常；确认没有点击产品、填写或发布行为。

## 验证边界

本次 macOS 替身测试与第四阶段回归不能证明 Windows 实机窗口识别已通过。
尚待 Windows 实机验证：真实 pywin32 导入、权限差异、DPI/多屏坐标、客户端实际标题、前台激活和真实桌面响应。
没有创建版本标签或推送 GitHub。

本次执行结果：macOS / Python 3.13.12，完整 pytest 最终 54 passed、1 skipped，退出码 0；pip check 通过。修正了新增对话框测试的 Qt 清理顺序，未把先前退出异常算作通过。

## 独立调试页面补充

主窗口新增第七项“自动化调试”，原六个业务页面仍保留，也保留自动上传页的弹窗入口。
页面显示窗口枚举和检测结果，macOS 明确不支持并禁用操作；服务和界面执行入口均检查平台。
手动选择后重新枚举将清除旧目标，避免误用过期选择。激活失败显示系统异常或未激活说明。
本次增补测试覆盖手动选择、刷新清除和未激活消息；已有业务回归继续运行。

Windows 验收推荐从左侧“自动化调试”进入，点击枚举，按标题搜索并手动选择客户端，检测最小化状态并尝试激活；关闭客户端后再次检查应明确报告失效。
操作不产生鼠标点击、键盘输入、上传、发布或安全验证绕过。

## 本地副本核查与扫描错误

本模块文件为 automation/windows.py，调试界面为 ui/window_debug.py，测试为 tests/test_windows.py。
如 Windows 副本 automation 中仅有 __init__.py，应先核对文件同步与实际项目路径，不能据本机实现认定 Windows 副本已有模块。
扫描部分窗口失败（窗口退出、进程路径权限不足）会同时记录日志并在扫描结果下显示诊断，不将失败静默当成全部识别成功。
标题关键词首尾空格会去除。修改工作区文件不代表已提交或同步到 Windows；本任务不进行 Git 提交、标签或推送。
