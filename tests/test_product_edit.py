"""编辑失败保留资料和图片元数据。"""
from dataclasses import replace
from decimal import Decimal
from PIL import Image
import pytest
from core.database import ProductDatabase
from core.excel_importer import read_products
from core.excel_template import generate_template,FIELDS
from core.product_validation import ProductValidator

@pytest.fixture
def setup(tmp_path):
    batch=read_products(generate_template(tmp_path/'t.xlsx'))
    p=batch.products[0]
    folder=tmp_path/str(p.values[-1]);folder.mkdir(parents=True)
    Image.new('RGB',(20,20)).save(folder/'1.png')
    db=ProductDatabase(tmp_path/'db');db.add(p)
    return db,p,tmp_path,[(str(folder/'1.png'),True)]


def change(p,field,value):
    return replace(p,values=tuple(value if f==field else v for f,v in zip(FIELDS,p.values)))


def test_edit_persists_all_fields_images_and_stale_rejected(setup):
    db,p,root,images=setup
    edited=change(change(p,'title','Edited title'),'price',Decimal('9.99'))
    db.save_edit(p,edited,root,images)
    assert db.get(p.product_id).values==edited.values
    assert db.get_images(p.product_id)==images
    with pytest.raises(ValueError):db.save_edit(p,p,root,images)
    assert db.get(p.product_id).values==edited.values


@pytest.mark.parametrize('field,value',[('title',''),('price',Decimal('0')),('price',Decimal('-1')),('moq',0),('moq',Decimal('1.2')),('keywords',''),('description',''),('product_id','')])
def test_invalid_edit_preserves_original(setup,field,value):
    db,p,root,images=setup
    db.save_images(p.product_id,images)
    with pytest.raises(ValueError):db.save_edit(p,change(p,field,value),root,images)
    assert db.get(p.product_id).values==p.values
    assert db.get_images(p.product_id)==images


def test_invalid_images_and_injected_write_failure_rollback(setup,monkeypatch):
    db,p,root,images=setup;db.save_images(p.product_id,images)
    with pytest.raises(ValueError):db.save_edit(p,p,root,[(str(root/'missing.png'),True)])
    original=db._write
    def fail(*args):
        original(*args)
        raise RuntimeError('injected write failure')
    monkeypatch.setattr(db,'_write',fail)
    with pytest.raises(RuntimeError):db.save_edit(p,change(p,'title','new'),root,images)
    assert db.get(p.product_id).values==p.values
    assert db.get_images(p.product_id)==images


def test_extensible_rules_duplicate_batch_and_cancel(setup):
    db,p,root,images=setup
    validator=ProductValidator((lambda data:['category：专用测试规则'],))
    assert any('专用' in e for e in validator.validate(p,root))
    assert any('重复' in e for e in ProductValidator().validate_all((p,p),root)[p.product_id])
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from ui.product_editor import ProductEditor
    app=QApplication.instance() or QApplication([])
    editor=ProductEditor(db,p,root)
    for _ in range(500):
        app.processEvents()
        if editor.images.worker is None:break
        QTest.qWait(10)
    assert editor.images.worker is None
    editor.inputs['title'].setText('not saved');editor.reject()
    assert db.get(p.product_id).values==p.values
