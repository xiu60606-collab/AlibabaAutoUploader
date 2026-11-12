"""产品表格展示模型。"""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from core.demo_data import Product

class ProductTableModel(QAbstractTableModel):
    HEADERS = ("产品编号", "产品标题", "产品价格", "图片数量", "当前状态", "最近操作时间")

    def __init__(self, products: tuple[Product, ...], parent=None) -> None:
        super().__init__(parent)
        self.products = products

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.products)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.products)) or not (0 <= index.column() < 6):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            p = self.products[index.row()]
            return (p.number, p.title, p.price, p.images, p.status, p.updated)[index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
            if orientation == Qt.Orientation.Vertical:
                return section + 1
        return None
