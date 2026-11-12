"""整个测试会话共享 QApplication，避免控件早于应用被销毁。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope='session', autouse=True)
def qt_application():
    application = QApplication.instance() or QApplication([])
    yield application
    application.closeAllWindows()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()

@pytest.fixture(autouse=True)
def isolated_product_database(tmp_path, monkeypatch):
    monkeypatch.setattr('ui.import_page.application_database_path', lambda: tmp_path / 'products.sqlite3')
