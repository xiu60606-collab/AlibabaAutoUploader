"""异步读取、虚拟表格预览、明确确认后的内存导入。"""
import logging
from pathlib import Path
from threading import Event
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QFileDialog, QTableView, QPlainTextEdit, QLabel, QHeaderView, QMessageBox, QDialog, QDialogButtonBox
from core.database import ProductDatabase, application_database_path
import sqlite3
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
    imported = Signal()
    root_changed = Signal(object)

    def __init__(self, parent=None, store=None) -> None:
        super().__init__(parent)
        self.store = store if store is not None else ProductDatabase(application_database_path())
        self.worker: Reader | None = None
        box = QVBoxLayout(self)
        box.addWidget(QLabel('产品导入 · 预览确认后保存到本机用户数据目录'))
        box.addWidget(QLabel('确认后保存 SQLite；不会触发上传。支持最多 100000 行。'))
        self.image_root_button = QPushButton('选择图片根目录')
        self.image_root_label = QLabel('未选择图片根目录')
        box.addWidget(self.image_root_button); box.addWidget(self.image_root_label)
        self.image_root_button.clicked.connect(self.select_image_root)
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
            result = self.model.result
            count = len(result.products)
            if isinstance(self.store, ProductDatabase):
                diff = self.store.differences(result)
                policy = 'cancel'
                if diff:
                    choice = QMessageBox(self)
                    choice.setWindowTitle('重复产品处理')
                    choice.setText(f'发现 {len(diff)} 个已有编号，请明确选择处理方式。')
                    skip = choice.addButton('跳过重复产品', QMessageBox.ButtonRole.AcceptRole)
                    update = choice.addButton('更新已有产品', QMessageBox.ButtonRole.ActionRole)
                    choice.addButton('取消导入', QMessageBox.ButtonRole.RejectRole)
                    choice.exec()
                    if choice.clickedButton() is skip:
                        policy = 'skip'
                    elif choice.clickedButton() is update:
                        dialog = QDialog(self)
                        dialog.setWindowTitle('更新差异预览 · 确认后覆盖所列字段')
                        dialog.resize(760, 520)
                        layout = QVBoxLayout(dialog)
                        text = QPlainTextEdit(); text.setReadOnly(True)
                        text.setPlainText('\n'.join(f'{pid} · {field}: {old} → {new}' for pid,changes in diff.items() for field,(old,new) in changes.items()) or '重复产品字段相同，无字段差异。')
                        layout.addWidget(text)
                        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
                        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
                        layout.addWidget(buttons)
                        if dialog.exec() != QDialog.DialogCode.Accepted:return
                        policy = 'update'
                    else:return
                count = self.store.import_products(result, policy, diff if policy == 'update' else None)
            else:
                self.store.commit(result)
        except (ValueError, sqlite3.Error, OSError) as exc:
            logger.exception("数据库导入失败")
            self.errors.setPlainText(str(exc))
            return
        self.confirm.setEnabled(False)
        self.model.replace(ImportResult())
        self.errors.setPlainText(f'已确认保存 {count} 个产品至产品存储；未执行上传。')
        self.imported.emit()
        logger.info('已确认产品导入 %d 个产品', count)

    def cancel_import(self) -> None:
        if self.worker is not None:
            self.worker.cancel.set()
        self.model.replace(ImportResult())
        self.confirm.setEnabled(False)
        self.errors.setPlainText('已取消待导入批次，已保存内存产品不变。')

    def select_image_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, '选择图片根目录')
        if selected:
            self.image_root_label.setText(selected)
            self.root_changed.emit(Path(selected))
