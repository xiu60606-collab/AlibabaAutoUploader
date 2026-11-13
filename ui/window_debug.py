"""用户主动触发的窗口调试界面。"""
from PySide6.QtCore import QAbstractTableModel,QModelIndex,Qt,QThread,Signal,Slot
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QPushButton,QTableView,QLabel,QAbstractItemView
from automation.windows import WindowService

class WindowModel(QAbstractTableModel):
    HEADERS=('窗口标题','句柄','PID','进程路径','位置 (x,y)','尺寸','最小化')
    def __init__(self,parent=None):super().__init__(parent);self.windows=[]
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.windows)
    def columnCount(self,parent=QModelIndex()):return 0 if parent.isValid() else 7
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role==Qt.ItemDataRole.DisplayRole:
            w=self.windows[index.row()]
            return (w.title,hex(w.hwnd),str(w.pid),w.process,str(w.rect[:2]),str(w.size),'是' if w.minimized else '否')[index.column()]
        return None
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if role==Qt.ItemDataRole.DisplayRole:return self.HEADERS[section] if orientation==Qt.Orientation.Horizontal else section+1

class DebugWorker(QThread):
    result=Signal(object)
    error=Signal(str)
    def __init__(self,operation,parent=None):super().__init__(parent);self.operation=operation
    def run(self):
        try:self.result.emit(self.operation())
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception('窗口调试失败');self.error.emit(str(exc))

class WindowDebug(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle('Windows 客户端窗口识别调试');self.resize(1000,600)
        self.worker=None;self.target=None
        box=QVBoxLayout(self)
        box.addWidget(QLabel('只识别窗口；选择不代表客户端已连接。不执行填写、点击或发布。'))
        line=QHBoxLayout();self.keyword=QLineEdit();self.keyword.setPlaceholderText('标题关键词，例如 Alibaba 或 阿里巴巴；留空列出全部可见窗口')
        self.refresh=QPushButton('枚举 / 查找窗口');line.addWidget(self.keyword);line.addWidget(self.refresh);box.addLayout(line)
        self.model=WindowModel(self);self.table=QTableView();self.table.setModel(self.model);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);box.addWidget(self.table)
        buttons=QHBoxLayout();self.select=QPushButton('选为目标');self.check=QPushButton('检测目标状态');self.activate=QPushButton('尝试激活目标')
        for b in (self.select,self.check,self.activate):buttons.addWidget(b)
        box.addLayout(buttons);self.message=QLabel('未选择目标');self.message.setWordWrap(True);box.addWidget(self.message)
        self.refresh.clicked.connect(self.scan);self.select.clicked.connect(self.choose);self.check.clicked.connect(lambda:self.status(False));self.activate.clicked.connect(lambda:self.status(True))
        import sys
        if sys.platform!='win32':
            self.message.setText('仅支持 Windows 10/11；macOS 不执行窗口识别或激活。')
            for b in (self.refresh,self.select,self.check,self.activate):b.setEnabled(False)

    def run_operation(self,operation,callback):
        import sys
        if sys.platform != 'win32':
            self.message.setText('仅支持 Windows 10/11；当前系统不执行 Windows 操作。')
            return
        if self.worker is not None:return
        self.worker=DebugWorker(operation,self)
        for b in (self.refresh,self.select,self.check,self.activate):b.setEnabled(False)
        self.worker.result.connect(callback);self.worker.error.connect(self.message.setText);self.worker.finished.connect(self.on_worker_thread_finished);self.worker.start()

    @Slot()
    def on_worker_thread_finished(self) -> None:
        """线程退出后清除引用，延迟释放对象并恢复按钮。"""
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        import sys
        for button in (self.refresh, self.select, self.check, self.activate):
            button.setEnabled(sys.platform == 'win32')

    def scan(self):
        if self.worker is not None:return
        keyword=self.keyword.text();self.target=None
        self.message.setText('正在后台枚举；请手动核对标题及进程后选择目标')
        def operation():
            service = WindowService()
            windows = service.find(keyword)
            return windows, service.warnings
        def completed(result):
            windows, warnings = result
            self.show_windows(windows)
            if warnings:
                self.message.setText(self.message.text() + '\n部分窗口读取失败：\n' + '\n'.join(warnings))
        self.run_operation(operation, completed)

    def show_windows(self,windows):
        self.model.beginResetModel();self.model.windows=windows;self.model.endResetModel()
        self.message.setText(f'发现 {len(windows)} 个候选窗口；尚未选择目标')

    def choose(self):
        index=self.table.currentIndex()
        if index.isValid():
            self.target=self.model.windows[index.row()]
            self.message.setText(f'手动目标：{self.target.title} / {hex(self.target.hwnd)} / PID {self.target.pid}')
        else:
            self.message.setText('请先在窗口列表中选择一行')

    def status(self,activate):
        target=self.target
        if target is None:self.message.setText('请先手动选择目标');return
        def operation():
            service=WindowService()
            if activate:return '激活成功（已核对前台句柄）' if service.activate(target) else '未激活：可能受到 Windows 前台权限限制，请手动切换窗口'
            info=service.inspect(target.hwnd,target.pid)
            return f'窗口存在；最小化：{info.minimized}；标题：{info.title}；尺寸：{info.size}'
        self.run_operation(operation,self.message.setText)

    def done(self,result):
        if self.worker is not None:self.message.setText('检测执行中，请完成后关闭');return
        super().done(result)

    def closeEvent(self, event) -> None:
        """后台操作完成前拒绝关闭，避免销毁仍运行的 QThread。"""
        if self.worker is not None:
            self.message.setText('检测执行中，请完成后关闭')
            event.ignore()
            return
        super().closeEvent(event)
