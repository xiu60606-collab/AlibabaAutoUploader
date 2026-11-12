"""SQLite 数据刷新、搜索筛选和非模拟展示。"""
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from core.excel_template import generate_template
from core.excel_importer import read_products
from ui.main_window import MainWindow


def wait(window,app):
    for _ in range(500):
        app.processEvents()
        if window.refresh_worker is None:break
        QTest.qWait(10)
    assert window.refresh_worker is None


def test_real_products_refresh_search_and_filter(tmp_path):
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    try:
        wait(window,app)
        assert window.model.rowCount()==0
        window.import_page.store.commit(read_products(generate_template(tmp_path/'input.xlsx')))
        window.import_page.imported.emit()
        wait(window,app)
        assert window.model.rowCount()==3
        assert window.model.data(window.model.index(0,0))=='000001'
        assert [w.text() for w in window.metric_labels]==['3','3','0','3']
        window.search.setText('000002')
        assert window.proxy.rowCount()==1
        window.search.clear()
        window.status_filter.setCurrentText('数据校验通过')
        assert window.proxy.rowCount()==0
        window.status_filter.setCurrentText('数据校验失败')
        assert window.proxy.rowCount()==3
        assert window.image_products.count()==3
    finally:
        wait(window,app);window.close()
