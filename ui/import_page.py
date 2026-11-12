"""异步读取、虚拟表格预览、明确确认后的内存导入。"""
import logging
from pathlib import Path
from threading import Event
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QFileDialog, QTableView, QPlainTextEdit, QLabel, QHeaderView
from core.excel_template import FIELDS
from core.excel_importer import read_products, ImportResult, MemoryProductStore

logger = logging.getLogger(__name__)

class PreviewModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.result = ImportResult()

    def replace(self, result: ImportResult) -> None:
        self.beginResetModel()
        self.result = result
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.result.products)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(FIELDS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return str(self.result.products[index.row()].values[index.column()])
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return FIELDS[section] if orientation == Qt.Orientation.Horizontal else section + 1
        return None

class Reader(QThread):
    ready = Signal(object)

    def __init__(self, path: Path, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        self.cancel = Event()

    def run(self) -> None:
        self.ready.emit(read_products(self.path, self.cancel))

class ImportPage(QWidget):
    """保留内存导入批次；取消或校验失败不会修改已保存产品。"""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.store = MemoryProductStore()
        self.worker: Reader | None = None
        box = QVBoxLayout(self)
        box.addWidget(QLabel('产品导入 · 预览确认后仅保存在本次会话内存，退出后丢失'))
        box.addWidget(QLabel('工作台仍展示模拟数据；本页导入不会触发上传。支持最多 100000 行。'))
        line = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        self.choose = QPushButton('选择 Excel 文件')
        self.read = QPushButton('读取文件')
        line.addWidget(self.path, 1)
        line.addWidget(self.choose)
        line.addWidget(self.read)
        box.addLayout(line)
        self.model = PreviewModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        box.addWidget(self.table, 1)
        self.errors = QPlainTextEdit()
        self.errors.setReadOnly(True)
        self.errors.setMaximumHeight(120)
        box.addWidget(self.errors)
        buttons = QHBoxLayout()
        self.confirm = QPushButton('确认导入')
        self.confirm.setEnabled(False)
        self.cancel = QPushButton('取消导入')
        buttons.addWidget(self.confirm)
        buttons.addWidget(self.cancel)
        box.addLayout(buttons)
        self.choose.clicked.connect(self.select_file)
        self.read.clicked.connect(self.start_read)
        self.confirm.clicked.connect(self.commit)
        self.cancel.clicked.connect(self.cancel_import)

    def select_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, '选择产品表格', '', 'Excel (*.xlsx)')
        if selected:
            self.cancel_import()
            self.path.setText(selected)

    def start_read(self) -> None:
        """启动后台读取，期间保持导航和主线程事件循环可响应。"""
        if self.worker is not None:
            return
        if not self.path.text():
            self.errors.setPlainText('第 1 行 [file]：请先选择文件')
            return
        self.model.replace(ImportResult())
        self.confirm.setEnabled(False)
        self.errors.setPlainText('正在后台读取…')
        self.choose.setEnabled(False)
        self.read.setEnabled(False)
        self.worker = Reader(Path(self.path.text()), self)
        self.worker.ready.connect(self.loaded)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def loaded(self, result: ImportResult) -> None:
        if self.worker is not None and self.worker.cancel.is_set():
            return
        self.model.replace(result)
        self.errors.setPlainText('\n'.join(result.errors) if result.errors else f'预览 {len(result.products)} 个产品；尚未保存。')

    def finished(self) -> None:
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        self.choose.setEnabled(True)
        self.read.setEnabled(True)
        self.confirm.setEnabled(bool(self.model.result.products) and not self.model.result.errors)

    def commit(self) -> None:
        if self.worker is not None:
            return
        try:
            self.store.commit(self.model.result)
        except ValueError as exc:
            self.errors.setPlainText(str(exc))
            return
        count = len(self.model.result.products)
        self.confirm.setEnabled(False)
        self.model.replace(ImportResult())
        self.errors.setPlainText(f'已确认保存 {count} 个产品至临时内存；未执行上传。')
        logger.info('已确认内存导入 %d 个产品', count)

    def cancel_import(self) -> None:
        if self.worker is not None:
            self.worker.cancel.set()
        self.model.replace(ImportResult())
        self.confirm.setEnabled(False)
        self.errors.setPlainText('已取消待导入批次，已保存内存产品不变。')
