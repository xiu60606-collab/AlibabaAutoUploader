"""macOS 上通过替身验证窗口逻辑，不能代替 Windows 实机验收。"""
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from automation.windows import WindowService,PlatformNotSupported

@pytest.fixture
def service(monkeypatch):
    gui=Mock()
    gui.IsWindow.return_value=True;gui.IsWindowVisible.side_effect=lambda hwnd:hwnd!=2
    gui.GetWindowText.return_value='Alibaba Seller';gui.GetWindowRect.return_value=(10,20,1210,820)
    gui.IsIconic.return_value=True;gui.GetForegroundWindow.return_value=1
    gui.EnumWindows.side_effect=lambda callback,data:[callback(i,data) for i in [1,2]]
    process=Mock();process.GetWindowThreadProcessId.return_value=(7,42);process.QueryFullProcessImageName.return_value='C:/Seller/client.exe'
    api=Mock()
    monkeypatch.setattr(sys,'platform','win32')
    for name,module in [('win32gui',gui),('win32process',process),('win32api',api),('win32con',SimpleNamespace(SW_RESTORE=9))]:monkeypatch.setitem(sys.modules,name,module)
    return WindowService()

def test_platform_guard(monkeypatch):
    monkeypatch.setattr(sys,'platform','darwin')
    with pytest.raises(PlatformNotSupported):WindowService()

def test_enumeration_keyword_process_and_rect(service):
    windows=service.enumerate()
    assert len(windows)==1
    assert windows[0].pid==42 and windows[0].size==(1200,800)
    assert windows[0].minimized
    assert len(service.find('ALIBABA'))==1
    assert service.find('不存在')==[]
    service.api.OpenProcess.return_value.Close.assert_called()

def test_closed_reused_and_permissions(service):
    service.gui.IsWindow.return_value=False
    with pytest.raises(ValueError):service.inspect(1)
    service.gui.IsWindow.return_value=True
    with pytest.raises(ValueError):service.inspect(1,99)
    service.api.OpenProcess.side_effect=PermissionError('denied')
    assert '不可读取' in service.inspect(1).process

def test_activation_result_timeout_and_exception(service,monkeypatch):
    target=service.inspect(1)
    assert service.activate(target)
    service.gui.ShowWindowAsync.assert_called_once()
    service.gui.GetForegroundWindow.return_value=2
    monkeypatch.setattr('automation.windows.time.sleep',lambda _:None)
    assert service.activate(target,0.1) is False
    with pytest.raises(ValueError):service.activate(target,0)
    service.gui.SetForegroundWindow.side_effect=RuntimeError('denied')
    with pytest.raises(RuntimeError):service.activate(target)

def test_debug_non_windows(qt_application,monkeypatch):
    monkeypatch.setattr(sys,'platform','darwin')
    from ui.window_debug import WindowDebug
    dialog=WindowDebug()
    assert not dialog.refresh.isEnabled()
    assert 'macOS' in dialog.message.text()
    dialog.close()
    dialog.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_application.processEvents()


def test_debug_manual_selection_and_refresh_reset(qt_application,monkeypatch):
    from automation.windows import WindowInfo
    from ui.window_debug import WindowDebug
    dialog=WindowDebug()
    target=WindowInfo(99,'Seller',42,'seller.exe',(0,0,100,200),False)
    dialog.show_windows([target])
    assert dialog.target is None
    dialog.table.setCurrentIndex(dialog.model.index(0,0))
    dialog.choose()
    assert dialog.target==target
    assert 'PID 42' in dialog.message.text()
    dialog.scan()
    assert dialog.target is None
    dialog.deleteLater()
    from PySide6.QtCore import QCoreApplication,QEvent
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


def test_debug_activation_failure_message(qt_application,monkeypatch):
    from automation.windows import WindowInfo
    from ui.window_debug import WindowDebug
    dialog=WindowDebug()
    dialog.target=WindowInfo(99,'Seller',42,'seller.exe',(0,0,100,200),False)
    monkeypatch.setattr('ui.window_debug.WindowService',lambda:SimpleNamespace(activate=lambda target:False))
    monkeypatch.setattr(dialog,'run_operation',lambda operation,callback:callback(operation()))
    dialog.status(True)
    assert '未激活' in dialog.message.text()
    dialog.deleteLater()
    from PySide6.QtCore import QCoreApplication,QEvent
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


def test_partial_scan_errors_are_reported(service):
    service.gui.GetWindowRect.side_effect = RuntimeError('window disappeared')
    assert service.enumerate() == []
    assert any('枚举失败' in warning for warning in service.warnings)


def test_keyword_trims_spaces(service):
    assert len(service.find('  Alibaba  ')) == 1
