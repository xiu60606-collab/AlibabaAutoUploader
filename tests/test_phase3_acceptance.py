"""第三阶段验收：离屏控件行为及独立进程启动/关闭。"""
import ast
import importlib
from importlib.metadata import version
import os
from pathlib import Path
import platform
import subprocess
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QTableView
from core.demo_data import DEMO_PRODUCTS
from ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_and_dependencies():
    assert platform.system() == 'Darwin', '本次验收要求在 macOS 执行'
    assert sys.version_info[:3] == (3, 13, 12)
    assert sys.prefix != sys.base_prefix
    for module, distribution in [('PySide6','PySide6'), ('openpyxl','openpyxl'), ('PIL','Pillow'), ('pytest','pytest')]:
        assert importlib.import_module(module)
        assert version(distribution)


def test_visible_table_resize_progress_and_demo_boundary():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.show()
        app.processEvents()
        assert window.isVisible()
        assert not window.grab().isNull()
        table = window.stack.widget(0).findChild(QTableView)
        from PySide6.QtTest import QTest
        for _ in range(500):
            app.processEvents()
            if window.refresh_worker is None:break
            QTest.qWait(10)
        assert table.model().rowCount() == 0
        widths = []
        for width, height in [(1024, 680), (1440, 900)]:
            window.resize(width, height)
            app.processEvents()
            widths.append(table.viewport().width())
            assert table.isVisible()
            assert window.progress.isVisible()
            assert table.model().rowCount() == 0
        assert widths[1] > widths[0]
        assert window.progress.minimum() == 0
        assert window.progress.maximum() == 100
        assert window.progress.value() == 0
        assert '尚未执行' in window.progress.text()
        labels = [item.text() for item in window.findChildren(QLabel)]
        assert any('不代表上传成功' in text for text in labels)
        assert any('未连接' in text for text in labels)
        assert [item.text() for item in window.findChildren(QLabel, 'metric')] == ['0', '0', '0', '0']
        assert '未执行导入或上传操作' in window.logs.toPlainText()
        assert all(not b.isEnabled() and '未启用' in b.text() for b in window.action_buttons)
        assert all('模拟' in p.status for p in DEMO_PRODUCTS)
        window.stack.setCurrentIndex(4)
        assert any('暂无真实上传记录' in l.text() for l in window.stack.currentWidget().findChildren(QLabel))
    finally:
        window.close()
        app.processEvents()
    assert not window.isVisible()


@pytest.mark.parametrize('backend', ['offscreen', 'cocoa'])
def test_main_entry_event_loop_and_clean_close(backend, tmp_path):
    """在隔离进程执行真实入口，定时关闭主窗口，并捕获回调异常。"""
    if backend == 'cocoa' and os.environ.get('RUN_NATIVE_GUI_TESTS') != '1':
        pytest.skip('原生桌面测试未启用；在图形桌面终端设置 RUN_NATIVE_GUI_TESTS=1 执行，不能据此认定通过')
    script = r'''
import runpy, sys
from pathlib import Path
import ui.import_page
ui.import_page.application_database_path = lambda: Path(sys.argv[2])
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow
errors = []
def exception_hook(kind, value, traceback):
    errors.append(str(value))
    sys.__excepthook__(kind, value, traceback)
sys.excepthook = exception_hook
original_exec = QApplication.exec
def bounded_exec(self):
    def inspect_and_close():
        try:
            windows = [w for w in self.topLevelWidgets() if isinstance(w, QMainWindow)]
            assert len(windows) == 1 and windows[0].isVisible()
            assert windows[0].stack.count() == 7
            for button in windows[0].nav_buttons:
                button.click()
            assert windows[0].stack.currentIndex() == 6
            assert windows[0].close()
        except BaseException:
            sys.excepthook(*sys.exc_info())
            self.exit(2)
    QTimer.singleShot(200, inspect_and_close)
    QTimer.singleShot(5000, lambda: self.exit(3))
    return original_exec()
QApplication.exec = bounded_exec
try:
    runpy.run_path(sys.argv[1], run_name='__main__')
except SystemExit as exc:
    assert exc.code == 0, exc.code
assert not errors, errors
print('ENTRY_AND_CLOSE_OK')
'''
    env = {**os.environ, 'QT_QPA_PLATFORM': backend, 'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, '-B', '-c', script, str(ROOT/'main.py'), str(tmp_path/'entry.sqlite3')], cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'ENTRY_AND_CLOSE_OK' in result.stdout
    assert 'Traceback' not in result.stderr


def test_no_automation_or_platform_specific_imports():
    """约束当前入口、界面和数据模块不导入真实自动化或平台专属库。"""
    prohibited = {'win32api','win32com','win32gui','pyautogui','pynput','ctypes','AppKit','Quartz'}
    paths = [ROOT/'main.py', *ROOT.joinpath('ui').glob('*.py'), *ROOT.joinpath('core').glob('*.py')]
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not prohibited.intersection(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or '').split('.')[0] not in prohibited
    runtime = (ROOT/'requirements.txt').read_text()
    assert 'pywin32==312; sys_platform == "win32"' in runtime
