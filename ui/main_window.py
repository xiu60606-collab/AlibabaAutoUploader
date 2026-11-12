"""桌面主界面；仅展示模拟数据，不执行客户端操作。"""
import logging
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QStackedWidget, QTableView, QProgressBar, QPlainTextEdit,
    QHeaderView, QAbstractItemView, QButtonGroup,
)
from core.demo_data import DEMO_PRODUCTS
from ui.product_model import ProductTableModel
from ui.import_page import ImportPage

logger = logging.getLogger(__name__)
APP_VERSION = "0.1.0"
PAGES = ("工作台", "产品管理", "产品导入", "自动上传", "上传记录", "软件设置")


def label(text: str, name: str = "") -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


class MainWindow(QMainWindow):
    """通过堆叠页面展示导航、产品数据及未启用的操作。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Alibaba Product Auto Uploader · 演示模式")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 680)
        self.setStyleSheet(Path(__file__).with_name("styles.qss").read_text(encoding="utf-8"))
        self.model = ProductTableModel(DEMO_PRODUCTS, self)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(192)
        side = QVBoxLayout(sidebar)
        side.addWidget(label("ALI UPLOADER", "brand"))
        self.nav_group = QButtonGroup(self)
        self.nav_buttons: list[QPushButton] = []
        for index, title in enumerate(PAGES):
            button = QPushButton(title)
            button.setProperty("nav", True)
            button.setCheckable(True)
            self.nav_group.addButton(button, index)
            self.nav_buttons.append(button)
            side.addWidget(button)
        side.addStretch()
        side.addWidget(label("安全优先 · 默认草稿\n当前仅展示模拟数据", "sideNote"))
        layout.addWidget(sidebar)
        content = QWidget()
        content.setObjectName("content")
        body = QVBoxLayout(content)
        body.setContentsMargins(24, 18, 24, 18)
        body.setSpacing(14)
        header = QHBoxLayout()
        header.addWidget(label("Alibaba Product Auto Uploader", "appTitle"), 1)
        header.addWidget(label(f"版本 {APP_VERSION}", "muted"))
        body.addLayout(header)
        status = QHBoxLayout()
        status.addWidget(label("当前运行模式：演示 / 仅保存草稿", "badge"))
        status.addWidget(label("客户端：未连接（连接功能未启用）", "muted"))
        status.setStretch(0, 1)
        status.setStretch(1, 1)
        body.addLayout(status)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.dashboard())
        self.stack.addWidget(self.products_page())
        descriptions = (
            "Excel 导入尚未启用。后续将支持产品资料校验与导入。",
            "自动上传尚未启用，未连接任何客户端。正式发布必须经人工确认。",
            "暂无真实上传记录。工作台中的产品均为模拟数据。",
            "当前默认保存草稿，正式发布需要人工确认。配置编辑尚未启用。",
        )
        for title, description in zip(PAGES[2:], descriptions):
            if title == "产品导入":
                self.import_page = ImportPage(self)
                self.stack.addWidget(self.import_page)
                continue
            page = QWidget()
            box = QVBoxLayout(page)
            box.addWidget(label(title, "pageTitle"))
            box.addWidget(label(description, "muted"))
            box.addStretch()
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)
        actions = QHBoxLayout()
        self.action_buttons: list[QPushButton] = []
        for title in ("导入 Excel", "开始任务", "暂停", "继续", "停止"):
            button = QPushButton(f"{title}（未启用）")
            button.setEnabled(False)
            button.setToolTip("本阶段仅实现界面，此功能将在后续阶段开发。")
            self.action_buttons.append(button)
            actions.addWidget(button)
        actions.addStretch()
        body.addLayout(actions)
        layout.addWidget(content, 1)
        self.nav_group.idClicked.connect(self.switch_page)
        self.nav_buttons[0].setChecked(True)
        self.statusBar().showMessage("界面演示 · 无真实客户端连接 · 无真实上传操作")

    def switch_page(self, index: int) -> None:
        """切换导航页面并记录界面操作。"""
        self.stack.setCurrentIndex(index)
        logger.info("切换页面：%s", PAGES[index])

    def table(self) -> QTableView:
        view = QTableView()
        view.setModel(self.model)
        view.setAlternatingRowColors(True)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.verticalHeader().setVisible(False)
        view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        view.verticalHeader().setDefaultSectionSize(44)
        return view

    def dashboard(self) -> QWidget:
        """创建明确区分模拟统计和真实结果的工作台。"""
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(label("工作台", "pageTitle"))
        box.addWidget(label("模拟产品预览 · 以下统计不代表真实上传结果", "muted"))
        metrics = QHBoxLayout()
        for title, value in (("产品总数（模拟）", len(DEMO_PRODUCTS)), ("待上传产品数（模拟）", len(DEMO_PRODUCTS)), ("草稿保存成功数", 0), ("失败产品数", 0)):
            card = QFrame()
            card.setObjectName("card")
            card_box = QVBoxLayout(card)
            card_box.addWidget(label(title, "muted"))
            card_box.addWidget(label(str(value), "metric"))
            metrics.addWidget(card)
        box.addLayout(metrics)
        box.addWidget(label("产品任务表格 · 模拟数据"))
        box.addWidget(self.table(), 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("尚未执行上传任务 · %p%")
        box.addWidget(self.progress)
        box.addWidget(label("最近操作日志"))
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumHeight(100)
        self.logs.setPlainText("[界面] 已加载模拟产品数据。\n[状态] 未连接客户端，未执行导入或上传操作。")
        box.addWidget(self.logs)
        return page

    def products_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(label("产品管理", "pageTitle"))
        box.addWidget(label("只读模拟产品列表 · 编辑与持久化尚未启用", "muted"))
        box.addWidget(self.table())
        return page

    def closeEvent(self, event) -> None:
        """读取期间请求取消并暂缓关闭，避免销毁运行中的线程。"""
        if self.import_page.worker is not None:
            self.import_page.cancel_import()
            self.statusBar().showMessage("正在取消 Excel 读取，请稍后再次关闭窗口。")
            event.ignore()
            return
        super().closeEvent(event)
