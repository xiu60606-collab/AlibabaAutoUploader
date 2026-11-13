"""桌面主界面；仅展示模拟数据，不执行客户端操作。"""
import logging
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QStackedWidget, QTableView, QProgressBar, QPlainTextEdit,
    QHeaderView, QAbstractItemView, QButtonGroup,
)
from ui.database_model import DatabaseModel, ProductFilter, DatabaseReader
from PySide6.QtWidgets import QLineEdit
from ui.import_page import ImportPage
from ui.image_panel import ImagePanel
from ui.window_debug import WindowDebug
from ui.product_editor import ProductEditor
from core.excel_template import FIELDS
from PySide6.QtWidgets import QComboBox

logger = logging.getLogger(__name__)
APP_VERSION = "0.3.0"
PAGES = ("工作台", "产品管理", "产品导入", "自动上传", "上传记录", "软件设置", "自动化调试")


def label(text: str, name: str = "") -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


class MainWindow(QMainWindow):
    """通过堆叠页面展示导航、产品数据及未启用的操作。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Alibaba Product Auto Uploader · 本地产品管理")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 680)
        self.setStyleSheet(Path(__file__).with_name("styles.qss").read_text(encoding="utf-8"))
        self.model = DatabaseModel(self)
        self.refresh_worker = None
        self.refresh_pending = False
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
        side.addWidget(label("安全优先 · 默认草稿\n本地数据 · 自动上传未启用", "sideNote"))
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
        status.addWidget(label("当前运行模式：本地管理 / 默认草稿", "badge"))
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
            "暂无真实上传记录。尚未执行真实上传。",
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
            if title == "自动上传":
                debug = QPushButton("自动化调试 · Windows 窗口识别")
                debug.clicked.connect(lambda: WindowDebug(self).exec())
                box.addWidget(debug)
            box.addStretch()
            self.stack.addWidget(page)
        self.window_debug = WindowDebug(self)
        self.window_debug.setWindowFlags(Qt.WindowType.Widget)
        self.stack.addWidget(self.window_debug)
        self.import_page.imported.connect(self.refresh_image_products)
        self.import_page.root_changed.connect(self.set_image_root)
        self.image_panel.root_button.clicked.connect(self.refresh_image_products)
        self.refresh_image_products()
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
        self.statusBar().showMessage("本地产品管理 · 无真实客户端连接 · 无真实上传操作")

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
        box.addWidget(label("SQLite 产品统计 · 数据校验通过不代表上传成功", "muted"))
        metrics = QHBoxLayout()
        self.metric_labels = []
        for title, value in (("产品总数", 0), ("待处理产品数量", 0), ("数据校验通过数量", 0), ("数据校验失败数量", 0)):
            card = QFrame()
            card.setObjectName("card")
            card_box = QVBoxLayout(card)
            card_box.addWidget(label(title, "muted"))
            metric = label(str(value), "metric")
            self.metric_labels.append(metric)
            card_box.addWidget(metric)
            metrics.addWidget(card)
        box.addLayout(metrics)
        box.addWidget(label("产品数据 · SQLite"))
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
        self.logs.setPlainText("[界面] 正在读取本地产品数据库。\n[状态] 未连接客户端，未执行导入或上传操作。")
        box.addWidget(self.logs)
        return page

    def products_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(label("产品管理", "pageTitle"))
        box.addWidget(label("SQLite 产品列表 · 校验结果仅为本地通用检查", "muted"))
        filters = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("搜索产品编号或标题")
        self.status_filter = QComboBox(); self.status_filter.addItems(["全部", "数据校验通过", "数据校验失败"])
        filters.addWidget(self.search); filters.addWidget(self.status_filter)
        box.addLayout(filters)
        self.proxy = ProductFilter(self); self.proxy.setSourceModel(self.model)
        self.product_table = self.table(); self.product_table.setModel(self.proxy)
        self.search.textChanged.connect(self.apply_filters)
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        self.product_table.clicked.connect(self.select_table_product)
        self.product_table.doubleClicked.connect(lambda index: self.edit_product())
        box.addWidget(self.product_table)
        self.image_products = QComboBox()
        self.image_products.setPlaceholderText("选择已确认导入的产品以管理图片")
        box.addWidget(self.image_products)
        tools = QHBoxLayout()
        edit = QPushButton("查看 / 编辑选中产品")
        check = QPushButton("批量检查所有产品")
        edit.clicked.connect(self.edit_product)
        check.clicked.connect(self.check_products)
        tools.addWidget(edit); tools.addWidget(check)
        box.addLayout(tools)
        self.validation_errors = QPlainTextEdit()
        self.validation_errors.setReadOnly(True)
        self.validation_errors.setMaximumHeight(90)
        box.addWidget(self.validation_errors)
        self.image_panel = ImagePanel(self)
        box.addWidget(self.image_panel)
        self.image_products.currentIndexChanged.connect(self.select_image_product)
        return page

    def closeEvent(self, event) -> None:
        """读取期间请求取消并暂缓关闭，避免销毁运行中的线程。"""
        if self.window_debug.worker is not None:
            self.statusBar().showMessage("窗口检测执行中，请完成后关闭。")
            event.ignore(); return
        if self.refresh_worker is not None:
            self.statusBar().showMessage("正在刷新产品，请稍后关闭。")
            event.ignore(); return
        if self.image_panel.worker is not None:
            self.statusBar().showMessage("正在检查图片，请等待检查完成后关闭。")
            event.ignore()
            return
        if self.import_page.worker is not None:
            self.import_page.cancel_import()
            self.statusBar().showMessage("正在取消 Excel 读取，请稍后再次关闭窗口。")
            event.ignore()
            return
        super().closeEvent(event)

    def refresh_image_products(self) -> None:
        if self.refresh_worker is not None:
            self.refresh_pending = True; return
        self.refresh_worker = DatabaseReader(self.import_page.store.path, self.image_panel.root, self)
        self.refresh_worker.ready.connect(self.apply_snapshot)
        self.refresh_worker.failed.connect(lambda message: self.logs.appendPlainText("刷新失败：" + message))
        self.refresh_worker.finished.connect(self.refresh_finished)
        self.refresh_worker.start()

    def refresh_finished(self) -> None:
        worker = self.refresh_worker; self.refresh_worker = None
        worker.deleteLater()
        if self.refresh_pending:
            self.refresh_pending = False; self.refresh_image_products()

    def apply_snapshot(self, products, errors, counts) -> None:
        self.model.replace(products, errors, counts)
        self.image_products.clear()
        for product in products:
            self.image_products.addItem(f"{product.product_id} · {product.values[1]}", product)
        passed = sum(not e for e in errors.values())
        # 尚无上传任务模块，所有本地产品均待处理。
        for widget, value in zip(self.metric_labels, (len(products), len(products), passed, len(products)-passed)):
            widget.setText(str(value))
        self.validation_errors.setPlainText("\n".join(f"{pid}：{len(e)} 个错误\n" + "\n".join(e) for pid,e in errors.items()) or "暂无产品")
        self.logs.appendPlainText(f"已刷新 {len(products)} 个数据库产品；未执行上传。")

    def apply_filters(self) -> None:
        self.proxy.set_filters(self.search.text(), self.status_filter.currentText())

    def select_table_product(self, index) -> None:
        source = self.proxy.mapToSource(index)
        self.image_products.setCurrentIndex(source.row())

    def set_image_root(self, root) -> None:
        self.image_panel.root = root
        self.image_panel.root_label.setText(str(root))
        self.image_panel.cache.clear()
        self.refresh_image_products()

    def select_image_product(self, index: int) -> None:
        product = self.image_products.itemData(index)
        if product is not None:
            self.image_panel.select_product(product.product_id, str(product.values[FIELDS.index("image_folder")]))

    def edit_product(self) -> None:
        product = self.image_products.currentData()
        if product is None:
            self.validation_errors.setPlainText("请选择数据库产品"); return
        dialog = ProductEditor(self.import_page.store, product, self.image_panel.root, self)
        if dialog.exec():
            self.image_panel.cache.clear()
            self.refresh_image_products()

    def check_products(self) -> None:
        self.refresh_image_products()
