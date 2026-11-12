"""第四阶段重启持久化、图片顺序及正式数据边界验收。"""
import os
from pathlib import Path
import subprocess
import sys
from PIL import Image
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtTest import QTest
from core.database import ProductDatabase
from core.excel_importer import read_products
from core.excel_template import generate_template
from ui.main_window import MainWindow


def wait(window,app):
    for _ in range(500):
        app.processEvents()
        if window.refresh_worker is None and window.image_panel.worker is None:break
        QTest.qWait(10)
    assert window.refresh_worker is None
    assert window.image_panel.worker is None


def test_images_order_main_survive_new_process(tmp_path):
    path=tmp_path/'db';db=ProductDatabase(path)
    product=read_products(generate_template(tmp_path/'products.xlsx')).products[0]
    db.add(product)
    folder=tmp_path/str(product.values[-1]);folder.mkdir(parents=True)
    for name in ['1.png','2.png']:Image.new('RGB',(30,30)).save(folder/name)
    images=[(str(folder/'2.png'),True),(str(folder/'1.png'),False)]
    db.save_edit(product,product,tmp_path,images)
    script='''import sys
from pathlib import Path
from core.database import ProductDatabase
db=ProductDatabase(Path(sys.argv[1]))
assert db.get('000001').product_id=='000001'
assert [Path(p).name for p,m in db.get_images('000001')]==['2.png','1.png']
assert db.get_images('000001')[0][1] is True
print('PERSISTENCE_OK')
'''
    result=subprocess.run([sys.executable,'-B','-c',script,str(path)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert 'PERSISTENCE_OK' in result.stdout


def test_close_reopen_window_and_no_demo(tmp_path):
    app=QApplication.instance() or QApplication([])
    first=MainWindow();first.show();wait(first,app)
    first.import_page.store.commit(read_products(generate_template(tmp_path/'products.xlsx')))
    first.refresh_image_products();wait(first,app)
    assert first.model.rowCount()==3
    assert first.close()
    second=MainWindow();second.show();wait(second,app)
    try:
        assert second.model.rowCount()==3
        assert second.model.rows[0][0]=='000001'
        for index,button in enumerate(second.nav_buttons):
            button.click();app.processEvents();assert second.stack.currentIndex()==index
        labels=[w.text() for w in second.findChildren(QLabel)]
        assert not any('模拟' in text for text in labels)
        assert any('不代表上传成功' in text for text in labels)
        assert all('上传成功' not in row[5] for row in second.model.rows)
        assert all(not b.isEnabled() for b in second.action_buttons)
    finally:
        wait(second,app);second.close()
