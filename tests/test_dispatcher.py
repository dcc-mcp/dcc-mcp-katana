from __future__ import annotations

import sys
import threading
from types import SimpleNamespace

import pytest

from dcc_mcp_katana import dispatcher as dispatcher_module


class FakeEventModule:
    def __init__(self, *, auto_run=True):
        self.auto_run = auto_run
        self.handler = None
        self.queued = []
        self.queued_ready = threading.Event()
        self.queue_return_allowed = threading.Event()
        self.queue_return_allowed.set()

    def RegisterEventHandler(self, handler, eventType):
        assert eventType == dispatcher_module.KatanaDispatcher.event_type
        self.handler = handler

    def UnregisterEventHandler(self, handler, eventType):
        assert handler == self.handler
        assert eventType == dispatcher_module.KatanaDispatcher.event_type
        self.handler = None

    def QueueEvent(self, event_type, event_id, pending):
        self.queued.append((event_type, event_id, pending))
        self.queued_ready.set()
        if not self.queue_return_allowed.wait(timeout=1.0):
            raise AssertionError("fake QueueEvent return barrier timed out")
        if self.auto_run:
            self.handler(event_type, event_id, pending=pending)

    def wait_for_queued(self, *, timeout):
        return self.queued_ready.wait(timeout)

    def hold_queue_return(self):
        self.queue_return_allowed.clear()

    def release_queue_return(self):
        self.queue_return_allowed.set()

    def run_next(self):
        event_type, event_id, pending = self.queued.pop(0)
        if not self.queued:
            self.queued_ready.clear()
        self.handler(event_type, event_id, pending=pending)


def install_fake_katana(monkeypatch, event_module):
    katana = SimpleNamespace(Utils=SimpleNamespace(EventModule=event_module))
    monkeypatch.setitem(sys.modules, "Katana", katana)


def run_in_thread(callback):
    result = {}

    def target():
        try:
            result["value"] = callback()
        except Exception as error:
            result["error"] = error

    thread = threading.Thread(target=target)
    thread.start()
    return thread, result


def test_dispatcher_installs_and_executes_queued_call(monkeypatch):
    events = FakeEventModule()
    install_fake_katana(monkeypatch, events)
    dispatcher = dispatcher_module.KatanaDispatcher()
    dispatcher.install()
    thread, result = run_in_thread(lambda: dispatcher.dispatch_callable(lambda value: value + 1, 2))
    thread.join(timeout=2)
    assert result == {"value": 3}
    dispatcher.uninstall()
    assert events.handler is None


@pytest.mark.parametrize("_iteration", range(10))
def test_dispatcher_rejects_over_capacity_and_recovers_after_cancel(monkeypatch, _iteration):
    events = FakeEventModule(auto_run=False)
    install_fake_katana(monkeypatch, events)
    monkeypatch.setattr(dispatcher_module, "MIN_TIMEOUT_SECONDS", 0.02)
    dispatcher = dispatcher_module.KatanaDispatcher(max_pending=1)
    dispatcher.install()
    events.hold_queue_return()

    first_thread, first = run_in_thread(
        lambda: dispatcher.dispatch_callable(lambda: "late", timeout_hint_secs=0.02)
    )
    assert events.wait_for_queued(timeout=1.0)
    assert threading.Event().wait(0.05) is False
    second_thread, second = run_in_thread(lambda: dispatcher.dispatch_callable(lambda: "blocked"))
    second_thread.join(timeout=1)
    assert "queue is full" in str(second["error"])

    events.release_queue_return()
    first_thread.join(timeout=1)
    assert "was cancelled" in str(first["error"])
    events.run_next()
    assert events.queued == []

    recovered_thread, recovered = run_in_thread(
        lambda: dispatcher.dispatch_callable(lambda: "recovered")
    )
    assert events.wait_for_queued(timeout=1.0)
    events.run_next()
    recovered_thread.join(timeout=1)
    assert recovered == {"value": "recovered"}


def test_dispatcher_marks_started_timeout_as_unknown(monkeypatch):
    events = FakeEventModule(auto_run=False)
    install_fake_katana(monkeypatch, events)
    monkeypatch.setattr(dispatcher_module, "MIN_TIMEOUT_SECONDS", 0.02)
    dispatcher = dispatcher_module.KatanaDispatcher()
    dispatcher.install()

    release = threading.Event()
    thread, result = run_in_thread(
        lambda: dispatcher.dispatch_callable(lambda: release.wait(1), timeout_hint_secs=0.02)
    )
    while not events.queued:
        threading.Event().wait(0.001)
    event_type, event_id, pending = events.queued.pop(0)
    runner = threading.Thread(target=lambda: events.handler(event_type, event_id, pending=pending))
    runner.start()
    thread.join(timeout=1)
    assert "outcome is unknown" in str(result["error"])
    release.set()
    runner.join(timeout=1)


def test_timeout_coercion_is_bounded():
    assert dispatcher_module._coerce_timeout(None) == dispatcher_module.DEFAULT_TIMEOUT_SECONDS
    assert dispatcher_module._coerce_timeout(-1) == dispatcher_module.MIN_TIMEOUT_SECONDS
    assert dispatcher_module._coerce_timeout(99999) == dispatcher_module.MAX_TIMEOUT_SECONDS
    with pytest.raises(RuntimeError, match="numeric"):
        dispatcher_module._coerce_timeout("nope")
