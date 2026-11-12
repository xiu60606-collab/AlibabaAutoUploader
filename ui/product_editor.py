"""产品编辑对话框，取消不写库。"""
from decimal import Decimal, InvalidOperation
import logging
import sqlite3
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLineEdit,QPlainTextEdit,QDialogButtonBox,QScrollArea,QWidget,QLabel
from core.excel_template import FIELDS
from core.excel_importer import ImportedProduct
from core.product_images import ImageCollection
from ui.image_panel import ImagePanel

logger=logging.getLogger(__name__)

class ProductEditor(QDialog):
    def __init__(self,store,product,root,parent=None) -> None:
        super().__init__(parent)
        self.store,self.original=store,product
        self.setWindowTitle('产品详细资料 · 本地编辑')
        self.resize(850,760)
        outer=QVBoxLayout(self);scroll=QScrollArea();scroll.setWidgetResizable(True)
        content=QWidget();box=QVBoxLayout(content);form=QFormLayout();self.inputs={}
        for field,value in zip(FIELDS,product.values):
            widget=QPlainTextEdit(str(value)) if field in {'description','keywords'} else QLineEdit(str(value))
            if isinstance(widget,QPlainTextEdit):widget.setMaximumHeight(90)
            if field=='product_id':widget.setReadOnly(True)
            self.inputs[field]=widget;form.addRow(field,widget)
        box.addLayout(form)
        self.images=ImagePanel();self.images.root=root
        box.addWidget(self.images)
        self.images.select_product(product.product_id,str(product.values[FIELDS.index('image_folder')]))
        self.images.root_button.setEnabled(False)
        self.images.worker.finished.connect(self.restore_order) if self.images.worker else None
        self.error=QLabel('通用本地检查，不是阿里巴巴官方完整发布规则。');self.error.setWordWrap(True);box.addWidget(self.error)
        scroll.setWidget(content);outer.addWidget(scroll)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);outer.addWidget(buttons)

    def restore_order(self) -> None:
        saved=self.store.get_images(self.original.product_id)
        collection=self.images.collection
        mapping={str(i.path):i for i in collection.images}
        if saved:
            collection.images=[mapping[p] for p,_ in saved if p in mapping]+[i for i in collection.images if str(i.path) not in {p for p,_ in saved}]
            for p,main in saved:
                if main and p in mapping:collection.main=mapping[p].path
        self.images.render();self.images.root_button.setEnabled(False)

    def save(self) -> None:
        if self.images.worker is not None:
            self.error.setText('请等待图片检查完成');return
        try:
            values=[]
            for field in FIELDS:
                widget=self.inputs[field]
                text=widget.toPlainText().strip() if isinstance(widget,QPlainTextEdit) else widget.text().strip()
                if field in {'price','weight'} and text:value=Decimal(text)
                elif field=='moq':
                    number=Decimal(text)
                    if not number.is_finite() or number!=number.to_integral_value():raise ValueError('moq：必须为正整数')
                    value=int(number)
                else:value=text
                values.append(value)
            edited=ImportedProduct(self.original.row,tuple(values))
            images=[(str(i.path),i.path==self.images.collection.main) for i in self.images.collection.images]
            self.store.save_edit(self.original,edited,self.images.root,images)
        except (ValueError,InvalidOperation,sqlite3.Error,OSError) as exc:
            logger.exception('产品保存失败');self.error.setText(str(exc));return
        self.accept()

    def done(self,result: int) -> None:
        if self.images.worker is not None:
            self.error.setText('请等待图片检查完成后关闭');return
        super().done(result)
