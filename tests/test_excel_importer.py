"""导入校验、原子保存与后台界面流程。"""
from decimal import Decimal
from threading import Event
from openpyxl import Workbook, load_workbook
import pytest
from core.excel_template import generate_template
from core.excel_importer import read_products, MemoryProductStore


def modify(path, field, value, row=2):
    wb = load_workbook(path)
    ws = wb.active
    col = [c.value for c in ws[1]].index(field) + 1
    ws.cell(row,col,value)
    wb.save(path)
    wb.close()


def test_valid_decimal_text_and_atomic_commit(tmp_path):
    path = generate_template(tmp_path/'a.xlsx')
    modify(path,'price','0.10')
    result = read_products(path)
    assert not result.errors
    assert result.products[0].product_id == '000001'
    assert result.products[0].values[5] == Decimal('0.10')
    assert isinstance(result.products[0].values[5],Decimal)
    store = MemoryProductStore()
    assert not store.products
    store.commit(result)
    before = store.products
    with pytest.raises(ValueError):
        store.commit(result)
    assert store.products == before


@pytest.mark.parametrize('field,value', [('title',' '),('keywords',' '),('description',' '),('moq',0),('moq',1.5),('price','NaN'),('price',-1),('currency','XYZ'),('price','=1+1'),('product_id','000002')])
def test_invalid_batch(tmp_path,field,value):
    path=generate_template(tmp_path/'bad.xlsx')
    modify(path,field,value)
    result=read_products(path)
    assert result.errors
    assert any(f'[{field}]' in e for e in result.errors)
    assert all('行 [' in e for e in result.errors)
    store=MemoryProductStore()
    with pytest.raises(ValueError):store.commit(result)
    assert not store.products


def test_missing_corrupt_headers_blank_numeric_id_cancel(tmp_path):
    assert '[file]' in read_products(tmp_path/'missing.xlsx').errors[0]
    corrupt=tmp_path/'bad.xlsx';corrupt.write_bytes(b'broken')
    assert read_products(corrupt).errors
    path=generate_template(tmp_path/'a.xlsx')
    wb=load_workbook(path);ws=wb.active
    ws.cell(2,1,42);ws.cell(2,1).number_format='000000'
    ws.append([None]*13);ws.append([' ']*13)
    wb.save(path);wb.close()
    result=read_products(path)
    assert len(result.products)==3 and result.products[0].product_id=='000042'
    cancel=Event();cancel.set()
    assert read_products(path,cancel).errors
    wb=load_workbook(path);wb.active.cell(1,2,'unknown');wb.save(path);wb.close()
    assert any('[title]' in e and '第 1 行' in e for e in read_products(path).errors)


def test_async_preview_confirm_and_cancel(tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from ui.import_page import ImportPage
    app=QApplication.instance() or QApplication([])
    page=ImportPage()
    path=generate_template(tmp_path/'ui.xlsx')
    page.path.setText(str(path));page.start_read()
    for _ in range(500):
        app.processEvents()
        if page.worker is None:break
        QTest.qWait(10)
    assert page.worker is None
    assert page.model.rowCount()==3 and not page.store.products
    assert page.confirm.isEnabled()
    page.cancel_import()
    assert not page.store.products and not page.confirm.isEnabled()
    page.start_read()
    for _ in range(500):
        app.processEvents()
        if page.worker is None:break
        QTest.qWait(10)
    assert page.worker is None
    page.confirm.click()
    assert len(page.store.products)==3
    page.cancel_import()
    assert len(page.store.products)==3
    page.close()
