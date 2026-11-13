"""离屏验证界面导航和演示边界，不连接客户端。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableView
from ui.main_window import MainWindow, PAGES

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app):
    widget = MainWindow()
    widget.show()
    app.processEvents()
    from PySide6.QtTest import QTest
    for _ in range(500):
        app.processEvents()
        if widget.refresh_worker is None: break
        QTest.qWait(10)
    yield widget
    widget.close()

def test_navigation(window, app):
    assert window.stack.count() == 7
    for index, button in enumerate(window.nav_buttons):
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert window.stack.currentIndex() == index
        assert button.isChecked()

def test_demo_safety_and_model(window):
    assert window.model.rowCount() == 0
    assert window.model.columnCount() == 6
    assert window.model.data(QModelIndex()) is None
    assert window.model.rows == []
    assert all(not button.isEnabled() for button in window.action_buttons)
    assert window.progress.value() == 0
    assert len([v for v in window.findChildren(QTableView) if v.model() is window.model]) == 1

def test_resizing(window, app):
    assert window.size().width() == 1280
    assert window.size().height() == 800
    window.resize(1024, 680)
    app.processEvents()
    assert window.width() == 1024
    assert window.height() == 680
    assert window.minimumWidth() == 1024
    assert window.minimumHeight() == 680
