"""图片安全边界、格式校验、排序及原图不变性。"""
from io import BytesIO
from pathlib import Path
from PIL import Image
import pytest
from core.product_images import scan_images


def test_scan_sort_thumbnail_reorder_and_originals(tmp_path):
    folder=tmp_path/'P001';folder.mkdir()
    for name in ['10.jpg','2.jpg','01.png','3.webp']:
        Image.new('RGB',(32,24),'blue').save(folder/name)
    original={p.name:p.read_bytes() for p in folder.iterdir()}
    result=scan_images(tmp_path,'P001')
    assert not result.errors
    assert [p.path.name for p in result.images]==['01.png','2.jpg','3.webp','10.jpg']
    assert all((p.width,p.height)==(32,24) for p in result.images)
    with Image.open(BytesIO(result.images[0].thumbnail)) as im:assert max(im.size)<=640
    result.set_main(2);main=result.main
    result.move(2,0)
    assert result.images[0].path==main and result.main==main
    assert original=={p.name:p.read_bytes() for p in folder.iterdir()}


@pytest.mark.parametrize('folder',['../outside','/tmp','C:\\outside','..\\outside',''])
def test_traversal(tmp_path,folder):
    result=scan_images(tmp_path,folder)
    assert not result.images and result.errors


def test_bad_missing_empty_and_size(tmp_path,monkeypatch):
    import core.product_images as module
    folder=tmp_path/'P';folder.mkdir()
    assert scan_images(tmp_path,'missing').errors
    assert '没有可用图片' in scan_images(tmp_path,'P').errors
    (folder/'broken.jpg').write_bytes(b'bad')
    Image.new('RGB',(20,20)).save(folder/'wrong.jpg',format='PNG')
    (folder/'note.txt').write_text('hello')
    result=scan_images(tmp_path,'P')
    assert len(result.errors)==4
    assert any('不匹配' in e for e in result.errors)
    Image.new('RGB',(20,20)).save(folder/'good.png')
    monkeypatch.setattr(module,'MAX_BYTES',1)
    assert any('20 MiB' in e for e in scan_images(tmp_path,'P').errors)


def test_symlink_escape(tmp_path):
    root=tmp_path/'root';root.mkdir();outside=tmp_path/'out';outside.mkdir()
    Image.new('RGB',(20,20)).save(outside/'a.png')
    (root/'P').symlink_to(outside,target_is_directory=True)
    assert not scan_images(root,'P').images
    (root/'Q').mkdir();(root/'Q'/'a.png').symlink_to(outside/'a.png')
    result=scan_images(root,'Q')
    assert not result.images and any('符号链接' in e for e in result.errors)


def test_panel_preview_main_and_move(tmp_path):
    from PySide6.QtWidgets import QApplication
    from ui.image_panel import ImagePanel
    app=QApplication.instance() or QApplication([])
    for name in ['1.png','2.png']:Image.new('RGB',(20,20)).save(tmp_path/name)
    panel=ImagePanel();panel.collection=scan_images(tmp_path,'.');panel.render()
    assert panel.items.count()==2
    panel.items.setCurrentRow(1);panel.set_main()
    assert panel.collection.main.name=='2.png'
    panel.move(-1)
    assert panel.collection.images[0].path.name=='2.png'
    assert not panel.preview.pixmap().isNull()
    panel.close()
