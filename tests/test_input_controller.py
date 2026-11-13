"""Mock 输入后端，绝不向真实桌面发送输入。"""
import sys,time
from threading import Event,Thread
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from automation.windows import WindowInfo
from automation.input_controller import InputController,Action,InputStopped

@pytest.fixture
def controller(monkeypatch):
    target=WindowInfo(1,'TEST',42,'test.exe',(0,0,500,500),False)
    service=Mock();service.inspect.return_value=target;service.gui.GetForegroundWindow.return_value=1;service.gui.WindowFromPoint.return_value=1
    gui=Mock();gui.position.return_value=(10,10)
    clipboard={'value':'original'}
    clip=SimpleNamespace(paste=lambda:clipboard['value'],copy=lambda v:clipboard.update(value=v))
    monkeypatch.setattr(sys,'platform','win32');monkeypatch.setitem(sys.modules,'pyautogui',gui);monkeypatch.setitem(sys.modules,'pyperclip',clip)
    monkeypatch.setattr('automation.input_controller.WindowService',lambda:service)
    return InputController(target,1,0)

@pytest.mark.parametrize('failure',['missing','pid','foreground','identity'])
def test_invalid_window_no_input(controller,failure):
    if failure in {'missing','pid'}:controller.service.inspect.side_effect=ValueError(failure)
    elif failure=='foreground':controller.service.gui.GetForegroundWindow.return_value=2
    else:controller.service.inspect.return_value=WindowInfo(1,'other',42,'test.exe',(0,0,500,500),False)
    controller.run((Action('click',(10,10)),))
    controller.gui.click.assert_not_called();assert controller.stop_event.is_set()

def test_unicode_ascii_and_clipboard(controller):
    controller.run((Action('ascii','Ab12'),Action('unicode','中文')))
    assert controller.state=='完成'
    controller.gui.hotkey.assert_called_once_with('ctrl','v')
    assert controller.clip.paste()=='original'
    assert controller.gui.FAILSAFE is True

@pytest.mark.parametrize('emergency',[False,True])
def test_pause_resume_stop_duplicate(controller,emergency):
    controller.pause()
    started=Event()
    thread=Thread(target=lambda:controller.run((Action('click',(10,10)),),lambda _:started.set()))
    thread.start();assert started.wait(1)
    try:
        with pytest.raises(RuntimeError):controller.run(())
        assert not controller.gui.click.called
        controller.resume()
        if emergency:controller.emergency_stop()
        else:controller.stop()
    finally:
        controller.stop();thread.join(2)
    assert not thread.is_alive()
    assert controller.stop_event.is_set()

def test_bounds_and_failsafe(controller):
    controller.run((Action('click',(900,900)),))
    controller.gui.click.assert_not_called()

def test_unconfirmed_other_window_and_platform(controller,monkeypatch):
    with pytest.raises(ValueError):InputController(controller.target,2)
    monkeypatch.setattr(sys,'platform','darwin')
    with pytest.raises(RuntimeError):InputController(controller.target,1)

def test_resume_completes(controller):
    controller.pause();started=Event()
    thread=Thread(target=lambda:controller.run((Action('click',(10,10)),),lambda _:started.set()))
    thread.start();assert started.wait(1)
    assert not controller.gui.click.called
    controller.resume();thread.join(2)
    assert not thread.is_alive() and controller.state=='完成'
    controller.gui.click.assert_called_once()


def test_failsafe_stops_before_input(controller):
    controller.gui.failSafeCheck.side_effect=RuntimeError('FAILSAFE')
    controller.run((Action('click',(10,10)),))
    controller.gui.click.assert_not_called()
    assert controller.stop_event.is_set()
