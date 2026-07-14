"""Katana main-thread dispatcher backed by the native event queue."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, current_thread, main_thread
from typing import Any, Callable, Optional


@dataclass
class _PendingCall:
    callback: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    completed: Event
    result: dict[str, Any]


class KatanaDispatcher:
    """Execute work from Katana's ``Utils.EventModule`` processing loop."""

    event_type = "dcc_mcp_katana_call"

    def __init__(self) -> None:
        self._installed = False

    def install(self) -> None:
        if self._installed:
            return
        from Katana import Utils

        Utils.EventModule.RegisterEventHandler(self._run, eventType=self.event_type)
        self._installed = True

    def uninstall(self) -> None:
        if not self._installed:
            return
        from Katana import Utils

        Utils.EventModule.UnregisterEventHandler(self._run, eventType=self.event_type)
        self._installed = False

    def dispatch_callable(self, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        for key in (
            "context",
            "action_name",
            "skill_name",
            "execution",
            "timeout_hint_secs",
            "affinity",
            "thread_affinity",
        ):
            kwargs.pop(key, None)
        if current_thread() is main_thread():
            return callback(*args, **kwargs)
        if not self._installed:
            raise RuntimeError("Katana event dispatcher is not installed")

        pending = _PendingCall(callback, args, kwargs, Event(), {})
        from Katana import Utils

        Utils.EventModule.QueueEvent(self.event_type, id(pending), pending=pending)
        if not pending.completed.wait(30):
            raise RuntimeError("Timed out waiting for Katana main-thread execution")
        if "error" in pending.result:
            raise pending.result["error"]
        return pending.result["value"]

    def _run(
        self,
        _event_type: str,
        _event_id: int,
        pending: Optional[_PendingCall] = None,
        **_: Any,
    ) -> None:
        if pending is None:
            return
        try:
            pending.result["value"] = pending.callback(*pending.args, **pending.kwargs)
        except Exception as error:
            pending.result["error"] = error
        finally:
            pending.completed.set()
