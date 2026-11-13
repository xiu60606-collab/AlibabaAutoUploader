"""独立测试窗口及线程安全的输入调试面板。"""
import os
import sys
from PySide6.QtCore import Signal,Slot,QThread,Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QLineEdit,QPlainTextEdit,QDoubleSpinBox
from automation.input_controller import InputController,Action
from automation.windows import WindowService

class DoubleButton(QPushButton):
    double_clicked=Signal()
    def mouseDoubleClickEvent(self,event):
        self.double_clicked.emit();super().mouseDoubleClickEvent(event)

class InputTestWindow(QWidget):
    start_requested=Signal()
    def __init__(self):
        super().__init__(None,Qt.WindowType.Window)
        self.setWindowTitle(f'AlibabaAutoUploader INPUT TEST {os.getpid()}')
        self.resize(600,550)
        box=QVBoxLayout(self)
        box.addWidget(QLabel('独立输入测试；不操作卖家客户端。先手动绑定，再点击下方开始。'))
        self.single=QPushButton('单击测试');self.double=DoubleButton('双击测试')
        self.text=QLineEdit();self.chinese=QLineEdit()
        self.scroll=QPlainTextEdit('\n'.join(f'滚动测试行 {i}' for i in range(100)));self.scroll.setReadOnly(True)
        self.result=QLabel('等待测试')
        self.start=QPushButton('在本测试窗口开始')
        self.emergency=QPushButton('紧急停止')
        for w in (self.single,self.double,self.text,self.chinese,self.scroll,self.result,self.start,self.emergency):box.addWidget(w)
        self.single.clicked.connect(lambda:self.result.setText('已收到单击'))
        self.double.double_clicked.connect(lambda:self.result.setText('已收到双击'))
        self.text.textChanged.connect(lambda text:self.result.setText('英文框：'+text))
        self.chinese.textChanged.connect(lambda text:self.result.setText('Unicode 框：'+text))
        self.scroll.verticalScrollBar().valueChanged.connect(lambda v:self.result.setText(f'滚动位置：{v}'))
        self.start.clicked.connect(self.start_requested)
        self.running=False
    def closeEvent(self,event):
        if self.running:self.emergency.click();event.ignore();return
        super().closeEvent(event)

class InputWorker(QThread):
    message=Signal(str)
    def __init__(self,controller,actions,parent):super().__init__(parent);self.controller,self.actions=controller,actions
    def run(self):self.controller.run(self.actions,self.message.emit)

class InputPanel(QWidget):
    def __init__(self,get_target,parent=None):
        super().__init__(parent);self.get_target=get_target;self.worker=None;self.controller=None;self.target=None
        self.test=InputTestWindow();self.test.hide()
        box=QVBoxLayout(self);box.addWidget(QLabel('输入控制测试 · 仅允许独立测试窗口'))
        row=QHBoxLayout();self.open=QPushButton('打开测试窗口');self.bind=QPushButton('绑定手动选中目标');self.start=QPushButton('开始（转到测试窗）')
        for b in (self.open,self.bind,self.start):row.addWidget(b)
        box.addLayout(row)
        row=QHBoxLayout();self.pause=QPushButton('暂停');self.resume=QPushButton('继续');self.stop=QPushButton('停止');self.emergency=QPushButton('紧急停止')
        for b in (self.pause,self.resume,self.stop,self.emergency):row.addWidget(b)
        box.addLayout(row)
        self.delay=QDoubleSpinBox();self.delay.setRange(0,5);self.delay.setValue(0.3);self.delay.setPrefix('操作延迟 秒：');box.addWidget(self.delay)
        self.state=QLabel('未绑定目标');box.addWidget(self.state)
        self.logs=QPlainTextEdit();self.logs.setReadOnly(True);self.logs.setMaximumHeight(100);box.addWidget(self.logs)
        self.open.clicked.connect(self.test.show)
        self.bind.clicked.connect(self.bind_target)
        self.start.clicked.connect(self.show_start)
        self.test.start_requested.connect(self.begin)
        for button,method in ((self.pause,'pause'),(self.resume,'resume'),(self.stop,'stop'),(self.emergency,'emergency_stop'),(self.test.emergency,'emergency_stop')):
            button.clicked.connect(lambda checked=False,m=method:self.control(m))
        if sys.platform!='win32':
            self.state.setText('macOS 仅可查看测试窗口；Windows 输入功能不支持')
            for b in (self.bind,self.start,self.pause,self.resume,self.stop,self.emergency,self.test.start):b.setEnabled(False)
    def record(self,text):self.state.setText(text);self.logs.appendPlainText(text)
    def bind_target(self):
        if self.worker:return
        try:
            target=self.get_target()
            if target is None:raise ValueError('请先在窗口列表中手动选择独立测试窗口')
            if target.hwnd!=int(self.test.winId()) or target.pid!=os.getpid():raise ValueError('只允许本软件测试窗口，拒绝客户端或其他窗口')
            WindowService().inspect(target.hwnd,target.pid)
            self.target=target;self.record(f'已绑定：{target.title} / {target.hwnd} / PID {target.pid}')
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception('绑定失败');self.target=None;self.record(str(exc))
    def show_start(self):
        self.test.show();self.record('请手动切换到测试窗口，点击“在本测试窗口开始”')
    def begin(self):
        if self.worker is not None:return
        try:
            if self.target is None or self.get_target()!=self.target:raise ValueError('目标变化或未绑定，请重新选择并绑定')
            self.controller=InputController(self.target,int(self.test.winId()),self.delay.value())
            def point(w):
                p=w.mapToGlobal(w.rect().center());return p.x(),p.y()
            actions=(Action('move',point(self.test.single)),Action('click',point(self.test.single)),Action('double_click',point(self.test.double)),Action('click',point(self.test.text)),Action('ascii','Test123'),Action('key','tab'),Action('click',point(self.test.chinese)),Action('unicode','中文 Unicode 测试'),Action('move',point(self.test.scroll)),Action('scroll',-3))
            self.worker=InputWorker(self.controller,actions,self);self.worker.message.connect(self.record);self.worker.finished.connect(self.on_input_finished)
            self.test.running=True;self.bind.setEnabled(False);self.start.setEnabled(False);self.test.start.setEnabled(False);self.worker.start()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception('输入任务启动失败');self.record(str(exc))
    def control(self,method):
        if self.controller:
            getattr(self.controller,method)();self.record('请求：'+method)
    @Slot()
    def on_input_finished(self):
        worker=self.worker;self.worker=None;worker.deleteLater();self.test.running=False
        self.bind.setEnabled(True);self.start.setEnabled(True);self.test.start.setEnabled(True)
    def stop_for_close(self):
        if self.worker:
            self.controller.stop();self.record('正在停止，请线程结束后再次关闭');return False
        self.test.close();return True
