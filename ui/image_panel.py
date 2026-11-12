"""本地产品图片面板，图片校验在工作线程执行。"""
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QSize, Qt
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QListWidget, QListWidgetItem, QPlainTextEdit
from core.product_images import scan_images, ImageCollection

class ImageReader(QThread):
    ready = Signal(object)
    def __init__(self, root: Path, folder: str, parent=None) -> None:
        super().__init__(parent)
        self.root, self.folder = root, folder
    def run(self) -> None:
        self.ready.emit(scan_images(self.root, self.folder))

class ImagePanel(QWidget):
    """按产品缓存图片顺序和主图，切换产品不写入原文件。"""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.root: Path | None = None
        self.product_id = ''
        self.folder = ''
        self.worker: ImageReader | None = None
        self.cache: dict[str, ImageCollection] = {}
        self.collection = ImageCollection([], [])
        box = QVBoxLayout(self)
        self.root_button = QPushButton('选择产品图片根目录')
        self.root_label = QLabel('未选择根目录；image_folder 为该目录下的相对路径')
        self.root_label.setWordWrap(True)
        box.addWidget(self.root_button);box.addWidget(self.root_label)
        self.info = QLabel('请先在产品导入页确认导入，再选择产品。')
        box.addWidget(self.info)
        self.items = QListWidget();self.items.setIconSize(QSize(80,80))
        self.items.setMaximumHeight(140)
        box.addWidget(self.items)
        self.preview = QLabel('图片预览');self.preview.setMinimumHeight(100)
        box.addWidget(self.preview)
        buttons = QHBoxLayout()
        self.main_button = QPushButton('设为主图');self.up = QPushButton('前移');self.down = QPushButton('后移')
        for b in (self.main_button,self.up,self.down):buttons.addWidget(b)
        box.addLayout(buttons)
        self.errors = QPlainTextEdit();self.errors.setReadOnly(True);self.errors.setMaximumHeight(80)
        box.addWidget(self.errors)
        self.root_button.clicked.connect(self.choose_root)
        self.items.currentRowChanged.connect(self.show_preview)
        self.main_button.clicked.connect(self.set_main)
        self.up.clicked.connect(lambda:self.move(-1))
        self.down.clicked.connect(lambda:self.move(1))

    def choose_root(self) -> None:
        text = QFileDialog.getExistingDirectory(self,'选择产品图片根目录')
        if text:
            self.root=Path(text);self.cache.clear();self.root_label.setText(text);self.load()

    def select_product(self, product_id: str, folder: str) -> None:
        self.product_id,self.folder=product_id,folder
        self.load()

    def load(self) -> None:
        if self.worker is not None:
            return
        self.collection=ImageCollection([],[])
        self.render()
        if not self.root or not self.product_id:return
        if self.product_id in self.cache:
            self.collection=self.cache[self.product_id];self.render();return
        self.info.setText('正在后台检查图片…')
        self.worker=ImageReader(self.root,self.folder,self)
        self.loading_id=self.product_id
        self.root_button.setEnabled(False)
        self.worker.ready.connect(self.loaded)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def loaded(self, collection: ImageCollection) -> None:
        self.cache[self.loading_id]=collection
        if self.loading_id==self.product_id:
            self.collection=collection;self.render()

    def finished(self) -> None:
        worker=self.worker;self.worker=None
        if worker:worker.deleteLater()
        self.root_button.setEnabled(True)
        if self.loading_id!=self.product_id:self.load()

    def render(self) -> None:
        self.items.clear();self.preview.clear()
        self.info.setText(f'{self.product_id or "未选择产品"} · 有效图片 {len(self.collection.images)} 张')
        for image in self.collection.images:
            pix=QPixmap();pix.loadFromData(image.thumbnail)
            suffix=' [主图]' if image.path==self.collection.main else ''
            self.items.addItem(QListWidgetItem(QIcon(pix),image.path.name+suffix))
        self.errors.setPlainText('\n'.join(self.collection.errors))
        self.items.setCurrentRow(0)

    def show_preview(self,index: int) -> None:
        if 0<=index<len(self.collection.images):
            image=self.collection.images[index]
            pix=QPixmap();pix.loadFromData(image.thumbnail)
            self.preview.setPixmap(pix.scaled(400,180,mode=Qt.TransformationMode.SmoothTransformation,aspectMode=Qt.AspectRatioMode.KeepAspectRatio))
            self.preview.setToolTip(f'{image.width} × {image.height}；{image.byte_size} 字节')

    def set_main(self) -> None:
        index=self.items.currentRow()
        if index>=0:self.collection.set_main(index);self.render();self.items.setCurrentRow(index)

    def move(self,delta: int) -> None:
        index=self.items.currentRow();target=index+delta
        if 0<=target<len(self.collection.images) and index>=0:
            self.collection.move(index,target);self.render();self.items.setCurrentRow(target)
