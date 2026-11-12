"""真实数据库快照模型及后台校验刷新。"""
import logging
from PySide6.QtCore import QAbstractTableModel,QModelIndex,Qt,QThread,Signal,QSortFilterProxyModel
from core.database import ProductDatabase
from core.product_validation import ProductValidator

class DatabaseModel(QAbstractTableModel):
    HEADERS=('产品编号','产品标题','价格','MOQ','图片数量','数据校验状态')
    def __init__(self,parent=None):
        super().__init__(parent);self.rows=[];self.products=();self.errors={}
    def replace(self,products,errors,counts):
        self.beginResetModel();self.products=products;self.errors=errors
        self.rows=[(p.product_id,str(p.values[1]),str(p.values[5]),p.values[7],counts.get(p.product_id,0),'数据校验失败' if errors[p.product_id] else '数据校验通过') for p in products]
        self.endResetModel()
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def columnCount(self,parent=QModelIndex()):return 0 if parent.isValid() else 6
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role==Qt.ItemDataRole.DisplayRole:return self.rows[index.row()][index.column()]
        return None
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if role==Qt.ItemDataRole.DisplayRole:return self.HEADERS[section] if orientation==Qt.Orientation.Horizontal else section+1
        return None

class ProductFilter(QSortFilterProxyModel):
    def __init__(self,parent=None):
        super().__init__(parent);self.search='';self.status='全部'
    def filterAcceptsRow(self,row,parent):
        values=self.sourceModel().rows[row]
        return (self.search.casefold() in (' '.join(map(str,values[:2]))).casefold()) and (self.status=='全部' or self.status==values[5])
    def set_filters(self,search,status):
        self.beginFilterChange()
        self.search,self.status=search,status
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

class DatabaseReader(QThread):
    ready=Signal(object,object,object)
    failed=Signal(str)
    def __init__(self,path,root,parent=None):
        super().__init__(parent);self.path,self.root=path,root
    def run(self):
        try:
            store=ProductDatabase(self.path);products=store.products
            validator=ProductValidator();errors={};counts={}
            for p in products:
                images=store.get_images(p.product_id)
                errors[p.product_id]=validator.validate(p,self.root,[path for path,_ in images] if images else None)
                if self.root is not None:
                    from core.product_images import scan_images
                    counts[p.product_id]=len(scan_images(self.root,str(p.values[-1])).images)
                else:counts[p.product_id]=len(images)
            self.ready.emit(products,errors,counts)
        except Exception as exc:
            logging.getLogger(__name__).exception('数据库后台刷新失败');self.failed.emit(str(exc))
