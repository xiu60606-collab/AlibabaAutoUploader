"""仅授权本应用测试窗口的有限输入控制器。"""
from dataclasses import dataclass
import logging
import sys
import time
from threading import Event, Lock
from automation.windows import WindowService, WindowInfo, PlatformNotSupported

logger=logging.getLogger(__name__)

@dataclass(frozen=True)
class Action:
    kind: str
    value: object = None

class InputStopped(RuntimeError):
    pass

class InputController:
    """单任务控制器；不得用生产客户端 HWND 作为允许目标。"""
    def __init__(self,target: WindowInfo,allowed_hwnd: int,delay: float=0.3) -> None:
        if sys.platform!='win32':raise PlatformNotSupported('输入控制仅支持 Windows')
        if target.hwnd!=allowed_hwnd:raise ValueError('本阶段只允许本软件独立测试窗口')
        if not 0<=delay<=5:raise ValueError('操作延迟须为 0–5 秒')
        import pyautogui
        import pyperclip
        self.gui,self.clip=pyautogui,pyperclip
        self.gui.FAILSAFE=True
        self.gui.PAUSE=0.05
        self.service=WindowService()
        self.target,self.allowed_hwnd,self.delay=target,allowed_hwnd,delay
        self.stop_event=Event();self.paused=Event();self.lock=Lock()
        self.state='待启动';self.deadline=0.0;self.notify=lambda text:None

    def report(self,text: str) -> None:
        logger.info('输入控制：%s',text);self.notify(text)

    def pause(self) -> None:self.paused.set()
    def resume(self) -> None:self.paused.clear()
    def stop(self) -> None:self.stop_event.set()
    def emergency_stop(self) -> None:
        self.stop_event.set()
        logger.warning('输入控制：请求紧急停止')

    def checkpoint(self) -> WindowInfo:
        if self.stop_event.is_set():raise InputStopped('已停止')
        if time.monotonic()>self.deadline:raise InputStopped('任务超过 120 秒，已停止')
        current=self.service.inspect(self.target.hwnd,self.target.pid)
        if current.title!=self.target.title or current.process!=self.target.process or current.minimized:
            raise InputStopped('窗口身份或状态变化，请重新选择目标')
        if self.service.gui.GetForegroundWindow()!=self.target.hwnd:
            raise InputStopped('目标失去前台焦点，已停止；请重新选择')
        self.gui.failSafeCheck()
        return current

    def wait(self,seconds: float) -> None:
        end=time.monotonic()+seconds
        for _ in range(2500):
            self.checkpoint()
            if not self.paused.is_set() and time.monotonic()>=end:return
            self.stop_event.wait(0.05)
        raise InputStopped('等待超时')

    def point(self,value) -> tuple[int,int]:
        current=self.checkpoint();x,y=value
        left,top,right,bottom=current.rect
        if not left<=x<right or not top<=y<bottom:raise InputStopped('坐标超出目标窗口')
        hit=self.service.gui.WindowFromPoint((x,y))
        if hit!=current.hwnd and self.service.gui.GetAncestor(hit,2)!=current.hwnd:
            raise InputStopped('坐标被其他窗口遮挡，已停止')
        return x,y

    def run(self,actions: tuple[Action,...],notify=None) -> None:
        """在调用线程执行；状态由信号回调送至界面，不接触 QWidget。"""
        if not self.lock.acquire(blocking=False):raise RuntimeError('任务已运行，拒绝重复启动')
        self.notify=notify or (lambda text:None)
        self.deadline=time.monotonic()+120
        try:
            if len(actions)>100:raise ValueError('一次最多 100 个动作')
            self.state='运行中';self.report(self.state)
            for action in actions:
                self.wait(self.delay)
                self.checkpoint()
                kind,value=action.kind,action.value
                if kind in {'move','click','double_click'}:
                    x,y=self.point(value)
                    if kind=='move':self.gui.moveTo(x,y,duration=0)
                    elif kind=='click':self.gui.click(x,y)
                    else:
                        self.gui.click(x,y);self.wait(0.1)
                        x,y=self.point(value);self.gui.click(x,y)
                elif kind=='scroll':
                    self.point(self.gui.position());self.gui.scroll(int(value))
                elif kind=='key':
                    if value not in {'tab','enter','backspace','left','right','home','end'}:raise ValueError('不允许的测试按键')
                    self.gui.press(value)
                elif kind=='ascii':
                    if not str(value).isascii():raise ValueError('英文输入仅支持 ASCII')
                    for char in str(value):
                        self.wait(0);self.gui.write(char)
                elif kind=='unicode':
                    old=self.clip.paste()
                    try:
                        self.clip.copy(str(value));self.checkpoint()
                        self.gui.hotkey('ctrl','v');self.wait(0.2)
                    finally:
                        if self.clip.paste()==str(value):self.clip.copy(old)
                else:raise ValueError('不支持的动作')
                self.report(f'完成动作：{kind}')
            self.state='完成';self.report(self.state)
        except Exception as exc:
            self.stop_event.set();self.state='已停止 / 错误'
            logger.exception('输入任务终止');self.report(f'{self.state}：{type(exc).__name__}: {exc}')
        finally:self.lock.release()
