"""Windows 顶层窗口识别；不发送鼠标键盘输入。"""
from dataclasses import dataclass
import logging
import sys
import time

logger = logging.getLogger(__name__)

class PlatformNotSupported(RuntimeError):
    pass

@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    process: str
    rect: tuple[int,int,int,int]
    minimized: bool

    @property
    def size(self) -> tuple[int,int]:
        return self.rect[2]-self.rect[0], self.rect[3]-self.rect[1]

class WindowService:
    """仅 Windows 可实例化；按句柄及 PID 校验手动选定窗口。"""
    def __init__(self) -> None:
        if sys.platform != 'win32':
            raise PlatformNotSupported('窗口识别仅支持 Windows 10/11，当前系统不执行 Windows 操作。')
        try:
            import win32gui
            import win32process
            import win32api
            import win32con
        except ImportError as exc:
            raise RuntimeError('缺少 pywin32，请在项目虚拟环境安装 requirements.txt') from exc
        self.warnings: list[str] = []
        self.gui,self.process,self.api,self.con=win32gui,win32process,win32api,win32con

    def inspect(self, hwnd: int, expected_pid: int | None=None) -> WindowInfo:
        if not self.gui.IsWindow(hwnd):raise ValueError('窗口已关闭或句柄无效，请重新选择')
        _,pid=self.process.GetWindowThreadProcessId(hwnd)
        if expected_pid is not None and pid!=expected_pid:raise ValueError('窗口句柄已被其他进程复用，请重新选择')
        path='不可读取（权限限制或进程退出）'
        try:
            handle=self.api.OpenProcess(0x1000,False,pid)
            try:path=self.process.QueryFullProcessImageName(handle,0)
            finally:handle.Close()
        except Exception as exc:
            logger.warning('无法读取 PID %s 的进程路径：%s',pid,exc)
            self.warnings.append(f'PID {pid}：进程路径不可读取：{exc}')
        return WindowInfo(hwnd,self.gui.GetWindowText(hwnd),pid,path,tuple(self.gui.GetWindowRect(hwnd)),bool(self.gui.IsIconic(hwnd)))

    def enumerate(self) -> list[WindowInfo]:
        self.warnings.clear()
        windows=[]
        deadline=time.monotonic()+5.0
        def callback(hwnd,unused):
            if time.monotonic()>deadline:raise TimeoutError('窗口枚举超过 5 秒，请重试')
            if self.gui.IsWindowVisible(hwnd):
                try:windows.append(self.inspect(hwnd))
                except Exception as exc:
                    logger.warning('枚举窗口 %s 失败：%s',hwnd,exc)
                    self.warnings.append(f'HWND {hex(hwnd)}：枚举失败：{exc}')
            return True
        self.gui.EnumWindows(callback,None)
        return windows

    def find(self, keyword: str) -> list[WindowInfo]:
        """标题匹配仅给候选，不据此自动选择目标。"""
        keyword = keyword.strip()
        if not keyword:return self.enumerate()
        return [w for w in self.enumerate() if keyword.casefold() in w.title.casefold()]

    def activate(self, target: WindowInfo, timeout: float=2.0) -> bool:
        """有限时尝试恢复并激活；不绕过 Windows 前台权限限制。"""
        if not 0<timeout<=5:raise ValueError('激活超时必须在 0–5 秒之间')
        current=self.inspect(target.hwnd,target.pid)
        if current.minimized:self.gui.ShowWindowAsync(target.hwnd,self.con.SW_RESTORE)
        self.gui.SetForegroundWindow(target.hwnd)
        for _ in range(int(timeout/0.05)+1):
            self.inspect(target.hwnd,target.pid)
            if self.gui.GetForegroundWindow()==target.hwnd:return True
            time.sleep(0.05)
        return False
