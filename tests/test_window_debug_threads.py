"""实际 QThread 生命周期回归；Win32 工作内容使用替身。"""
from threading import Event
import sys
from types import SimpleNamespace
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtTest import QTest
from ui.window_debug import WindowDebug


def settle(dialog,app):
    for _ in range(500):
        app.processEvents()
        if dialog.worker is None:break
        QTest.qWait(10)
    assert dialog.worker is None

@pytest.mark.parametrize('fails',[False,True])
def test_scan_thread_finish_error_reentry_and_close(qt_application,monkeypatch,fails):
    monkeypatch.setattr(sys,'platform','win32')
    gate=Event();calls=[]
    def find(keyword):
        calls.append(keyword)
        if not gate.wait(3):raise TimeoutError('test worker timeout')
        if fails:raise RuntimeError('测试扫描失败')
        return []
    monkeypatch.setattr('ui.window_debug.WindowService',lambda:SimpleNamespace(find=find,warnings=[]))
    dialog=WindowDebug();dialog.show()
    try:
        # QDialog.finished(int) 仍是原信号，不能被线程清理方法覆盖。
        closed=[];dialog.finished.connect(closed.append)
        dialog.scan();worker=dialog.worker
        assert worker is not None
        assert not dialog.refresh.isEnabled()
        dialog.scan();assert dialog.worker is worker
        assert not dialog.close()
        assert dialog.isVisible()
        gate.set();settle(dialog,qt_application)
        assert len(calls)==1
        assert all(b.isEnabled() for b in (dialog.refresh,dialog.select,dialog.check,dialog.activate))
        assert ('测试扫描失败' if fails else '发现 0 个候选窗口') in dialog.message.text()
        # 线程结束后可以再次扫描，无失效引用。
        dialog.scan();settle(dialog,qt_application)
        assert len(calls)==2
        assert dialog.close()
        assert closed
    finally:
        gate.set();settle(dialog,qt_application)
        dialog.close();dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        qt_application.processEvents()
